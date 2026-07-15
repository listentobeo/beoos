from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import BusinessAccess, require_admin, require_business_access
from app.domain.quotes import (
    PublicQuoteAcceptResult,
    PublicQuoteView,
    QuoteCreate,
    QuoteTemplateCreate,
    QuoteTemplateUpdate,
    QuoteTemplateView,
    QuoteUpdate,
    QuoteView,
)
from app.infrastructure.database import get_session
from app.infrastructure.models import (
    AuditLog,
    Business,
    Contact,
    CRMLead,
    LeadStage,
    PriceCatalogItem,
    Quote,
    QuoteStatus,
    QuoteTemplate,
    QuoteTemplateType,
)
from app.services.paystack import PaystackService
from app.services.quote_engine import calculate_quote, default_mural_input

router = APIRouter(prefix="/businesses/{business_id}/quotes", tags=["quotes"])
public_router = APIRouter(prefix="/quotes", tags=["public-quotes"])


@router.get("", response_model=list[QuoteView])
async def list_quotes(
    business_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[QuoteView]:
    rows = (
        await session.execute(
            select(Quote, CRMLead, Contact)
            .outerjoin(CRMLead, CRMLead.id == Quote.lead_id)
            .outerjoin(Contact, Contact.id == Quote.contact_id)
            .where(Quote.business_id == business_id)
            .order_by(Quote.updated_at.desc())
        )
    ).all()
    return [_quote_view(quote, lead, contact) for quote, lead, contact in rows]


@router.get("/templates", response_model=list[QuoteTemplateView])
async def list_quote_templates(
    business_id: UUID,
    include_inactive: bool = False,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> list[QuoteTemplateView]:
    query = (
        select(QuoteTemplate)
        .where(QuoteTemplate.business_id == business_id)
        .order_by(QuoteTemplate.active.desc(), QuoteTemplate.updated_at.desc())
    )
    if not include_inactive:
        query = query.where(QuoteTemplate.active.is_(True))
    templates = (await session.scalars(query)).all()
    return [_template_view(template) for template in templates]


@router.post("/templates", response_model=QuoteTemplateView, status_code=201)
async def create_quote_template(
    business_id: UUID,
    payload: QuoteTemplateCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> QuoteTemplateView:
    template = QuoteTemplate(
        business_id=business_id,
        name=payload.name,
        description=payload.description,
        template_type=payload.template_type,
        field_schema=payload.field_schema,
        default_input=payload.default_input,
        design_settings=payload.design_settings,
        terms_settings=payload.terms_settings,
    )
    session.add(template)
    await session.flush()
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="quote_template.created",
            resource_type="quote_template",
            resource_id=str(template.id),
            details={"name": template.name, "template_type": template.template_type.value},
        )
    )
    await session.commit()
    return _template_view(template)


@router.patch("/templates/{template_id}", response_model=QuoteTemplateView)
async def update_quote_template(
    business_id: UUID,
    template_id: UUID,
    payload: QuoteTemplateUpdate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> QuoteTemplateView:
    template = await _template(session, business_id, template_id, include_inactive=True)
    template.name = payload.name
    template.description = payload.description
    template.template_type = payload.template_type
    template.field_schema = payload.field_schema
    template.default_input = payload.default_input
    template.design_settings = payload.design_settings
    template.terms_settings = payload.terms_settings
    template.active = payload.active
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="quote_template.updated",
            resource_type="quote_template",
            resource_id=str(template.id),
            details={"name": template.name, "active": template.active},
        )
    )
    await session.commit()
    return _template_view(template)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_quote_template(
    business_id: UUID,
    template_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    template = await _template(session, business_id, template_id, include_inactive=True)
    template.active = False
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="quote_template.deactivated",
            resource_type="quote_template",
            resource_id=str(template.id),
            details={"name": template.name},
        )
    )
    await session.commit()


@router.get("/{quote_id}", response_model=QuoteView)
async def get_quote(
    business_id: UUID,
    quote_id: UUID,
    _access: BusinessAccess = Depends(require_business_access),
    session: AsyncSession = Depends(get_session),
) -> QuoteView:
    return await _get_quote_view(session, business_id, quote_id)


