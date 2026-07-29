from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models import (
    Business,
    MarketingExperiment,
    MarketingMetric,
    MarketingOpportunity,
)

READ_SCOPE = "marketing:read"
PROPOSE_SCOPE = "marketing:propose"
MAX_RANGE_DAYS = 730


class EmptyInput(BaseModel):
    pass


class PageInput(BaseModel):
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0, le=100_000)


class DateRangeInput(PageInput):
    start_date: datetime = Field(default_factory=lambda: datetime.now(UTC) - timedelta(days=90))
    end_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str | None = Field(default=None, min_length=2, max_length=40)

    @model_validator(mode="after")
    def validate_range(self) -> DateRangeInput:
        self.start_date = _aware(self.start_date)
        self.end_date = _aware(self.end_date)
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be earlier than end_date")
        if self.end_date - self.start_date > timedelta(days=MAX_RANGE_DAYS):
            raise ValueError(f"date range cannot exceed {MAX_RANGE_DAYS} days")
        return self


class PerformanceInput(DateRangeInput):
    page_url: str | None = Field(default=None, max_length=2_000)
    query: str | None = Field(default=None, max_length=2_000)


class BrandedInput(DateRangeInput):
    brand_terms: list[str] = Field(default_factory=list, max_length=20)


class RecordListInput(PageInput):
    status: str | None = Field(default=None, max_length=40)


class RecordGetInput(BaseModel):
    id: UUID


class ComparePeriodsInput(BaseModel):
    baseline_start: datetime
    baseline_end: datetime
    comparison_start: datetime
    comparison_end: datetime
    source: str | None = Field(default=None, max_length=40)
    page_url: str | None = Field(default=None, max_length=2_000)
    query: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_periods(self) -> ComparePeriodsInput:
        self.baseline_start = _aware(self.baseline_start)
        self.baseline_end = _aware(self.baseline_end)
        self.comparison_start = _aware(self.comparison_start)
        self.comparison_end = _aware(self.comparison_end)
        if not (
            self.baseline_start < self.baseline_end <= self.comparison_start < self.comparison_end
        ):
            raise ValueError("periods must be ordered and non-overlapping")
        total = self.comparison_end - self.baseline_start
        if total > timedelta(days=MAX_RANGE_DAYS * 2):
            raise ValueError("combined comparison window is too large")
        return self


class OpportunityProposalInput(BaseModel):
    source: str = Field(min_length=2, max_length=80)
    property: str = Field(default="", max_length=2_000)
    page_or_query: str = Field(min_length=1, max_length=2_000)
    evidence_period_start: datetime
    evidence_period_end: datetime
    baseline_metrics: dict[str, Any]
    detected_issue: str = Field(min_length=3, max_length=5_000)
    recommendation: str = Field(min_length=5, max_length=10_000)
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    expected_outcome: str = Field(min_length=3, max_length=2_000)
    limitations: str = Field(default="", max_length=5_000)

    @model_validator(mode="after")
    def validate_evidence_period(self) -> OpportunityProposalInput:
        self.evidence_period_start = _aware(self.evidence_period_start)
        self.evidence_period_end = _aware(self.evidence_period_end)
        if self.evidence_period_start >= self.evidence_period_end:
            raise ValueError("evidence period must be ordered")
        return self


class ExperimentDraftInput(BaseModel):
    opportunity_id: UUID
    approved_change: str = Field(min_length=5, max_length=10_000)
    target: str = Field(min_length=1, max_length=2_000)
    baseline_period_start: datetime
    baseline_period_end: datetime
    comparison_period_start: datetime
    comparison_period_end: datetime

    @model_validator(mode="after")
    def validate_periods(self) -> ExperimentDraftInput:
        values = [
            _aware(self.baseline_period_start),
            _aware(self.baseline_period_end),
            _aware(self.comparison_period_start),
            _aware(self.comparison_period_end),
        ]
        (
            self.baseline_period_start,
            self.baseline_period_end,
            self.comparison_period_start,
            self.comparison_period_end,
        ) = values
        if not (values[0] < values[1] <= values[2] < values[3]):
            raise ValueError("experiment periods must be ordered and non-overlapping")
        return self


