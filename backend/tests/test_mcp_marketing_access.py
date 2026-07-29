from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError

from app.api.external_access import _validated_scopes
from app.api.mcp import MCPRequest, _tool_manifest, mcp_rpc
from app.core.config import Settings
from app.core.security import ExternalTokenAccess, require_external_api_token
from app.infrastructure.models import ExternalAPIToken
from app.services.mcp_marketing import (
    DateRangeInput,
    RecordGetInput,
    _get_opportunity,
    call_marketing_tool,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT / "database" / "migrations" / "versions" / "20260729_0028_mcp_marketing_access.py"
)

READ_TOOLS = {
    "marketing.get_summary",
    "marketing.list_properties",
    "marketing.get_page_performance",
    "marketing.get_query_performance",
    "marketing.get_branded_searches",
    "marketing.list_opportunities",
    "marketing.get_opportunity",
    "marketing.list_experiments",
    "marketing.get_experiment",
    "marketing.compare_periods",
    "marketing.get_content_clusters",
    "marketing.get_data_freshness",
}
PROPOSAL_TOOLS = {
    "marketing.propose_opportunity",
    "marketing.create_experiment_draft",
    "marketing.request_experiment_approval",
    "marketing.record_manual_implementation",
}


class ScalarRows:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def all(self) -> list[Any]:
        return self.rows


class FakeSession:
    def __init__(
        self,
        *,
        scalar_values: list[Any] | None = None,
        scalar_rows: list[Any] | None = None,
    ) -> None:
        self.scalar_values = list(scalar_values or [])
        self.scalar_rows = list(scalar_rows or [])
        self.statements: list[Any] = []
        self.added: list[Any] = []
        self.commits = 0

    async def scalar(self, statement: Any) -> Any:
        self.statements.append(statement)
        return self.scalar_values.pop(0) if self.scalar_values else None

    async def scalars(self, statement: Any) -> ScalarRows:
        self.statements.append(statement)
        return ScalarRows(self.scalar_rows)

    async def get(self, _model: Any, _identifier: Any) -> Any:
        return None

    def add(self, value: Any) -> None:
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        pass

    async def refresh(self, _value: Any) -> None:
        pass


def _access(*scopes: str) -> ExternalTokenAccess:
    return ExternalTokenAccess(
        business_id=uuid4(),
        token_id=uuid4(),
        owner_user_id="user_owner",
        scopes=tuple(scopes),
    )


def test_requested_marketing_tools_have_typed_tenant_free_inputs() -> None:
    manifest = _tool_manifest(("marketing:read", "marketing:propose"))
    by_name = {tool["name"]: tool for tool in manifest}
    assert READ_TOOLS | PROPOSAL_TOOLS <= set(by_name)
    for name in READ_TOOLS | PROPOSAL_TOOLS:
        schema = by_name[name]["inputSchema"]
        assert schema["type"] == "object"
        assert "business_id" not in schema.get("properties", {})
        assert by_name[name]["outputSchema"]["properties"]["business_id"]["format"] == "uuid"
        assert by_name[name]["annotations"]["destructiveHint"] is False
    assert all(by_name[name]["annotations"]["readOnlyHint"] for name in READ_TOOLS)
    assert all(not by_name[name]["annotations"]["readOnlyHint"] for name in PROPOSAL_TOOLS)


def test_proposal_tools_require_separate_opt_in_scope() -> None:
    names = {tool["name"] for tool in _tool_manifest(("marketing:read",))}
    assert READ_TOOLS <= names
    assert not names.intersection(PROPOSAL_TOOLS)


def test_external_token_scopes_reject_wildcard_and_unknown_values() -> None:
    with pytest.raises(HTTPException) as wildcard:
        _validated_scopes(["*"])
    assert wildcard.value.status_code == 422
    with pytest.raises(HTTPException):
        _validated_scopes(["marketing:publish"])
    assert _validated_scopes(["marketing:read", "marketing:propose"]) == [
        "marketing:propose",
        "marketing:read",
    ]


def test_date_ranges_are_ordered_and_bounded() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        DateRangeInput(start_date=now, end_date=now - timedelta(days=1))
    with pytest.raises(ValidationError):
        DateRangeInput(start_date=now - timedelta(days=731), end_date=now)