@router.post("", response_model=QuoteView, status_code=201)
async def create_quote(
    business_id: UUID,
    payload: QuoteCreate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> QuoteView:
    business = await _business(session, business_id)
    template = (
        await _template(session, business_id, payload.template_id)
        if payload.template_id
        else None
    )
    lead = await _lead(session, business_id, payload.lead_id) if payload.lead_id else None
    contact_id = payload.contact_id or (lead.contact_id if lead else None)
    contact = await _contact(session, business_id, contact_id) if contact_id else None
    seeded_input = _apply_template(payload.input_data, template)
    template_type = template.template_type if template else payload.template_type
    input_data = await _attach_catalogue_items(
        session,
        business_id,
        _seed_input(payload, lead, contact, seeded_input, template_type=template_type),
    )
    calculation, proposal, subtotal, total, deposit = calculate_quote(
        business=business,
        template_type=template_type.value,
        input_data=input_data,
    )
    quote = Quote(
        business_id=business_id,
        template_id=template.id if template else None,
        lead_id=payload.lead_id,
        contact_id=contact_id,
        title=payload.title,
        template_type=template_type,
        status=QuoteStatus.draft,
        currency=str(input_data.get("currency") or "NGN").upper()[:3],
        subtotal=subtotal,
        total=total,
        deposit_required=deposit,
        valid_until=payload.valid_until,
        input_data=input_data,
        calculation=calculation,
        proposal=proposal,
        internal_notes="",
    )
    session.add(quote)
    if lead and lead.stage in {
        LeadStage.new,
        LeadStage.contacted,
        LeadStage.qualified,
        LeadStage.quote_needed,
    }:
        lead.stage = LeadStage.quoted
    await session.flush()
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="quote.created",
            resource_type="quote",
            resource_id=str(quote.id),
            details={
                "template_type": quote.template_type.value,
                "lead_id": str(payload.lead_id or ""),
            },
        )
    )
    await session.commit()
    return await _get_quote_view(session, business_id, quote.id)