class ApprovalRequestInput(BaseModel):
    experiment_id: UUID
    reason: str = Field(min_length=3, max_length=2_000)


class ManualImplementationInput(BaseModel):
    experiment_id: UUID
    implementation_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: str = Field(min_length=3, max_length=5_000)


INPUT_MODELS: dict[str, type[BaseModel]] = {
    "marketing.get_summary": DateRangeInput,
    "marketing.list_properties": PageInput,
    "marketing.get_page_performance": PerformanceInput,
    "marketing.get_query_performance": PerformanceInput,
    "marketing.get_branded_searches": BrandedInput,
    "marketing.list_opportunities": RecordListInput,
    "marketing.get_opportunity": RecordGetInput,
    "marketing.list_experiments": RecordListInput,
    "marketing.get_experiment": RecordGetInput,
    "marketing.compare_periods": ComparePeriodsInput,
    "marketing.get_content_clusters": DateRangeInput,
    "marketing.get_data_freshness": EmptyInput,
    "marketing.propose_opportunity": OpportunityProposalInput,
    "marketing.create_experiment_draft": ExperimentDraftInput,
    "marketing.request_experiment_approval": ApprovalRequestInput,
    "marketing.record_manual_implementation": ManualImplementationInput,
}

MARKETING_TOOL_SCOPES = {
    name: PROPOSE_SCOPE
    if name.startswith("marketing.")
    and name
    in {
        "marketing.propose_opportunity",
        "marketing.create_experiment_draft",
        "marketing.request_experiment_approval",
        "marketing.record_manual_implementation",
    }
    else READ_SCOPE
    for name in INPUT_MODELS
}

DESCRIPTIONS = {
    "marketing.get_summary": "Summarize tenant marketing metrics for a validated date range.",
    "marketing.list_properties": "List configured tenant marketing properties without credentials.",
    "marketing.get_page_performance": (
        "Aggregate page performance with source and freshness metadata."
    ),
    "marketing.get_query_performance": "Aggregate search-query performance.",
    "marketing.get_branded_searches": "List searches matching tenant or supplied brand terms.",
    "marketing.list_opportunities": "List tenant marketing opportunities.",
    "marketing.get_opportunity": "Get one tenant marketing opportunity.",
    "marketing.list_experiments": "List tenant marketing experiments.",
    "marketing.get_experiment": "Get one tenant marketing experiment.",
    "marketing.compare_periods": "Compare two ordered marketing measurement periods.",
    "marketing.get_content_clusters": "Derive evidence-backed content clusters.",
    "marketing.get_data_freshness": "Show data freshness by source.",
    "marketing.propose_opportunity": "Create an internal opportunity proposal for human review.",
    "marketing.create_experiment_draft": (
        "Create an internal experiment draft without implementation."
    ),
    "marketing.request_experiment_approval": "Move an experiment draft to human approval.",
    "marketing.record_manual_implementation": (
        "Record a human implementation of an approved experiment."
    ),
}


def marketing_tool_manifest(scopes: tuple[str, ...]) -> list[dict[str, Any]]:
    allowed = set(scopes)
    tools: list[dict[str, Any]] = []
    for name, model in INPUT_MODELS.items():
        required = MARKETING_TOOL_SCOPES[name]
        if "*" not in allowed and required not in allowed:
            continue
        tools.append(
            {
                "name": name,
                "description": DESCRIPTIONS[name],
                "inputSchema": model.model_json_schema(),
                "outputSchema": {
                    "type": "object",
                    "properties": {
                        "business_id": {"type": "string", "format": "uuid"},
                        "source_metadata": {"type": "object"},
                    },
                    "required": ["business_id"],
                    "additionalProperties": True,
                },
                "annotations": {
                    "readOnlyHint": required == READ_SCOPE,
                    "destructiveHint": False,
                    "openWorldHint": False,
                },
            }
        )
    return tools


