import hashlib
import json
import re
from decimal import Decimal
from typing import Any
from uuid import UUID

import httpx
import structlog
from openai import AsyncOpenAI
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.domain.quotes import (
    QuoteAIDraftLineItem,
    QuoteAIDraftRequest,
    QuoteAIDraftResponse,
)
from app.infrastructure.models import (
    Business,
    Contact,
    CRMLead,
    EmailMessage,
    EmailThread,
    PriceCatalogItem,
    QuoteTemplate,
    QuoteTemplateType,
)
from app.services.quote_engine import default_mural_input

logger = structlog.get_logger()

SYSTEM_PROMPT = """
You are BeoOS Quote Architect, a tenant-aware quotation specialist for SMEs.

You turn BeoOS business context into a structured quotation draft. You do not create records,
send messages, promise fixed prices, or invent stock/fees that are not supported by the context.

Rules:
- Return only valid JSON matching the requested schema.
- Use the business brand policy, quote templates, and price catalogue first.
- If information is missing, put it in missing_information instead of hallucinating.
- For custom quotes, use line_items when catalogue/pricing exists.
- For mural/service quotes, write clear client-facing proposal language.
- Keep every output scoped to this tenant only.
"""


class QuoteAIService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def draft(
        self,
        *,
        session: AsyncSession,
        business_id: UUID,
        user_id: str,
        payload: QuoteAIDraftRequest,
    ) -> QuoteAIDraftResponse:
        context = await self._context(session=session, business_id=business_id, payload=payload)
        fallback = self._fallback(payload=payload, context=context)
        provider = self._effective_provider()
        if provider is None:
            fallback.warnings.append(
                "No AI quote provider is configured yet; BeoOS generated a "
                "structured fallback draft."
            )
            return fallback
        try:
            if provider == "anthropic":
                return await self._anthropic(payload=payload, context=context)
            if provider == "replicate":
                return await self._replicate(payload=payload, context=context, user_id=user_id)
            return await self._openai(payload=payload, context=context, user_id=user_id)
        except Exception:
            logger.exception(
                "quote_ai_draft_failed",
                business_id=str(business_id),
                provider=provider,
            )
            fallback.warnings.append(
                f"{provider.title()} quote drafting failed; BeoOS returned a "
                "structured fallback draft."
            )
            return fallback

    def _effective_provider(self) -> str | None:
        if self._settings.ai_quote_provider == "anthropic":
            return "anthropic" if self._settings.anthropic_api_key else None
        if self._settings.ai_quote_provider == "openai":
            return "openai" if self._settings.openai_api_key else None
        if self._settings.ai_quote_provider == "replicate":
            return "replicate" if self._settings.replicate_api_token else None
        if self._settings.anthropic_api_key:
            return "anthropic"
        if self._settings.ai_configured:
            return self._settings.effective_ai_provider
        return None

    async def _context(
        self,
        *,
        session: AsyncSession,
        business_id: UUID,
        payload: QuoteAIDraftRequest,
    ) -> dict[str, Any]:
        business = await session.get(Business, business_id)
        lead = (
            await session.scalar(
                select(CRMLead).where(
                    CRMLead.business_id == business_id,
                    CRMLead.id == payload.lead_id,
                )
            )
            if payload.lead_id
            else None
        )
        contact_id = payload.contact_id or (lead.contact_id if lead else None)
        contact = (
            await session.scalar(
                select(Contact).where(Contact.business_id == business_id, Contact.id == contact_id)
            )
            if contact_id
            else None
        )
        template = (
            await session.scalar(
                select(QuoteTemplate).where(
                    QuoteTemplate.business_id == business_id,
                    QuoteTemplate.id == payload.template_id,
                    QuoteTemplate.active.is_(True),
                )
            )
            if payload.template_id
            else None
        )
        templates = (
            await session.scalars(
                select(QuoteTemplate)
                .where(QuoteTemplate.business_id == business_id, QuoteTemplate.active.is_(True))
                .order_by(QuoteTemplate.updated_at.desc())
                .limit(8)
            )
        ).all()
        prices = (
            await session.scalars(
                select(PriceCatalogItem)
                .where(
                    PriceCatalogItem.business_id == business_id,
                    PriceCatalogItem.active.is_(True),
                )
                .order_by(PriceCatalogItem.updated_at.desc())
                .limit(40)
            )
        ).all()
        thread_messages: list[EmailMessage] = []
        if lead and lead.thread_id:
            thread_messages = (
                await session.scalars(
                    select(EmailMessage)
                    .join(EmailThread, EmailThread.id == EmailMessage.thread_id)
                    .where(
                        EmailThread.business_id == business_id,
                        EmailMessage.thread_id == lead.thread_id,
                    )
                    .order_by(EmailMessage.sent_at.desc())
                    .limit(6)
                )
            ).all()

        return {
            "business": {
                "id": str(business.id) if business else str(business_id),
                "name": business.name if business else "Business",
                "primary_email": business.primary_email if business else "",
                "reply_signature": business.reply_signature if business else "",
                "timezone": business.timezone if business else "Africa/Lagos",
                "settings": _json(business.settings if business else {}),
            },
            "lead": _lead_context(lead),
            "contact": _contact_context(contact),
            "selected_template": _template_context(template),
            "templates": [_template_context(item) for item in templates],
            "price_catalogue": [_price_context(item) for item in prices],
            "recent_thread_messages": [
                {
                    "sender": message.sender_email,
                    "subject": message.subject,
                    "body_text": message.body_text[:1200],
                    "sent_at": message.sent_at.isoformat(),
                }
                for message in reversed(thread_messages)
            ],
        }

    async def _openai(
        self,
        *,
        payload: QuoteAIDraftRequest,
        context: dict[str, Any],
        user_id: str,
    ) -> QuoteAIDraftResponse:
        client = AsyncOpenAI(api_key=self._settings.openai_api_key)
        try:
            response = await client.responses.parse(
                model=self._settings.openai_model,
                instructions=SYSTEM_PROMPT,
                input=self._prompt(payload=payload, context=context),
                reasoning={"effort": "low"},
                text_format=QuoteAIDraftResponse,
                store=False,
                safety_identifier=hashlib.sha256(user_id.encode()).hexdigest()[:64],
            )
            if response.output_parsed is None:
                raise RuntimeError("OpenAI returned no quote draft")
            output = response.output_parsed
            output.provider = "openai"
            output.model = self._settings.openai_model
            return output
        finally:
            await client.close()

    async def _anthropic(
        self,
        *,
        payload: QuoteAIDraftRequest,
        context: dict[str, Any],
    ) -> QuoteAIDraftResponse:
        body = {
            "model": self._settings.anthropic_model,
            "max_tokens": 2200,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": self._prompt(payload=payload, context=context),
                }
            ],
        }
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self._settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
        text = "".join(
            part.get("text", "")
            for part in response.json().get("content", [])
            if isinstance(part, dict)
        )
        output = _parse_response(text)
        output.provider = "anthropic"
        output.model = self._settings.anthropic_model
        return output

    async def _replicate(
        self,
        *,
        payload: QuoteAIDraftRequest,
        context: dict[str, Any],
        user_id: str,
    ) -> QuoteAIDraftResponse:
        owner, model = self._settings.replicate_model.split("/", maxsplit=1)
        url = f"https://api.replicate.com/v1/models/{owner}/{model}/predictions"
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            "Response JSON schema:\n"
            f"{json.dumps(QuoteAIDraftResponse.model_json_schema(), ensure_ascii=False)}\n\n"
            f"{self._prompt(payload=payload, context=context)}"
        )
        input_payload = {
            "prompt": prompt,
            "system_prompt": "Return only valid JSON.",
            "reasoning_effort": "medium",
            "verbosity": "low",
            "max_completion_tokens": 2200,
        }
        headers = {
            "Authorization": f"Bearer {self._settings.replicate_api_token}",
            "Content-Type": "application/json",
            "Prefer": "wait=10",
        }
        async with httpx.AsyncClient(timeout=self._settings.replicate_timeout_seconds) as client:
            response = await client.post(
                url,
                headers=headers,
                json={
                    "input": input_payload,
                    "context": {
                        "safety_identifier": hashlib.sha256(user_id.encode()).hexdigest()[:64],
                    },
                },
            )
            if response.status_code == 422:
                response = await client.post(url, headers=headers, json={"input": input_payload})
            response.raise_for_status()
            prediction = response.json()
            output = await self._poll_replicate(client, str(prediction["id"]))
        draft = _parse_response(_stringify_output(output))
        draft.provider = "replicate"
        draft.model = self._settings.replicate_model
        return draft

    async def _poll_replicate(self, client: httpx.AsyncClient, prediction_id: str) -> Any:
        attempts = max(1, self._settings.replicate_timeout_seconds // 3)
        for _ in range(attempts):
            response = await client.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers={"Authorization": f"Bearer {self._settings.replicate_api_token}"},
            )
            response.raise_for_status()
            prediction = response.json()
            if prediction.get("status") == "succeeded":
                return prediction.get("output")
            if prediction.get("status") in {"failed", "canceled"}:
                raise RuntimeError(f"Replicate prediction {prediction.get('status')}")
        raise RuntimeError("Replicate prediction timed out")

    def _prompt(self, *, payload: QuoteAIDraftRequest, context: dict[str, Any]) -> str:
        return json.dumps(
            {
                "task": "Generate a BeoOS quotation draft. Do not create the quote.",
                "user_request": payload.model_dump(mode="json"),
                "tenant_context": context,
                "output_schema": QuoteAIDraftResponse.model_json_schema(),
            },
            ensure_ascii=False,
            default=str,
        )

    def _fallback(
        self,
        *,
        payload: QuoteAIDraftRequest,
        context: dict[str, Any],
    ) -> QuoteAIDraftResponse:
        business = context["business"]
        lead = context.get("lead") or {}
        contact = context.get("contact") or {}
        template = context.get("selected_template") or {}
        client_name = (
            payload.client_name
            or contact.get("name")
            or contact.get("email")
            or "Client"
        )
        service = (
            payload.service
            or lead.get("service")
            or _infer_service(payload.prompt)
            or "service"
        )
        title = (
            payload.title
            or f"{client_name} {service.title()} Quote"
        )[:240]
        template_type = (
            template.get("template_type")
            or payload.template_type
            or QuoteTemplateType.custom
        )
        if str(template_type) == "mural":
            input_data = default_mural_input(
                {
                    "client_name": client_name,
                    "email": contact.get("email") or "",
                    "phone": contact.get("phone") or "",
                    "project_title": title,
                    "project_type": service,
                    "deadline": payload.deadline or lead.get("deadline") or "",
                    "problem": payload.notes or lead.get("summary") or "",
                    "solution": payload.prompt,
                    "reference_assets": payload.reference_assets,
                }
            )
            line_items: list[QuoteAIDraftLineItem] = []
        else:
            line_items = self._catalogue_line_items(
                service,
                context["price_catalogue"],
                payload.prompt,
            )
            input_data = {
                "client_name": client_name,
                "email": contact.get("email") or "",
                "phone": contact.get("phone") or "",
                "project_title": title,
                "summary": payload.prompt,
                "scope": _template_value(template, "scope")
                or f"{business['name']} will provide the listed {service} items/services.",
                "timeline": (
                    payload.deadline
                    or lead.get("deadline")
                    or _template_value(template, "timeline")
                )
                or "Timeline to be agreed after approval.",
                "payment_terms": _template_value(template, "payment_terms")
                or "Payment terms to be agreed before commencement.",
                "assumptions": _template_value(template, "assumptions")
                or "Pricing is based on the information currently available.",
                "exclusions": _template_value(template, "exclusions") or "",
                "warranty": _template_value(template, "warranty") or "",
                "deposit_percent": _template_value(template, "deposit_percent") or "50",
                "currency": "NGN",
                "line_items": [item.model_dump() for item in line_items],
                "design_settings": template.get("design_settings") or {},
                "reference_assets": payload.reference_assets,
                "reference_notes": payload.notes,
            }
        missing = []
        if client_name == "Client":
            missing.append("Client name")
        if not contact.get("email") and not contact.get("phone"):
            missing.append("Client email or phone number")
        if not line_items and str(template_type) == "custom":
            missing.append("Priced catalogue item or manual line item")
        return QuoteAIDraftResponse(
            provider="deterministic",
            model="fallback",
            title=title,
            template_type=QuoteTemplateType(str(template_type)),
            template_id=UUID(str(template["id"])) if template.get("id") else payload.template_id,
            lead_id=payload.lead_id,
            contact_id=UUID(str(contact["id"])) if contact.get("id") else payload.contact_id,
            input_data=input_data,
            line_items=line_items,
            summary=(
                f"Prepared a draft for {client_name}. It uses tenant context, "
                "available template defaults, and catalogue items where matched."
            ),
            assumptions=[
                "The user will review pricing and scope before sending.",
                "Payment links are generated only after a quote exists and "
                "Paystack/Stripe is configured.",
            ],
            missing_information=missing,
        )

    def _catalogue_line_items(
        self,
        service: str,
        prices: list[dict[str, Any]],
        prompt: str,
    ) -> list[QuoteAIDraftLineItem]:
        haystack = f"{service} {prompt}".lower()
        matches = [
            item
            for item in prices
            if item["service"].lower() in haystack or item["label"].lower() in haystack
        ][:5]
        if not matches and prices:
            matches = prices[:3]
        return [
            QuoteAIDraftLineItem(
                label=item["label"],
                description=item["service"],
                quantity="1",
                unit_price=str(item.get("amount_min") or item.get("amount_max") or "0"),
            )
            for item in matches
        ]


