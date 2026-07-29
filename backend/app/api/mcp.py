from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import ExternalTokenAccess, require_external_api_token
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    Business,
    CRMLead,
    EmailThread,
    ExternalAPIRequestLog,
    LeadStage,
    MarketingMetric,
    PriceCatalogItem,
    Quote,
    QuoteStatus,
    ThreadCategory,
    ThreadStatus,
)
from app.services.mcp_marketing import (
    MARKETING_TOOL_SCOPES,
    call_marketing_tool,
    marketing_tool_manifest,
)

router = APIRouter(prefix="/mcp", tags=["mcp"])

SERVER_INFO = {"name": "BeoOS", "version": "0.1.0"}
PROTOCOL_VERSION = "2025-06-18"

TOOL_SCOPES = {
    "get_business_profile": "business:read",
    "get_operating_summary": "analytics:read",
    "list_inbox_threads": "inbox:read",
    "list_crm_leads": "crm:read",
    "list_price_catalogue": "pricing:read",
    "list_quotes": "quotes:read",
    "list_marketing_metrics": "marketing:read",
    **MARKETING_TOOL_SCOPES,
}


class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] = Field(default_factory=dict)


class MCPRateLimitError(Exception):
    pass


@router.post("", response_model=None)
async def mcp_rpc(
    request: MCPRequest,
    access: ExternalTokenAccess = Depends(require_external_api_token),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
    x_request_id: str | None = Header(default=None, alias="X-Request-ID"),
    mcp_protocol_version: str | None = Header(default=None, alias="MCP-Protocol-Version"),
) -> dict[str, Any] | Response:
    correlation_id = (x_request_id or "").strip()[:160] or str(uuid.uuid4())
    tool_name = _request_tool_name(request)
    started = time.perf_counter()
    status_value = "success"
    error_code: str | None = None
    error_message: str | None = None
    response: dict[str, Any]
    try:
        await _enforce_rate_limit(session, access, settings)
        if mcp_protocol_version and mcp_protocol_version != PROTOCOL_VERSION:
            raise ValueError(f"Unsupported MCP protocol version: {mcp_protocol_version}")
        if request.method == "initialize":
            result: Any = {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            }
        elif request.method == "notifications/initialized":
            result = {}
        elif request.method == "tools/list":
            result = {"tools": _tool_manifest(access.scopes)}
        elif request.method == "tools/call":
            async with asyncio.timeout(settings.mcp_tool_timeout_seconds):
                result = await _call_tool(session, access, request.params)
        else:
            raise LookupError(f"Unsupported MCP method: {request.method}")
        response = {"jsonrpc": "2.0", "id": request.id, "result": result}
    except MCPRateLimitError as exc:
        await session.rollback()
        status_value, error_code, error_message = "rate_limited", "rate_limit", str(exc)
        response = _error(request.id, -32029, error_message)
    except PermissionError as exc:
        await session.rollback()
        status_value, error_code, error_message = "denied", "scope_denied", str(exc)
        response = _error(request.id, -32003, error_message)
    except ValidationError:
        await session.rollback()
        status_value = "error"
        error_code = "invalid_request"
        error_message = "Invalid tool arguments"
        response = _error(request.id, -32602, error_message)
    except ValueError as exc:
        await session.rollback()
        status_value, error_code, error_message = "error", "invalid_request", str(exc)
        response = _error(request.id, -32602, _safe_error(error_message))
    except LookupError as exc:
        await session.rollback()
        status_value, error_code, error_message = "error", "method_not_found", str(exc)
        response = _error(request.id, -32601, _safe_error(error_message))
    except TimeoutError:
        await session.rollback()
        status_value, error_code, error_message = "timeout", "tool_timeout", "Tool timed out"
        response = _error(request.id, -32008, error_message)
    except Exception:
        await session.rollback()
        status_value = "error"
        error_code = "internal_error"
        error_message = "Internal MCP error"
        response = _error(request.id, -32603, error_message)
    finally:
        await _record_request(
            session,
            access=access,
            correlation_id=correlation_id,
            method=request.method,
            tool_name=tool_name,
            status_value=status_value,
            latency_ms=max(0, round((time.perf_counter() - started) * 1000)),
            error_code=error_code,
            error_message=error_message,
        )
    if request.id is None:
        return Response(status_code=202)
    return response