async def call_marketing_tool(
    session: AsyncSession,
    *,
    business_id: UUID,
    owner_user_id: str,
    name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    model_type = INPUT_MODELS.get(name)
    if model_type is None:
        raise ValueError(f"Unknown marketing MCP tool: {name}")
    payload = model_type.model_validate(arguments)
    if name == "marketing.list_properties":
        return await _list_properties(session, business_id, payload)
    if name == "marketing.get_data_freshness":
        return await _freshness_response(session, business_id)
    if name == "marketing.list_opportunities":
        return await _list_opportunities(session, business_id, payload)
    if name == "marketing.get_opportunity":
        return await _get_opportunity(session, business_id, payload)
    if name == "marketing.list_experiments":
        return await _list_experiments(session, business_id, payload)
    if name == "marketing.get_experiment":
        return await _get_experiment(session, business_id, payload)
    if name == "marketing.compare_periods":
        return await _compare_periods(session, business_id, payload)
    if name == "marketing.propose_opportunity":
        return await _propose_opportunity(session, business_id, payload)
    if name == "marketing.create_experiment_draft":
        return await _create_experiment_draft(session, business_id, owner_user_id, payload)
    if name == "marketing.request_experiment_approval":
        return await _request_experiment_approval(session, business_id, payload)
    if name == "marketing.record_manual_implementation":
        return await _record_manual_implementation(session, business_id, payload)

    assert isinstance(payload, DateRangeInput)
    rows = await _metrics(session, business_id, payload)
    freshness = _freshness(rows)
    if name == "marketing.get_summary":
        return _summary(business_id, rows, payload, freshness)
    if name == "marketing.get_page_performance":
        assert isinstance(payload, PerformanceInput)
        return _performance(business_id, rows, payload, freshness, dimension="page")
    if name == "marketing.get_query_performance":
        assert isinstance(payload, PerformanceInput)
        return _performance(business_id, rows, payload, freshness, dimension="query")
    if name == "marketing.get_branded_searches":
        assert isinstance(payload, BrandedInput)
        return await _branded(session, business_id, rows, payload, freshness)
    if name == "marketing.get_content_clusters":
        return _clusters(business_id, rows, payload, freshness)
    raise ValueError(f"Unknown marketing MCP tool: {name}")


async def _metrics(
    session: AsyncSession, business_id: UUID, payload: DateRangeInput
) -> list[MarketingMetric]:
    query = select(MarketingMetric).where(
        MarketingMetric.business_id == business_id,
        or_(
            MarketingMetric.metric_date.between(payload.start_date, payload.end_date),
            (
                MarketingMetric.metric_date.is_(None)
                & MarketingMetric.created_at.between(payload.start_date, payload.end_date)
            ),
        ),
    )
    if payload.source:
        query = query.where(MarketingMetric.source == payload.source)
    return list(
        (
            await session.scalars(
                query.order_by(MarketingMetric.metric_date.desc().nullslast()).limit(5_000)
            )
        ).all()
    )


def _summary(
    business_id: UUID,
    rows: list[MarketingMetric],
    payload: DateRangeInput,
    freshness: dict[str, str | None],
) -> dict[str, Any]:
    totals = _totals(rows)
    return {
        "business_id": str(business_id),
        "period": _period(payload.start_date, payload.end_date),
        "totals": totals,
        "sources": sorted({row.source for row in rows}),
        "source_metadata": {"freshness": freshness, "row_limit_applied": len(rows) == 5_000},
    }


async def _list_properties(
    session: AsyncSession, business_id: UUID, payload: BaseModel
) -> dict[str, Any]:
    assert isinstance(payload, PageInput)
    business = await session.get(Business, business_id)
    if business is None:
        raise ValueError("Business not found")
    settings = (business.settings or {}).get("marketing", {})
    if not isinstance(settings, dict):
        settings = {}
    properties = [
        {
            "source": "search_console",
            "property": str(settings.get("search_console_property_url") or ""),
            "connection_status": "configured_not_verified",
        },
        {
            "source": "blogger",
            "property": str(settings.get("blogger_blog_id") or ""),
            "connection_status": "configured_not_verified",
        },
        {
            "source": "clarity",
            "property": str(settings.get("clarity_project_id") or ""),
            "connection_status": "configured_not_verified",
        },
        {
            "source": "website",
            "property": str(settings.get("website_url") or ""),
            "connection_status": "manual_import",
        },
    ]
    properties = [item for item in properties if item["property"]]
    return _page(
        business_id,
        properties[payload.offset : payload.offset + payload.limit],
        payload,
        total=len(properties),
        source_metadata={"credentials_exposed": False, "connections_verified": False},
    )


def _performance(
    business_id: UUID,
    rows: list[MarketingMetric],
    payload: PerformanceInput,
    freshness: dict[str, str | None],
    *,
    dimension: Literal["page", "query"],
) -> dict[str, Any]:
    buckets: dict[str, list[MarketingMetric]] = defaultdict(list)
    for row in rows:
        key = row.page_url if dimension == "page" else row.query
        if not key:
            continue
        if payload.page_url and row.page_url != payload.page_url:
            continue
        if payload.query and row.query != payload.query:
            continue
        buckets[key].append(row)
    items = [
        {
            dimension: key,
            **_totals(values),
            "average_position": _average(
                [float(row.average_position) for row in values if row.average_position is not None]
            ),
        }
        for key, values in buckets.items()
    ]
    items.sort(key=lambda item: (item["impressions"], item["sessions"]), reverse=True)
    return _page(
        business_id,
        items[payload.offset : payload.offset + payload.limit],
        payload,
        total=len(items),
        source_metadata={"freshness": freshness, "dimension": dimension},
    )


async def _branded(
    session: AsyncSession,
    business_id: UUID,
    rows: list[MarketingMetric],
    payload: BrandedInput,
    freshness: dict[str, str | None],
) -> dict[str, Any]:
    business = await session.get(Business, business_id)
    if business is None:
        raise ValueError("Business not found")
    terms = {term.strip().lower() for term in payload.brand_terms if term.strip()}
    terms.update(
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+", business.name)
        if len(token) > 2
    )
    terms.add(business.slug.lower())
    branded = [
        row for row in rows if row.query and any(term in row.query.lower() for term in terms)
    ]
    buckets: dict[str, list[MarketingMetric]] = defaultdict(list)
    for row in branded:
        buckets[row.query].append(row)
    items = [{"query": query, **_totals(values)} for query, values in buckets.items()]
    items.sort(key=lambda item: item["impressions"], reverse=True)
    return _page(
        business_id,
        items[payload.offset : payload.offset + payload.limit],
        payload,
        total=len(items),
        source_metadata={"freshness": freshness, "brand_terms": sorted(terms)},
    )


async def _list_opportunities(
    session: AsyncSession, business_id: UUID, payload: BaseModel
) -> dict[str, Any]:
    assert isinstance(payload, RecordListInput)
    query = select(MarketingOpportunity).where(MarketingOpportunity.business_id == business_id)
    if payload.status:
        query = query.where(MarketingOpportunity.status == payload.status)
    rows = list(
        (
            await session.scalars(
                query.order_by(MarketingOpportunity.created_at.desc())
                .offset(payload.offset)
                .limit(payload.limit + 1)
            )
        ).all()
    )
    has_more = len(rows) > payload.limit
    return _page(
        business_id,
        [_opportunity(row) for row in rows[: payload.limit]],
        payload,
        has_more=has_more,
        source_metadata={"source": "beoos_marketing_opportunities"},
    )


async def _get_opportunity(
    session: AsyncSession, business_id: UUID, payload: BaseModel
) -> dict[str, Any]:
    assert isinstance(payload, RecordGetInput)
    row = await session.scalar(
        select(MarketingOpportunity).where(
            MarketingOpportunity.id == payload.id,
            MarketingOpportunity.business_id == business_id,
        )
    )
    if row is None:
        raise ValueError("Marketing opportunity not found")
    return {
        "business_id": str(business_id),
        "opportunity": _opportunity(row),
        "source_metadata": {"source": "beoos_marketing_opportunities"},
    }


async def _list_experiments(
    session: AsyncSession, business_id: UUID, payload: BaseModel
) -> dict[str, Any]:
    assert isinstance(payload, RecordListInput)
    query = select(MarketingExperiment).where(MarketingExperiment.business_id == business_id)
    if payload.status:
        query = query.where(MarketingExperiment.status == payload.status)
    rows = list(
        (
            await session.scalars(
                query.order_by(MarketingExperiment.created_at.desc())
                .offset(payload.offset)
                .limit(payload.limit + 1)
            )
        ).all()
    )
    return _page(
        business_id,
        [_experiment(row) for row in rows[: payload.limit]],
        payload,
        has_more=len(rows) > payload.limit,
        source_metadata={"source": "beoos_marketing_experiments"},
    )


async def _get_experiment(
    session: AsyncSession, business_id: UUID, payload: BaseModel
) -> dict[str, Any]:
    assert isinstance(payload, RecordGetInput)
    row = await session.scalar(
        select(MarketingExperiment).where(
            MarketingExperiment.id == payload.id,
            MarketingExperiment.business_id == business_id,
        )
    )
    if row is None:
        raise ValueError("Marketing experiment not found")
    return {
        "business_id": str(business_id),
        "experiment": _experiment(row),
        "source_metadata": {"source": "beoos_marketing_experiments"},
    }


async def _compare_periods(
    session: AsyncSession, business_id: UUID, payload: BaseModel
) -> dict[str, Any]:
    assert isinstance(payload, ComparePeriodsInput)
    first = DateRangeInput(
        start_date=payload.baseline_start,
        end_date=payload.baseline_end,
        source=payload.source,
        limit=100,
    )
    second = DateRangeInput(
        start_date=payload.comparison_start,
        end_date=payload.comparison_end,
        source=payload.source,
        limit=100,
    )
    baseline_rows = _filter_metrics(await _metrics(session, business_id, first), payload)
    comparison_rows = _filter_metrics(await _metrics(session, business_id, second), payload)
    baseline = _totals(baseline_rows)
    comparison = _totals(comparison_rows)
    deltas = {
        key: comparison[key] - baseline[key]
        for key in ("rows", "impressions", "clicks", "sessions", "leads")
    }
    return {
        "business_id": str(business_id),
        "baseline": {"period": _period(payload.baseline_start, payload.baseline_end), **baseline},
        "comparison": {
            "period": _period(payload.comparison_start, payload.comparison_end),
            **comparison,
        },
        "deltas": deltas,
        "source_metadata": {
            "freshness": _freshness(baseline_rows + comparison_rows),
            "filters": {
                "source": payload.source,
                "page_url": payload.page_url,
                "query": payload.query,
            },
        },
    }


def _clusters(
    business_id: UUID,
    rows: list[MarketingMetric],
    payload: DateRangeInput,
    freshness: dict[str, str | None],
) -> dict[str, Any]:
    buckets: dict[str, dict[str, Any]] = {}
    stopwords = {"and", "the", "for", "with", "from", "your", "this", "that"}
    for row in rows:
        for token in re.findall(r"[A-Za-z][A-Za-z0-9'-]{2,}", f"{row.query} {row.title}".lower()):
            if token in stopwords:
                continue
            bucket = buckets.setdefault(
                token, {"topic": token, "impressions": 0, "clicks": 0, "queries": set()}
            )
            bucket["impressions"] += row.impressions
            bucket["clicks"] += row.clicks
            if row.query:
                bucket["queries"].add(row.query)
    items = [
        {
            **{key: value for key, value in bucket.items() if key != "queries"},
            "queries": sorted(bucket["queries"])[:10],
            "recommendation": (
                f"Review a focused content cluster around {bucket['topic']} "
                "using the cited queries."
            ),
        }
        for bucket in buckets.values()
        if bucket["impressions"] >= 20 or len(bucket["queries"]) >= 2
    ]
    items.sort(key=lambda item: item["impressions"], reverse=True)
    return _page(
        business_id,
        items[payload.offset : payload.offset + payload.limit],
        payload,
        total=len(items),
        source_metadata={"freshness": freshness, "method": "token_cooccurrence"},
    )


async def _freshness_response(session: AsyncSession, business_id: UUID) -> dict[str, Any]:
    rows = list(
        (
            await session.scalars(
                select(MarketingMetric)
                .where(MarketingMetric.business_id == business_id)
                .order_by(MarketingMetric.created_at.desc())
                .limit(5_000)
            )
        ).all()
    )
    now = datetime.now(UTC)
    items = []
    for source, value in _freshness(rows).items():
        observed = datetime.fromisoformat(value) if value else None
        items.append(
            {
                "source": source,
                "latest_observation": value,
                "age_hours": round((now - observed).total_seconds() / 3600, 2)
                if observed
                else None,
                "status": _freshness_status(now, observed),
            }
        )
    return {
        "business_id": str(business_id),
        "items": items,
        "source_metadata": {
            "generated_at": now.isoformat(),
            "row_limit_applied": len(rows) == 5_000,
        },
    }


async def _propose_opportunity(
    session: AsyncSession, business_id: UUID, payload: BaseModel
) -> dict[str, Any]:
    assert isinstance(payload, OpportunityProposalInput)
    row = MarketingOpportunity(
        business_id=business_id,
        source=payload.source,
        property=payload.property,
        evidence={
            "period": _period(payload.evidence_period_start, payload.evidence_period_end),
            "origin": "mcp_proposal",
        },
        evidence_period_start=payload.evidence_period_start,
        evidence_period_end=payload.evidence_period_end,
        page_or_query=payload.page_or_query,
        baseline_metrics=payload.baseline_metrics,
        detected_issue=payload.detected_issue,
        recommendation=payload.recommendation,
        expected_outcome=payload.expected_outcome,
        limitations=payload.limitations,
        confidence=payload.confidence,
        status="pending_approval",
    )
    session.add(row)
    await session.flush()
    return {
        "business_id": str(business_id),
        "proposal": _opportunity(row),
        "requires_human_approval": True,
        "external_action_performed": False,
    }


async def _create_experiment_draft(
    session: AsyncSession,
    business_id: UUID,
    owner_user_id: str,
    payload: BaseModel,
) -> dict[str, Any]:
    assert isinstance(payload, ExperimentDraftInput)
    opportunity = await session.scalar(
        select(MarketingOpportunity).where(
            MarketingOpportunity.id == payload.opportunity_id,
            MarketingOpportunity.business_id == business_id,
        )
    )
    if opportunity is None:
        raise ValueError("Marketing opportunity not found")
    if opportunity.status != "approved":
        raise ValueError("Marketing opportunity requires human approval before experiment drafting")
    row = MarketingExperiment(
        business_id=business_id,
        opportunity_id=opportunity.id,
        approved_change=payload.approved_change,
        target_page=payload.target,
        baseline_period_start=payload.baseline_period_start,
        baseline_period_end=payload.baseline_period_end,
        comparison_period_start=payload.comparison_period_start,
        comparison_period_end=payload.comparison_period_end,
        owner=owner_user_id,
        execution_method="manual",
        status="draft",
    )
    session.add(row)
    await session.flush()
    return {
        "business_id": str(business_id),
        "draft": _experiment(row),
        "requires_human_approval": True,
        "external_action_performed": False,
    }


async def _request_experiment_approval(
    session: AsyncSession, business_id: UUID, payload: BaseModel
) -> dict[str, Any]:
    assert isinstance(payload, ApprovalRequestInput)
    row = await _tenant_experiment(session, business_id, payload.experiment_id)
    if row.status != "draft":
        raise ValueError("Only draft experiments can request approval")
    row.status = "pending_approval"
    row.result = {**(row.result or {}), "approval_reason": payload.reason}
    await session.flush()
    return {
        "business_id": str(business_id),
        "approval_request": _experiment(row),
        "requires_human_approval": True,
        "external_action_performed": False,
    }


async def _record_manual_implementation(
    session: AsyncSession, business_id: UUID, payload: BaseModel
) -> dict[str, Any]:
    assert isinstance(payload, ManualImplementationInput)
    row = await _tenant_experiment(session, business_id, payload.experiment_id)
    if row.status != "approved":
        raise ValueError("Experiment must be approved before implementation is recorded")
    row.implementation_date = _aware(payload.implementation_date)
    row.status = "measurement_pending"
    row.result = {**(row.result or {}), "implementation_notes": payload.notes}
    await session.flush()
    return {
        "business_id": str(business_id),
        "experiment": _experiment(row),
        "external_action_performed": False,
    }


async def _tenant_experiment(
    session: AsyncSession, business_id: UUID, experiment_id: UUID
) -> MarketingExperiment:
    row = await session.scalar(
        select(MarketingExperiment).where(
            MarketingExperiment.id == experiment_id,
            MarketingExperiment.business_id == business_id,
        )
    )
    if row is None:
        raise ValueError("Marketing experiment not found")
    return row


def _opportunity(row: MarketingOpportunity) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "business_id": str(row.business_id),
        "source": row.source,
        "property": row.property,
        "page_or_query": row.page_or_query,
        "evidence_period": _optional_period(row.evidence_period_start, row.evidence_period_end),
        "evidence": row.evidence,
        "baseline_metrics": row.baseline_metrics,
        "detected_issue": row.detected_issue,
        "recommendation": row.recommendation,
        "confidence": str(row.confidence) if row.confidence is not None else None,
        "expected_outcome": row.expected_outcome,
        "limitations": row.limitations,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _experiment(row: MarketingExperiment) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "business_id": str(row.business_id),
        "opportunity_id": str(row.opportunity_id),
        "approved_change": row.approved_change,
        "target": row.target_page,
        "implementation_date": (
            row.implementation_date.isoformat() if row.implementation_date else None
        ),
        "baseline_period": _period(row.baseline_period_start, row.baseline_period_end),
        "comparison_period": _period(row.comparison_period_start, row.comparison_period_end),
        "owner": row.owner,
        "status": row.status,
        "result_metrics": row.result,
        "interpretation": row.interpretation,
        "confounding_factors": row.confounding_factors,
        "reviewed_lesson": row.lesson,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _page(
    business_id: UUID,
    items: list[dict[str, Any]],
    payload: PageInput,
    *,
    total: int | None = None,
    has_more: bool | None = None,
    source_metadata: dict[str, Any],
) -> dict[str, Any]:
    if has_more is None:
        has_more = total is not None and payload.offset + len(items) < total
    return {
        "business_id": str(business_id),
        "items": items,
        "pagination": {
            "limit": payload.limit,
            "offset": payload.offset,
            "returned": len(items),
            "has_more": bool(has_more),
            "next_offset": payload.offset + len(items) if has_more else None,
            "total": total,
        },
        "source_metadata": source_metadata,
    }


def _totals(rows: list[MarketingMetric]) -> dict[str, int | float]:
    impressions = sum(row.impressions for row in rows)
    clicks = sum(row.clicks for row in rows)
    return {
        "rows": len(rows),
        "impressions": impressions,
        "clicks": clicks,
        "sessions": sum(row.sessions for row in rows),
        "leads": sum(row.leads for row in rows),
        "ctr": round(clicks / impressions, 4) if impressions else 0.0,
    }


def _freshness(rows: list[MarketingMetric]) -> dict[str, str | None]:
    latest: dict[str, datetime] = {}
    for row in rows:
        observed = _aware(row.metric_date or row.created_at)
        if row.source not in latest or observed > latest[row.source]:
            latest[row.source] = observed
    return {source: observed.isoformat() for source, observed in sorted(latest.items())}


def _freshness_status(now: datetime, observed: datetime | None) -> str:
    if observed is None:
        return "no_data"
    age = now - observed
    if age <= timedelta(days=3):
        return "fresh"
    if age <= timedelta(days=14):
        return "aging"
    return "stale"


def _filter_metrics(
    rows: list[MarketingMetric], payload: ComparePeriodsInput
) -> list[MarketingMetric]:
    return [
        row
        for row in rows
        if (not payload.page_url or row.page_url == payload.page_url)
        and (not payload.query or row.query == payload.query)
    ]


def _period(start: datetime, end: datetime) -> dict[str, str]:
    return {"start": _aware(start).isoformat(), "end": _aware(end).isoformat()}


def _optional_period(start: datetime | None, end: datetime | None) -> dict[str, str] | None:
    if start is None or end is None:
        return None
    return _period(start, end)


def _average(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