def _lead_context(lead: CRMLead | None) -> dict[str, Any] | None:
    if lead is None:
        return None
    return {
        "id": str(lead.id),
        "contact_id": str(lead.contact_id) if lead.contact_id else None,
        "thread_id": str(lead.thread_id) if lead.thread_id else None,
        "title": lead.title,
        "stage": lead.stage.value,
        "source": lead.source.value,
        "service": lead.service,
        "budget": lead.budget,
        "deadline": lead.deadline,
        "estimated_value": str(lead.estimated_value) if lead.estimated_value else None,
        "currency": lead.currency,
        "lead_score": lead.lead_score,
        "temperature": lead.temperature.value,
        "summary": lead.qualification_summary,
        "reasons": lead.qualification_reasons,
        "notes": lead.notes,
    }


def _contact_context(contact: Contact | None) -> dict[str, Any] | None:
    if contact is None:
        return None
    return {
        "id": str(contact.id),
        "name": contact.name,
        "email": contact.email,
        "phone": contact.phone,
        "preferred_channel": contact.preferred_channel,
        "is_existing_client": contact.is_existing_client,
    }


def _template_context(template: QuoteTemplate | None) -> dict[str, Any] | None:
    if template is None:
        return None
    return {
        "id": str(template.id),
        "name": template.name,
        "description": template.description,
        "template_type": template.template_type.value,
        "field_schema": _json(template.field_schema),
        "default_input": _json(template.default_input),
        "design_settings": _json(template.design_settings),
        "terms_settings": _json(template.terms_settings),
    }