async def _call_tool(
    session: AsyncSession,
    access: ExternalTokenAccess,
    params: dict[str, Any],
) -> dict[str, Any]:
    name = str(params.get("name") or "")
    arguments = params.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
    _ensure_scope(access, TOOL_SCOPES.get(name, ""))

    data: Any
    if name.startswith("marketing."):
        data = await call_marketing_tool(
            session,
            business_id=access.business_id,
            owner_user_id=access.owner_user_id,
            name=name,
            arguments=arguments,
        )
    elif name == "get_business_profile":
        data = await _business_profile(session, access.business_id)
    elif name == "get_operating_summary":
        data = await _operating_summary(session, access.business_id)
    elif name == "list_inbox_threads":
        data = await _list_inbox_threads(session, access.business_id, arguments)
    elif name == "list_crm_leads":
        data = await _list_crm_leads(session, access.business_id, arguments)
    elif name == "list_price_catalogue":
        data = await _list_price_catalogue(session, access.business_id, arguments)
    elif name == "list_quotes":
        data = await _list_quotes(session, access.business_id, arguments)
    elif name == "list_marketing_metrics":
        data = await _list_marketing_metrics(session, access.business_id, arguments)
    else:
        raise ValueError(f"Unknown BeoOS MCP tool: {name}")

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data, ensure_ascii=False, default=_json_default),
            }
        ],
        "structuredContent": data,
        "isError": False,
    }


async def _business_profile(session: AsyncSession, business_id: UUID) -> dict[str, Any]:
    business = await session.get(Business, business_id)
    if business is None:
        raise ValueError("Business not found")
    return {
        "id": str(business.id),
        "slug": business.slug,
        "name": business.name,
        "primary_email": business.primary_email,
        "whatsapp_number": business.whatsapp_number,
        "timezone": business.timezone,
        "reply_signature": business.reply_signature,
        "settings_summary": _settings_summary(business.settings),
    }


async def _operating_summary(session: AsyncSession, business_id: UUID) -> dict[str, Any]:
    now = datetime.now(UTC)
    open_leads = {
        LeadStage.new,
        LeadStage.contacted,
        LeadStage.qualified,
        LeadStage.quote_needed,
        LeadStage.quoted,
        LeadStage.deposit_pending,
    }
    open_quotes = {
        QuoteStatus.draft,
        QuoteStatus.needs_approval,
        QuoteStatus.approved,
        QuoteStatus.sent,
    }
    return {
        "generated_at": now.isoformat(),
        "inbox_threads": await _count(
            session,
            EmailThread.id,
            EmailThread.business_id == business_id,
        ),
        "unread": int(
            await session.scalar(
                select(func.coalesce(func.sum(EmailThread.unread_count), 0)).where(
                    EmailThread.business_id == business_id
                )
            )
            or 0
        ),
        "needs_approval": await _count(
            session,
            EmailThread.id,
            EmailThread.business_id == business_id,
            EmailThread.status == ThreadStatus.needs_approval,
        ),
        "spam_noise": await _count(
            session,
            EmailThread.id,
            EmailThread.business_id == business_id,
            EmailThread.category == ThreadCategory.spam,
        ),
        "open_crm_leads": await _count(
            session,
            CRMLead.id,
            CRMLead.business_id == business_id,
            CRMLead.stage.in_(open_leads),
        ),
        "open_quotes": await _count(
            session,
            Quote.id,
            Quote.business_id == business_id,
            Quote.status.in_(open_quotes),
        ),
        "active_price_items": await _count(
            session,
            PriceCatalogItem.id,
            PriceCatalogItem.business_id == business_id,
            PriceCatalogItem.active.is_(True),
        ),
        "marketing_rows_30d": await _count(
            session,
            MarketingMetric.id,
            MarketingMetric.business_id == business_id,
            MarketingMetric.created_at >= now - timedelta(days=30),
        ),
    }


