from app.infrastructure.models import Role
from app.services.tool_registry import (
    FUTURE_CONTROLLED_SPECS,
    ROLE_RANK,
    TOOL_SPECS,
    _failure_code,
    _request_hash,
    _sanitize,
    _validate_constraints,
    _validate_schema,
    tool_spec,
)


def test_real_tool_specs_are_typed_and_bounded() -> None:
    keys = {spec.key for spec in TOOL_SPECS}
    assert {
        "read_business_profile",
        "read_brand_policy",
        "read_official_pricing",
        "read_crm_contact",
        "read_recent_conversation",
        "calculate_quotation",
        "read_marketing_metrics",
        "request_human_approval",
    }.issubset(keys)
    assert {
        "create_crm_lead",
        "update_crm_stage",
        "create_draft",
        "create_quotation_draft",
        "schedule_follow_up",
    }.issubset(keys)
    assert all(spec.input_schema.get("type") == "object" for spec in TOOL_SPECS)
    assert all(spec.timeout_seconds <= 30 for spec in TOOL_SPECS)


def test_unimplemented_external_actions_are_registered_but_disabled() -> None:
    future_keys = {item[0] for item in FUTURE_CONTROLLED_SPECS}
    assert "send_approved_email" in future_keys
    assert "send_approved_whatsapp" in future_keys
    assert "create_paystack_payment_link" in future_keys


def test_role_order_and_failure_mapping_are_explicit() -> None:
    assert (
        ROLE_RANK[Role.owner]
        > ROLE_RANK[Role.admin]
        > ROLE_RANK[Role.manager]
        > ROLE_RANK[Role.agent]
    )
    assert _failure_code(PermissionError()) == "authorization"
    assert _failure_code(ValueError()) == "validation"


def test_tool_payload_hash_is_stable_and_secrets_are_redacted() -> None:
    assert _request_hash({"b": 2, "a": 1}) == _request_hash({"a": 1, "b": 2})
    sanitized = _sanitize({"access_token": "private", "value": "safe"})
    assert sanitized == {"access_token": "[REDACTED]", "value": "safe"}


def test_tool_contract_exposes_execution_controls() -> None:
    spec = tool_spec("calculate_quotation")
    assert spec.required_role == Role.agent
    assert spec.idempotency_strategy
    assert spec.retry_policy == "none"
    assert spec.failure_mapping["ValueError"] == "validation"


def test_tool_input_schema_is_enforced_by_backend() -> None:
    schema = tool_spec("calculate_quotation").input_schema
    _validate_schema(
        {"template_type": "mural", "input_data": {}},
        schema,
        "tool input",
    )
    try:
        _validate_schema({"template_type": "mural"}, schema, "tool input")
    except ValueError as exc:
        assert "input_data" in str(exc)
    else:
        raise AssertionError("missing required input was accepted")


def test_tenant_permission_constraints_are_enforced() -> None:
    _validate_constraints({"stage": "qualified"}, {"allowed_values": {"stage": ["qualified"]}})
    try:
        _validate_constraints({"stage": "won"}, {"allowed_values": {"stage": ["qualified"]}})
    except PermissionError:
        pass
    else:
        raise AssertionError("disallowed constrained value was accepted")