def _price_context(item: PriceCatalogItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "service": item.service,
        "label": item.label,
        "amount_min": str(item.amount_min) if item.amount_min is not None else None,
        "amount_max": str(item.amount_max) if item.amount_max is not None else None,
        "currency": item.currency,
        "stock_quantity": item.stock_quantity,
        "custom_fields": _json(item.custom_fields),
    }


def _template_value(template: dict[str, Any] | None, key: str) -> Any:
    if not template:
        return None
    for bucket in ("terms_settings", "default_input"):
        values = template.get(bucket)
        if isinstance(values, dict) and values.get(key):
            return values[key]
    return None


def _infer_service(prompt: str) -> str:
    lowered = prompt.lower()
    for keyword in ("mural", "portrait", "bulk", "retainer", "training", "repair", "installation"):
        if keyword in lowered:
            return keyword
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", lowered)
    return words[0] if words else "service"


def _parse_response(text: str) -> QuoteAIDraftResponse:
    try:
        return QuoteAIDraftResponse.model_validate_json(text)
    except ValidationError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start < 0 or end <= start:
            raise RuntimeError("AI provider returned invalid quote JSON") from None
        return QuoteAIDraftResponse.model_validate_json(text[start:end])


def _json(value: Any) -> Any:
    return json.loads(json.dumps(value or {}, default=_json_default))


def _json_default(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _stringify_output(output: Any) -> str:
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return "".join(str(part) for part in output)
    return json.dumps(output, ensure_ascii=False, default=str)