async def _list_inbox_threads(
    session: AsyncSession,
    business_id: UUID,
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    limit = _limit(arguments, default=20, maximum=100)
    query = select(EmailThread).where(EmailThread.business_id == business_id)
    category = arguments.get("category")
    status = arguments.get("status")
    if category:
        query = query.where(EmailThread.category == ThreadCategory(str(category)))
    if status:
        query = query.where(EmailThread.status == ThreadStatus(str(status)))
    threads = (
        await session.scalars(query.order_by(EmailThread.latest_message_at.desc()).limit(limit))
    ).all()
    return [
        {
            "id": str(thread.id),
            "subject": thread.subject,
            "category": thread.category.value,
            "status": thread.status.value,
            "priority": thread.priority,
            "is_deal": thread.is_deal,
            "unread_count": thread.unread_count,
            "latest_message_at": thread.latest_message_at,
        }
        for thread in threads
    ]


async def _list_crm_leads(
    session: AsyncSession,
    business_id: UUID,
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    limit = _limit(arguments, default=20, maximum=100)
    query = select(CRMLead).where(CRMLead.business_id == business_id)
    stage = arguments.get("stage")
    if stage:
        query = query.where(CRMLead.stage == LeadStage(str(stage)))
    leads = (
        await session.scalars(
            query.order_by(CRMLead.lead_score.desc(), CRMLead.updated_at.desc()).limit(limit)
        )
    ).all()
    return [
        {
            "id": str(lead.id),
            "title": lead.title,
            "stage": lead.stage.value,
            "source": lead.source.value,
            "service": lead.service,
            "budget": lead.budget,
            "deadline": lead.deadline,
            "estimated_value": lead.estimated_value,
            "currency": lead.currency,
            "probability": lead.probability,
            "lead_score": lead.lead_score,
            "temperature": lead.temperature.value,
            "summary": lead.qualification_summary,
            "next_follow_up_at": lead.next_follow_up_at,
            "updated_at": lead.updated_at,
        }
        for lead in leads
    ]


async def _list_price_catalogue(
    session: AsyncSession,
    business_id: UUID,
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    limit = _limit(arguments, default=50, maximum=200)
    query = select(PriceCatalogItem).where(PriceCatalogItem.business_id == business_id)
    if arguments.get("active_only", True):
        query = query.where(PriceCatalogItem.active.is_(True))
    service = arguments.get("service")
    if service:
        query = query.where(PriceCatalogItem.service == str(service))
    items = (
        await session.scalars(
            query.order_by(PriceCatalogItem.service, PriceCatalogItem.label).limit(limit)
        )
    ).all()
    return [
        {
            "id": str(item.id),
            "service": item.service,
            "label": item.label,
            "amount_min": item.amount_min,
            "amount_max": item.amount_max,
            "currency": item.currency,
            "stock_quantity": item.stock_quantity,
            "custom_fields": item.custom_fields,
            "active": item.active,
            "updated_at": item.updated_at,
        }
        for item in items
    ]


async def _list_quotes(
    session: AsyncSession,
    business_id: UUID,
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    limit = _limit(arguments, default=20, maximum=100)
    query = select(Quote).where(Quote.business_id == business_id)
    status = arguments.get("status")
    if status:
        query = query.where(Quote.status == QuoteStatus(str(status)))
    quotes = (await session.scalars(query.order_by(Quote.updated_at.desc()).limit(limit))).all()
    return [
        {
            "id": str(quote.id),
            "title": quote.title,
            "status": quote.status.value,
            "template_type": quote.template_type.value,
            "currency": quote.currency,
            "subtotal": quote.subtotal,
            "total": quote.total,
            "deposit_required": quote.deposit_required,
            "has_payment_url": bool(quote.payment_url),
            "updated_at": quote.updated_at,
        }
        for quote in quotes
    ]


async def _list_marketing_metrics(
    session: AsyncSession,
    business_id: UUID,
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    limit = _limit(arguments, default=50, maximum=200)
    source = arguments.get("source")
    query = select(MarketingMetric).where(MarketingMetric.business_id == business_id)
    if source:
        query = query.where(MarketingMetric.source == str(source))
    rows = (
        await session.scalars(query.order_by(MarketingMetric.created_at.desc()).limit(limit))
    ).all()
    return [
        {
            "id": str(row.id),
            "source": row.source,
            "page_url": row.page_url,
            "query": row.query,
            "title": row.title,
            "impressions": row.impressions,
            "clicks": row.clicks,
            "sessions": row.sessions,
            "leads": row.leads,
            "ctr": row.ctr,
            "average_position": row.average_position,
            "engagement_rate": row.engagement_rate,
            "avg_time_seconds": row.avg_time_seconds,
            "scroll_depth": row.scroll_depth,
            "metric_date": row.metric_date,
        }
        for row in rows
    ]


async def _count(session: AsyncSession, column: Any, *conditions: Any) -> int:
    value = await session.scalar(select(func.count(column)).where(*conditions))
    return int(value or 0)


def _tool_manifest(scopes: tuple[str, ...]) -> list[dict[str, Any]]:
    allowed_scopes = set(scopes)
    tools = []
    for name, scope in TOOL_SCOPES.items():
        if name.startswith("marketing."):
            continue
        if "*" not in allowed_scopes and scope not in allowed_scopes:
            continue
        tools.append(_tool_schema(name))
    return [*tools, *marketing_tool_manifest(scopes)]


def _tool_schema(name: str) -> dict[str, Any]:
    schemas: dict[str, dict[str, Any]] = {
        "get_business_profile": {
            "description": "Get the connected BeoOS tenant business profile and settings summary.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        "get_operating_summary": {
            "description": (
                "Get a high-level operating summary for inbox, CRM, quotes, pricing, and marketing."
            ),
            "inputSchema": {"type": "object", "properties": {}},
        },
        "list_inbox_threads": {
            "description": "List recent BeoOS inbox threads for this tenant.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "category": {"type": "string"},
                    "status": {"type": "string"},
                },
            },
        },
        "list_crm_leads": {
            "description": "List CRM leads with qualification and follow-up signals.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "stage": {"type": "string"},
                },
            },
        },
        "list_price_catalogue": {
            "description": "List price catalogue and inventory items the AI can use for quotes.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    "service": {"type": "string"},
                    "active_only": {"type": "boolean"},
                },
            },
        },
        "list_quotes": {
            "description": "List quotations and quote payment status signals.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    "status": {"type": "string"},
                },
            },
        },
        "list_marketing_metrics": {
            "description": "List imported marketing intelligence metrics by source.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    "source": {"type": "string"},
                },
            },
        },
    }
    schema = schemas[name]
    return {"name": name, **schema}


