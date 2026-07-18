"""Tenant-scoped marketing intelligence endpoints."""

# ruff: noqa: E501

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.marketing import (
    MarketingActionItem,
    MarketingConnectionStatus,
    MarketingConnectionUpdate,
    MarketingContentCluster,
    MarketingImportRequest,
    MarketingImportResponse,
    MarketingMetricView,
    MarketingPageOpportunity,
    MarketingProviderStatus,
    MarketingQueryOpportunity,
    MarketingSummary,
    MarketingTotal,
)
from app.infrastructure.database import get_session
from app.infrastructure.models import AuditLog, Business, MarketingMetric

router = APIRouter(prefix="/businesses/{business_id}/marketing", tags=["marketing"])

STOPWORDS = {
    "a",
    "about",
    "after",
    "all",
    "and",
    "art",
    "beo",
    "best",
    "buy",
    "can",
    "for",
    "from",
    "how",
    "in",
    "is",
    "me",
    "my",
    "near",
    "of",
    "on",
    "or",
    "price",
    "prices",
    "service",
    "studio",
    "the",
    "to",
    "what",
    "where",
    "with",
    "you",
    "your",
}


@router.get("/connections", response_model=MarketingConnectionStatus)
async def marketing_connections(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> MarketingConnectionStatus:
    business = await _business(session, business_id)
    tenant_settings = _marketing_settings(business)
    return MarketingConnectionStatus(
        business_id=business_id,
        settings=tenant_settings,
        providers=_provider_status(settings=settings, tenant_settings=tenant_settings),
    )


@router.patch("/connections", response_model=MarketingConnectionStatus)
async def update_marketing_connections(
    business_id: UUID,
    payload: MarketingConnectionUpdate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> MarketingConnectionStatus:
    business = await _business(session, business_id)
    merged_settings = dict(business.settings or {})
    merged_settings["marketing"] = payload.model_dump()
    business.settings = merged_settings
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="marketing.connections.updated",
            resource_type="business",
            resource_id=str(business_id),
            details=payload.model_dump(),
        )
    )
    await session.commit()
    return MarketingConnectionStatus(
        business_id=business_id,
        settings=payload,
        providers=_provider_status(settings=settings, tenant_settings=payload),
    )


