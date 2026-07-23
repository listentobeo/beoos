from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.domain.business_context import BusinessPolicyCreate, ContextReference
from app.infrastructure.models import (
    BusinessPolicy,
    BusinessProfile,
    BusinessService,
    BusinessStaffAuthority,
)

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "database"
    / "migrations"
    / "versions"
    / "20260723_0016_business_context.py"
)


def test_typed_context_models_are_tenant_scoped_and_versioned() -> None:
    for model in (BusinessProfile, BusinessService, BusinessPolicy, BusinessStaffAuthority):
        assert model.__table__.c.business_id.nullable is False
        assert "source_type" in model.__table__.c
        assert "authority_level" in model.__table__.c
        assert "approval_status" in model.__table__.c
    for model in (BusinessProfile, BusinessService, BusinessPolicy):
        assert "version" in model.__table__.c
        assert "supersedes_id" in model.__table__.c


def test_context_migration_enforces_rls_and_version_tenant_integrity() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    for table_name in (
        "business_profiles",
        "business_services",
        "business_policies",
        "business_staff_authorities",
    ):
        assert table_name in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "beoos_can_access_business(business_id)" in migration
    assert "beoos_assert_context_tenant" in migration


def test_policy_categories_are_typed() -> None:
    policy = BusinessPolicyCreate(
        policy_key="discount_controls",
        category="discounts",
        name="Discount controls",
        rules={"autonomous_discounting": False},
        source_type="owner_input",
        source_id="onboarding:1",
        authority_level="official",
        approval_status="approved",
    )
    assert policy.category == "discounts"


def test_context_reference_keeps_provenance_and_classification() -> None:
    reference = ContextReference(
        context_type="business_policy",
        record_id=uuid4(),
        version=2,
        classification="official_fact",
        source_type="owner_approval",
        source_id="approval:1",
        authority_level="official",
        effective_from=datetime.now(UTC),
        expires_at=None,
        approval_status="approved",
        data={"refunds": "human approval required"},
    )
    assert reference.classification == "official_fact"
    assert reference.approval_status == "approved"