def _ensure_scope(access: ExternalTokenAccess, required_scope: str) -> None:
    scopes = set(access.scopes)
    if not required_scope:
        raise PermissionError("Tool does not declare a scope")
    if "*" not in scopes and required_scope not in scopes:
        raise PermissionError(f"Missing scope: {required_scope}")


def _limit(arguments: dict[str, Any], *, default: int, maximum: int) -> int:
    value = arguments.get("limit", default)
    try:
        limit = int(value)
    except (TypeError, ValueError):
        limit = default
    return max(1, min(limit, maximum))


def _settings_summary(settings: dict[str, Any] | None) -> dict[str, Any]:
    values = settings or {}
    raw_whatsapp = values.get("whatsapp")
    whatsapp: dict[str, Any] = raw_whatsapp if isinstance(raw_whatsapp, dict) else {}
    raw_ai_policy = values.get("ai_policy")
    ai_policy: dict[str, Any] = raw_ai_policy if isinstance(raw_ai_policy, dict) else {}
    return {
        "whatsapp_enabled": bool(whatsapp.get("enabled")),
        "whatsapp_connection_mode": whatsapp.get("connection_mode", "unknown"),
        "whatsapp_connection_status": whatsapp.get("connection_status", "unknown"),
        "ai_policy_configured": bool(ai_policy),
        "website_form_configured": bool(values.get("website_form_key")),
    }


def _json_default(value: Any) -> str | int | float | bool | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    return str(value)


def _error(request_id: str | int | None, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _request_tool_name(request: MCPRequest) -> str:
    if request.method != "tools/call":
        return request.method
    return str(request.params.get("name") or "unknown")


async def _enforce_rate_limit(
    session: AsyncSession,
    access: ExternalTokenAccess,
    settings: Settings,
) -> None:
    since = datetime.now(UTC) - timedelta(minutes=1)
    count = int(
        await session.scalar(
            select(func.count(ExternalAPIRequestLog.id)).where(
                ExternalAPIRequestLog.token_id == access.token_id,
                ExternalAPIRequestLog.created_at >= since,
            )
        )
        or 0
    )
    if count >= settings.mcp_rate_limit_per_minute:
        raise MCPRateLimitError("MCP token rate limit exceeded")


async def _record_request(
    session: AsyncSession,
    *,
    access: ExternalTokenAccess,
    correlation_id: str,
    method: str,
    tool_name: str,
    status_value: str,
    latency_ms: int,
    error_code: str | None,
    error_message: str | None,
) -> None:
    try:
        session.add(
            ExternalAPIRequestLog(
                business_id=access.business_id,
                token_id=access.token_id,
                correlation_id=correlation_id,
                method=method[:120],
                tool_name=tool_name[:160],
                status=status_value,
                latency_ms=latency_ms,
                error_code=error_code,
                error_message_safe=_safe_error(error_message) if error_message else None,
            )
        )
        await session.commit()
    except Exception:
        await session.rollback()


def _safe_error(message: str) -> str:
    sanitized = message.replace("beoos_", "[REDACTED]_")
    return sanitized[:500]