@router.post("/from-lead/{lead_id}", response_model=QuoteView, status_code=201)
async def create_quote_from_lead(
    business_id: UUID,
    lead_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> QuoteView:
    lead = await _lead(session, business_id, lead_id)
    title = f"{lead.title} Quote"
    payload = QuoteCreate(
        lead_id=lead.id,
        contact_id=lead.contact_id,
        title=title[:240],
        template_type=QuoteTemplateType.mural,
        input_data={},
    )
    return await create_quote(
        business_id=business_id,
        payload=payload,
        access=access,
        session=session,
    )


@router.post("/{quote_id}/payment-link", response_model=QuoteView)
async def create_quote_payment_link(
    business_id: UUID,
    quote_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> QuoteView:
    settings = get_settings()
    row = (
        await session.execute(
            select(Quote, CRMLead, Contact)
            .outerjoin(CRMLead, CRMLead.id == Quote.lead_id)
            .outerjoin(Contact, Contact.id == Quote.contact_id)
            .where(Quote.id == quote_id, Quote.business_id == business_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    quote, lead, contact = row
    if not contact or not contact.email:
        raise HTTPException(status_code=400, detail="Quote needs a client email for Paystack")
    if quote.deposit_required is None:
        raise HTTPException(status_code=400, detail="Quote has no deposit amount")
    if not quote.payment_url:
        reference = f"beoos-{quote.id.hex[:24]}"
        quote.payment_reference = reference
        quote.payment_url = await PaystackService(settings).initialize_transaction(
            email=contact.email,
            amount=quote.deposit_required,
            currency=quote.currency,
            reference=reference,
            callback_url=f"{settings.frontend_url.rstrip('/')}/quotes/{quote.public_token}",
            metadata={
                "quote_id": str(quote.id),
                "business_id": str(business_id),
                "actor_id": access.user_id,
            },
        )
        session.add(
            AuditLog(
                business_id=business_id,
                actor_id=access.user_id,
                action="quote.payment_link_created",
                resource_type="quote",
                resource_id=str(quote.id),
                details={"reference": reference},
            )
        )
        await session.commit()
    return await _get_quote_view(session, business_id, quote.id)


@router.patch("/{quote_id}", response_model=QuoteView)
async def update_quote(
    business_id: UUID,
    quote_id: UUID,
    payload: QuoteUpdate,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> QuoteView:
    business = await _business(session, business_id)
    quote = await session.scalar(
        select(Quote).where(Quote.id == quote_id, Quote.business_id == business_id)
    )
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    input_data = await _attach_catalogue_items(session, business_id, payload.input_data)
    calculation, proposal, subtotal, total, deposit = calculate_quote(
        business=business,
        template_type=quote.template_type.value,
        input_data=input_data,
    )
    old_status = quote.status
    quote.title = payload.title
    quote.status = payload.status
    quote.input_data = input_data
    quote.calculation = calculation
    quote.proposal = proposal
    quote.subtotal = subtotal
    quote.total = total
    quote.deposit_required = deposit
    quote.valid_until = payload.valid_until
    quote.internal_notes = payload.internal_notes
    if payload.status == QuoteStatus.approved and not quote.approved_by:
        quote.approved_by = access.user_id
    if payload.status == QuoteStatus.sent and not quote.sent_at:
        quote.sent_at = datetime.now(UTC)
    if payload.status == QuoteStatus.accepted and not quote.accepted_at:
        quote.accepted_at = datetime.now(UTC)
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="quote.updated",
            resource_type="quote",
            resource_id=str(quote.id),
            details={"old_status": old_status.value, "new_status": quote.status.value},
        )
    )
    await session.commit()
    return await _get_quote_view(session, business_id, quote.id)


@router.delete("/{quote_id}", status_code=204)
async def delete_quote(
    business_id: UUID,
    quote_id: UUID,
    access: BusinessAccess = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
) -> None:
    quote = await session.scalar(
        select(Quote).where(Quote.id == quote_id, Quote.business_id == business_id)
    )
    if quote is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    session.add(
        AuditLog(
            business_id=business_id,
            actor_id=access.user_id,
            action="quote.deleted",
            resource_type="quote",
            resource_id=str(quote.id),
            details={
                "title": quote.title,
                "status": quote.status.value,
                "total": str(quote.total),
                "lead_id": str(quote.lead_id or ""),
            },
        )
    )
    await session.delete(quote)
    await session.commit()


@public_router.get("/{public_token}", response_model=PublicQuoteView)
async def get_public_quote(
    public_token: str,
    session: AsyncSession = Depends(get_session),
) -> PublicQuoteView:
    quote, business, contact = await _public_quote_row(session, public_token)
    if quote.client_viewed_at is None:
        quote.client_viewed_at = datetime.now(UTC)
        await session.commit()
    return _public_quote_view(quote, business, contact)


@public_router.post("/{public_token}/accept", response_model=PublicQuoteAcceptResult)
async def accept_public_quote(
    public_token: str,
    session: AsyncSession = Depends(get_session),
) -> PublicQuoteAcceptResult:
    quote, _business, _contact = await _public_quote_row(session, public_token)
    now = datetime.now(UTC)
    if quote.accepted_at is None:
        quote.accepted_at = now
        quote.status = QuoteStatus.accepted
        if quote.lead_id:
            lead = await session.get(CRMLead, quote.lead_id)
            if lead and lead.stage not in {LeadStage.won, LeadStage.lost}:
                lead.stage = LeadStage.deposit_pending
        await session.commit()
    return PublicQuoteAcceptResult(
        status=quote.status,
        accepted_at=quote.accepted_at or now,
        payment_url=quote.payment_url,
    )


async def _business(session: AsyncSession, business_id: UUID) -> Business:
    business = await session.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


async def _lead(session: AsyncSession, business_id: UUID, lead_id: UUID | None) -> CRMLead:
    lead = await session.scalar(
        select(CRMLead).where(CRMLead.id == lead_id, CRMLead.business_id == business_id)
    )
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


async def _contact(session: AsyncSession, business_id: UUID, contact_id: UUID | None) -> Contact:
    contact = await session.scalar(
        select(Contact).where(Contact.id == contact_id, Contact.business_id == business_id)
    )
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return contact


async def _template(
    session: AsyncSession,
    business_id: UUID,
    template_id: UUID,
    *,
    include_inactive: bool = False,
) -> QuoteTemplate:
    query = select(QuoteTemplate).where(
        QuoteTemplate.id == template_id,
        QuoteTemplate.business_id == business_id,
    )
    if not include_inactive:
        query = query.where(QuoteTemplate.active.is_(True))
    template = await session.scalar(query)
    if template is None:
        raise HTTPException(status_code=404, detail="Quote template not found")
    return template


async def _get_quote_view(session: AsyncSession, business_id: UUID, quote_id: UUID) -> QuoteView:
    row = (
        await session.execute(
            select(Quote, CRMLead, Contact)
            .outerjoin(CRMLead, CRMLead.id == Quote.lead_id)
            .outerjoin(Contact, Contact.id == Quote.contact_id)
            .where(Quote.id == quote_id, Quote.business_id == business_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    quote, lead, contact = row
    return _quote_view(quote, lead, contact)


async def _public_quote_row(
    session: AsyncSession,
    public_token: str,
) -> tuple[Quote, Business, Contact | None]:
    row = (
        await session.execute(
            select(Quote, Business, Contact)
            .join(Business, Business.id == Quote.business_id)
            .outerjoin(Contact, Contact.id == Quote.contact_id)
            .where(Quote.public_token == public_token)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Quote not found")
    return row


def _seed_input(
    payload: QuoteCreate,
    lead: CRMLead | None,
    contact: Contact | None,
    input_data: dict[str, object] | None = None,
    template_type: QuoteTemplateType | None = None,
) -> dict[str, object]:
    seed = dict(input_data or payload.input_data)
    if (template_type or payload.template_type) == QuoteTemplateType.mural:
        seed = default_mural_input(seed)
    if lead:
        seed.setdefault("project_title", lead.title)
        seed.setdefault("project_type", lead.service or "mural")
        seed.setdefault("deadline", lead.deadline or "")
    if contact:
        seed.setdefault("client_name", contact.name or contact.email)
        seed.setdefault("email", contact.email)
        seed.setdefault("phone", contact.phone or "")
    return seed


def _apply_template(
    input_data: dict[str, object],
    template: QuoteTemplate | None,
) -> dict[str, object]:
    if template is None:
        return dict(input_data)
    merged = dict(template.default_input)
    merged.update(template.terms_settings)
    merged["design_settings"] = {
        **template.design_settings,
        **(
            input_data.get("design_settings")
            if isinstance(input_data.get("design_settings"), dict)
            else {}
        ),
    }
    merged.update(input_data)
    return merged


async def _attach_catalogue_items(
    session: AsyncSession,
    business_id: UUID,
    input_data: dict[str, object],
) -> dict[str, object]:
    enriched = dict(input_data)
    raw_ids = enriched.get("price_item_ids")
    if not isinstance(raw_ids, list):
        return enriched
    item_ids: list[UUID] = []
    for raw_id in raw_ids:
        try:
            item_ids.append(UUID(str(raw_id)))
        except ValueError:
            continue
    if not item_ids:
        return enriched
    items = (
        await session.scalars(
            select(PriceCatalogItem).where(
                PriceCatalogItem.business_id == business_id,
                PriceCatalogItem.id.in_(item_ids),
                PriceCatalogItem.active.is_(True),
            )
        )
    ).all()
    enriched["catalogue_items"] = [
        {
            "id": str(item.id),
            "service": item.service,
            "label": item.label,
            "quantity": 1,
            "unit_price": str(item.amount_min or item.amount_max or 0),
            "stock_quantity": item.stock_quantity,
            "custom_fields": item.custom_fields,
        }
        for item in items
    ]
    return enriched


def _quote_view(quote: Quote, lead: CRMLead | None, contact: Contact | None) -> QuoteView:
    settings = get_settings()
    return QuoteView(
        id=quote.id,
        business_id=quote.business_id,
        template_id=quote.template_id,
        lead_id=quote.lead_id,
        contact_id=quote.contact_id,
        title=quote.title,
        template_type=quote.template_type,
        status=quote.status,
        currency=quote.currency,
        subtotal=quote.subtotal,
        total=quote.total,
        deposit_required=quote.deposit_required,
        public_url=f"{settings.frontend_url.rstrip('/')}/quotes/{quote.public_token}",
        valid_until=quote.valid_until,
        input_data=quote.input_data,
        calculation=quote.calculation,
        proposal=quote.proposal,
        internal_notes=quote.internal_notes,
        approved_by=quote.approved_by,
        sent_at=quote.sent_at,
        client_viewed_at=quote.client_viewed_at,
        accepted_at=quote.accepted_at,
        payment_url=quote.payment_url,
        payment_reference=quote.payment_reference,
        created_at=quote.created_at,
        updated_at=quote.updated_at,
        lead_title=lead.title if lead else None,
        contact_name=contact.name if contact else None,
        contact_email=contact.email if contact else None,
    )


def _template_view(template: QuoteTemplate) -> QuoteTemplateView:
    return QuoteTemplateView(
        id=template.id,
        business_id=template.business_id,
        name=template.name,
        description=template.description,
        template_type=template.template_type,
        field_schema=template.field_schema,
        default_input=template.default_input,
        design_settings=template.design_settings,
        terms_settings=template.terms_settings,
        active=template.active,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _public_quote_view(
    quote: Quote,
    business: Business,
    contact: Contact | None,
) -> PublicQuoteView:
    return PublicQuoteView(
        title=quote.title,
        business_name=business.name,
        contact_name=contact.name if contact else None,
        contact_email=contact.email if contact else None,
        status=quote.status,
        currency=quote.currency,
        total=quote.total,
        deposit_required=quote.deposit_required,
        proposal=quote.proposal,
        calculation=quote.calculation,
        payment_url=quote.payment_url,
        accepted_at=quote.accepted_at,
    )