async def test_external_token_revalidates_creator_membership() -> None:
    token = ExternalAPIToken(
        id=uuid4(),
        business_id=uuid4(),
        name="test",
        token_prefix="beoos_test",
        token_hash="hash",
        scopes=["marketing:read"],
        created_by_user_id="former_member",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    session = FakeSession(scalar_values=[token, token.business_id, None])
    with pytest.raises(HTTPException) as denied:
        await require_external_api_token(
            authorization="Bearer raw",
            x_beoos_api_key=None,
            settings=Settings(secret_encryption_key="test"),
            session=session,  # type: ignore[arg-type]
        )
    assert denied.value.status_code == 401
    assert "no longer has business access" in str(denied.value.detail)


@pytest.mark.parametrize(
    ("revoked_at", "expires_at", "expected"),
    [
        (datetime.now(UTC), None, "Invalid"),
        (None, datetime.now(UTC) - timedelta(seconds=1), "Expired"),
    ],
)
async def test_revoked_and_expired_external_tokens_are_rejected(
    revoked_at: datetime | None,
    expires_at: datetime | None,
    expected: str,
) -> None:
    token = ExternalAPIToken(
        id=uuid4(),
        business_id=uuid4(),
        name="test",
        token_prefix="beoos_test",
        token_hash="hash",
        scopes=["marketing:read"],
        created_by_user_id="owner",
        revoked_at=revoked_at,
        expires_at=expires_at,
    )
    session = FakeSession(scalar_values=[token])
    with pytest.raises(HTTPException) as denied:
        await require_external_api_token(
            authorization="Bearer raw",
            x_beoos_api_key=None,
            settings=Settings(secret_encryption_key="test"),
            session=session,  # type: ignore[arg-type]
        )
    assert expected in str(denied.value.detail)


async def test_cross_tenant_record_lookup_derives_business_filter() -> None:
    tenant_id = uuid4()
    other_tenant_id = uuid4()
    session = FakeSession(scalar_values=[None])
    with pytest.raises(ValueError, match="not found"):
        await _get_opportunity(
            session,  # type: ignore[arg-type]
            tenant_id,
            RecordGetInput(id=uuid4()),
        )
    params = session.statements[0].compile().params
    assert tenant_id in params.values()
    assert other_tenant_id not in params.values()


async def test_read_tool_executes_and_returns_authenticated_tenant() -> None:
    access = _access("marketing:read")
    session = FakeSession(scalar_rows=[])
    result = await call_marketing_tool(
        session,  # type: ignore[arg-type]
        business_id=access.business_id,
        owner_user_id=access.owner_user_id,
        name="marketing.get_data_freshness",
        arguments={},
    )
    assert result["business_id"] == str(access.business_id)
    assert result["items"] == []


async def test_mcp_notifications_return_202_and_are_audited() -> None:
    access = _access("marketing:read")
    session = FakeSession(scalar_values=[0])
    response = await mcp_rpc(
        MCPRequest(id=None, method="notifications/initialized"),
        access=access,
        session=session,  # type: ignore[arg-type]
        settings=Settings(mcp_rate_limit_per_minute=60),
        x_request_id="request-123",
        mcp_protocol_version="2025-06-18",
    )
    assert isinstance(response, Response)
    assert response.status_code == 202
    assert session.commits == 1
    audit = session.added[-1]
    assert audit.business_id == access.business_id
    assert audit.token_id == access.token_id
    assert audit.correlation_id == "request-123"
    assert audit.status == "success"


async def test_mcp_rate_limit_returns_safe_json_rpc_error_and_audits() -> None:
    access = _access("marketing:read")
    session = FakeSession(scalar_values=[60])
    response = await mcp_rpc(
        MCPRequest(id=7, method="tools/list"),
        access=access,
        session=session,  # type: ignore[arg-type]
        settings=Settings(mcp_rate_limit_per_minute=60),
        x_request_id=None,
        mcp_protocol_version=None,
    )
    assert isinstance(response, dict)
    assert response["error"]["code"] == -32029
    assert session.added[-1].status == "rate_limited"
    assert session.added[-1].error_code == "rate_limit"


def test_mcp_audit_migration_has_required_security_fields_and_rls() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    for field in (
        "business_id",
        "token_id",
        "correlation_id",
        "tool_name",
        "status",
        "latency_ms",
        "error_code",
        "error_message_safe",
    ):
        assert f'"{field}"' in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "beoos_can_access_business(business_id)" in migration


def test_external_token_model_stores_no_raw_token_column() -> None:
    columns = set(ExternalAPIToken.__table__.columns.keys())
    assert "token_hash" in columns
    assert "token_prefix" in columns
    assert "token" not in columns
    assert "raw_token" not in columns