@router.get("/summary", response_model=MarketingSummary)
async def marketing_summary(
    business_id: UUID,
    window_days: int = Query(default=90, ge=7, le=730),
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> MarketingSummary:
    since = datetime.now(UTC) - timedelta(days=window_days)
    metrics = (
        await session.scalars(
            select(MarketingMetric)
            .where(
                MarketingMetric.business_id == business_id,
                MarketingMetric.created_at >= since,
            )
            .order_by(MarketingMetric.created_at.desc())
            .limit(2000)
        )
    ).all()

    return MarketingSummary(
        window_days=window_days,
        totals=_totals(metrics),
        top_pages=_top_pages(metrics),
        query_opportunities=_query_opportunities(metrics),
        content_clusters=_content_clusters(metrics),
        action_items=_action_items(metrics),
        recent_metrics=[_metric_view(metric) for metric in metrics[:25]],
    )


@router.post("/import", response_model=MarketingImportResponse, status_code=201)
async def import_marketing_metrics(
    business_id: UUID,
    payload: MarketingImportRequest,
    _access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> MarketingImportResponse:
    created = 0
    skipped = 0
    for row in payload.rows:
        page_url = row.page_url.strip()
        query = row.query.strip()
        title = row.title.strip()
        existing = await session.scalar(
            select(MarketingMetric.id).where(
                MarketingMetric.business_id == business_id,
                MarketingMetric.source == payload.source,
                MarketingMetric.page_url == page_url,
                MarketingMetric.query == query,
                MarketingMetric.metric_date == row.metric_date,
            )
        )
        if existing is not None:
            skipped += 1
            continue
        session.add(
            MarketingMetric(
                business_id=business_id,
                source=payload.source,
                page_url=page_url,
                query=query,
                title=title,
                impressions=row.impressions,
                clicks=row.clicks,
                sessions=row.sessions,
                leads=row.leads,
                ctr=_ratio(row.ctr),
                average_position=row.average_position,
                engagement_rate=_ratio(row.engagement_rate),
                avg_time_seconds=row.avg_time_seconds,
                scroll_depth=_ratio(row.scroll_depth),
                metric_date=row.metric_date,
                raw_data=row.raw_data,
            )
        )
        created += 1
    await session.commit()
    return MarketingImportResponse(
        success=True,
        source=payload.source,
        rows_received=len(payload.rows),
        rows_created=created,
        duplicates_skipped=skipped,
    )


async def _business(session: AsyncSession, business_id: UUID) -> Business:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


def _marketing_settings(business: Business) -> MarketingConnectionUpdate:
    raw = (business.settings or {}).get("marketing") if isinstance(business.settings, dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    return MarketingConnectionUpdate.model_validate(raw)


def _provider_status(
    *,
    settings: Settings,
    tenant_settings: MarketingConnectionUpdate,
) -> list[MarketingProviderStatus]:
    google_configured = bool(settings.google_client_id and settings.google_client_secret)
    clarity_configured = bool(settings.microsoft_clarity_api_token)
    return [
        MarketingProviderStatus(
            key="search_console",
            label="Google Search Console",
            configured=google_configured,
            connected=google_configured and bool(tenant_settings.search_console_property_url),
            setup_required=[
                item
                for item, ready in [
                    ("GOOGLE_CLIENT_ID", bool(settings.google_client_id)),
                    ("GOOGLE_CLIENT_SECRET", bool(settings.google_client_secret)),
                    ("Search Console property URL", bool(tenant_settings.search_console_property_url)),
                ]
                if not ready
            ],
            notes="Uses the existing Google OAuth app plus a tenant-owned verified property.",
        ),
        MarketingProviderStatus(
            key="blogger",
            label="Blogger",
            configured=google_configured,
            connected=google_configured and bool(tenant_settings.blogger_blog_id),
            setup_required=[
                item
                for item, ready in [
                    ("GOOGLE_CLIENT_ID", bool(settings.google_client_id)),
                    ("GOOGLE_CLIENT_SECRET", bool(settings.google_client_secret)),
                    ("Blogger blog ID", bool(tenant_settings.blogger_blog_id)),
                ]
                if not ready
            ],
            notes="Uses Blogger API to read posts and performance metadata for content strategy.",
        ),
        MarketingProviderStatus(
            key="clarity",
            label="Microsoft Clarity",
            configured=clarity_configured,
            connected=clarity_configured and bool(tenant_settings.clarity_project_id),
            setup_required=[
                item
                for item, ready in [
                    ("MICROSOFT_CLARITY_API_TOKEN", clarity_configured),
                    ("Clarity project ID", bool(tenant_settings.clarity_project_id)),
                ]
                if not ready
            ],
            notes="Uses Clarity export data to identify friction, rage clicks, scroll depth, and drop-offs.",
        ),
        MarketingProviderStatus(
            key="website",
            label="Website / form leads",
            configured=True,
            connected=bool(tenant_settings.website_url),
            setup_required=[] if tenant_settings.website_url else ["Website URL"],
            notes="Connects the business website identity to BeoOS lead and content analysis.",
        ),
    ]


def _totals(metrics: list[MarketingMetric]) -> list[MarketingTotal]:
    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"rows": 0, "impressions": 0, "clicks": 0, "sessions": 0, "leads": 0}
    )
    for metric in metrics:
        bucket = buckets[metric.source]
        bucket["rows"] += 1
        bucket["impressions"] += metric.impressions
        bucket["clicks"] += metric.clicks
        bucket["sessions"] += metric.sessions
        bucket["leads"] += metric.leads
    return [
        MarketingTotal(source=source, **values)
        for source, values in sorted(
            buckets.items(),
            key=lambda item: item[1]["impressions"] + item[1]["sessions"],
            reverse=True,
        )
    ]


def _top_pages(metrics: list[MarketingMetric]) -> list[MarketingPageOpportunity]:
    buckets: dict[str, dict[str, object]] = {}
    positions: dict[str, list[float]] = defaultdict(list)
    for metric in metrics:
        key = metric.page_url or metric.title or "Unspecified page"
        bucket = buckets.setdefault(
            key,
            {
                "page_url": metric.page_url,
                "title": metric.title or metric.page_url or "Untitled page",
                "impressions": 0,
                "clicks": 0,
                "sessions": 0,
                "leads": 0,
            },
        )
        bucket["impressions"] = int(bucket["impressions"]) + metric.impressions
        bucket["clicks"] = int(bucket["clicks"]) + metric.clicks
        bucket["sessions"] = int(bucket["sessions"]) + metric.sessions
        bucket["leads"] = int(bucket["leads"]) + metric.leads
        if metric.average_position is not None:
            positions[key].append(float(metric.average_position))

    pages: list[MarketingPageOpportunity] = []
    for key, bucket in buckets.items():
        impressions = int(bucket["impressions"])
        clicks = int(bucket["clicks"])
        sessions = int(bucket["sessions"])
        leads = int(bucket["leads"])
        ctr = _safe_rate(clicks, impressions)
        avg_position = _avg(positions[key])
        pages.append(
            MarketingPageOpportunity(
                page_url=str(bucket["page_url"]),
                title=str(bucket["title"]),
                impressions=impressions,
                clicks=clicks,
                sessions=sessions,
                leads=leads,
                ctr=ctr,
                average_position=avg_position,
                recommendation=_page_recommendation(
                    ctr,
                    impressions,
                    avg_position,
                    sessions,
                    leads,
                ),
            )
        )
    return sorted(
        pages,
        key=lambda page: page.impressions + page.sessions,
        reverse=True,
    )[:12]


def _query_opportunities(metrics: list[MarketingMetric]) -> list[MarketingQueryOpportunity]:
    opportunities: list[MarketingQueryOpportunity] = []
    for metric in metrics:
        if not metric.query:
            continue
        ctr = _metric_ctr(metric)
        position = float(metric.average_position) if metric.average_position is not None else None
        if metric.impressions < 20:
            continue
        if ctr > 0.035 and (position is None or position <= 5):
            continue
        opportunities.append(
            MarketingQueryOpportunity(
                query=metric.query,
                page_url=metric.page_url,
                impressions=metric.impressions,
                clicks=metric.clicks,
                ctr=ctr,
                average_position=position,
                recommendation=_query_recommendation(metric.query, ctr, position),
            )
        )
    return sorted(
        opportunities,
        key=lambda item: (item.impressions * (1 - min(item.ctr, 0.2))),
        reverse=True,
    )[:20]


def _content_clusters(metrics: list[MarketingMetric]) -> list[MarketingContentCluster]:
    clusters: dict[str, dict[str, object]] = {}
    for metric in metrics:
        text = " ".join(part for part in [metric.query, metric.title] if part)
        for token in _tokens(text):
            cluster = clusters.setdefault(token, {"impressions": 0, "clicks": 0, "queries": set()})
            cluster["impressions"] = int(cluster["impressions"]) + metric.impressions
            cluster["clicks"] = int(cluster["clicks"]) + metric.clicks
            if metric.query:
                queries = cluster["queries"]
                if isinstance(queries, set):
                    queries.add(metric.query)

    output: list[MarketingContentCluster] = []
    for topic, cluster in clusters.items():
        queries = sorted(cluster["queries"]) if isinstance(cluster["queries"], set) else []
        impressions = int(cluster["impressions"])
        clicks = int(cluster["clicks"])
        if impressions < 20 and len(queries) < 2:
            continue
        output.append(
            MarketingContentCluster(
                topic=topic.title(),
                impressions=impressions,
                clicks=clicks,
                queries=queries[:5],
                recommended_angle=_cluster_angle(topic, queries),
            )
        )
    return sorted(output, key=lambda item: item.impressions, reverse=True)[:12]


def _action_items(metrics: list[MarketingMetric]) -> list[MarketingActionItem]:
    actions: list[MarketingActionItem] = []
    for page in _top_pages(metrics):
        if page.impressions >= 100 and page.ctr < 0.025:
            actions.append(
                MarketingActionItem(
                    priority="high",
                    source="search_console",
                    label="High impressions, weak click-through",
                    reason=(
                        f"{page.title} has {page.impressions} impressions but only "
                        f"{page.ctr:.1%} CTR."
                    ),
                    recommended_action=(
                        "Rewrite the page title/meta description around the clearest buying "
                        "intent, then add a stronger above-the-fold CTA."
                    ),
                    page_url=page.page_url or None,
                )
            )
        if page.sessions >= 50 and page.leads == 0:
            actions.append(
                MarketingActionItem(
                    priority="medium",
                    source="clarity",
                    label="Traffic without lead capture",
                    reason=f"{page.title} has {page.sessions} sessions but no imported leads.",
                    recommended_action=(
                        "Inspect Clarity recordings for drop-offs, then add a visible "
                        "WhatsApp/form CTA near the section users reach before leaving."
                    ),
                    page_url=page.page_url or None,
                )
            )
        if page.average_position and 6 <= page.average_position <= 20 and page.impressions >= 50:
            actions.append(
                MarketingActionItem(
                    priority="medium",
                    source="search_console",
                    label="Ranking within striking distance",
                    reason=f"{page.title} averages position {page.average_position:.1f}.",
                    recommended_action=(
                        "Refresh the page with missing FAQs, pricing proof, internal links, "
                        "and a clearer service-specific offer."
                    ),
                    page_url=page.page_url or None,
                )
            )
    for cluster in _content_clusters(metrics)[:4]:
        actions.append(
            MarketingActionItem(
                priority="low",
                source="content_cluster",
                label=f"Build cluster: {cluster.topic}",
                reason=(
                    f"{cluster.topic} is appearing across "
                    f"{len(cluster.queries)} query signal(s)."
                ),
                recommended_action=cluster.recommended_angle,
            )
        )
    return actions[:12]


def _metric_view(metric: MarketingMetric) -> MarketingMetricView:
    return MarketingMetricView(
        id=metric.id,
        source=metric.source,
        page_url=metric.page_url,
        query=metric.query,
        title=metric.title,
        impressions=metric.impressions,
        clicks=metric.clicks,
        sessions=metric.sessions,
        leads=metric.leads,
        ctr=metric.ctr,
        average_position=metric.average_position,
        engagement_rate=metric.engagement_rate,
        avg_time_seconds=metric.avg_time_seconds,
        scroll_depth=metric.scroll_depth,
        metric_date=metric.metric_date,
        created_at=metric.created_at,
    )


def _ratio(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if value > 1:
        return value / Decimal("100")
    return value


def _metric_ctr(metric: MarketingMetric) -> float:
    if metric.ctr is not None:
        return float(metric.ctr)
    return _safe_rate(metric.clicks, metric.impressions)


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _page_recommendation(
    ctr: float,
    impressions: int,
    avg_position: float | None,
    sessions: int,
    leads: int,
) -> str:
    if impressions >= 100 and ctr < 0.025:
        return (
            "Rewrite title/meta and make the offer clearer; visibility exists but the search "
            "result is not winning enough clicks."
        )
    if avg_position is not None and 6 <= avg_position <= 20:
        return (
            "Refresh this page; it is close enough to compete with better FAQs, proof, pricing "
            "clarity, and internal links."
        )
    if sessions >= 50 and leads == 0:
        return (
            "Improve conversion; add clearer WhatsApp/form CTAs and inspect user recordings "
            "for friction."
        )
    return "Keep monitoring; this page is a useful signal source."


def _query_recommendation(query: str, ctr: float, position: float | None) -> str:
    if position is not None and 6 <= position <= 20:
        return f"Create or refresh a section answering “{query}” directly, then link to the strongest service page."
    if ctr < 0.025:
        return f"Improve the search snippet for “{query}” with clearer benefit, location/service intent, and proof."
    return f"Use “{query}” as a supporting FAQ or content angle."


def _cluster_angle(topic: str, queries: list[str]) -> str:
    if queries:
        return f"Create a focused content cluster around {topic}: one authority service page, 3-5 support articles, and FAQs based on queries like “{queries[0]}”."
    return f"Create a focused content cluster around {topic}: authority page, support articles, FAQs, and internal links."


def _tokens(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", text.lower())
    return [token for token in tokens if token not in STOPWORDS][:12]
