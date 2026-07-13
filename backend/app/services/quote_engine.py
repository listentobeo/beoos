from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.domain.quotes import MuralQuoteInput
from app.infrastructure.models import Business

ZERO = Decimal("0")


def calculate_quote(
    *,
    business: Business,
    template_type: str,
    input_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], Decimal, Decimal, Decimal | None]:
    if template_type == "mural":
        return calculate_mural_quote(business=business, input_data=input_data)
    catalogue_items = input_data.get("catalogue_items")
    line_items: list[dict[str, str]] = []
    catalogue_total = ZERO
    if isinstance(catalogue_items, list):
        for item in catalogue_items:
            if not isinstance(item, dict):
                continue
            quantity = money(item.get("quantity") or 1)
            unit_price = money(item.get("unit_price"))
            total = quantity * unit_price
            catalogue_total += total
            line_items.append(
                {
                    "label": str(item.get("label") or "Catalogue item"),
                    "service": str(item.get("service") or ""),
                    "quantity": str(quantity),
                    "unit_price": str(round_money(unit_price)),
                    "total": str(round_money(total)),
                }
            )
    subtotal = money(input_data.get("subtotal")) or catalogue_total
    total = money(input_data.get("total") or subtotal)
    calculation = {
        "subtotal": str(round_money(subtotal)),
        "total": str(round_money(total)),
        "line_items": line_items,
    }
    proposal = {
        "summary": input_data.get("summary") or "Custom service quote.",
        "client_terms": input_data.get("client_terms") or "",
    }
    return calculation, proposal, subtotal, total, None


def default_mural_input(seed: dict[str, Any] | None = None) -> dict[str, Any]:
    data = {
        "client_name": "Client Name",
        "organization": "",
        "phone": "",
        "email": "",
        "address": "",
        "project_title": "Mural Project",
        "project_type": "school",
        "project_location": "",
        "deadline": "",
        "dimensions": {"width": "16", "height": "7", "unit": "ft"},
        "surface_type": "Smooth",
        "surface_condition": "Good",
        "access": "Ground Level",
        "environment": "Indoor",
        "problem": "The space needs a stronger visual identity and a more engaging environment.",
        "objectives": (
            "Beautify the environment, improve engagement, and communicate the client's "
            "values visually."
        ),
        "solution": (
            "A custom mural aligned with the client's goals, audience, location, and "
            "long-term use of the space."
        ),
        "success_criteria": (
            "The mural is completed on schedule, reflects the approved concept, and "
            "improves the visual experience of the space."
        ),
        "design_costs": {
            "Concept Creation": "40000",
            "Mood Board": "15000",
            "Mockups": "35000",
            "Presentation Boards": "15000",
            "Client Meetings": "20000",
            "Site Survey": "20000",
            "Revisions": "15000",
        },
        "labor": [
            {"role": "Lead Artist", "hours": "40", "rate": "6000"},
            {"role": "Assistant Artist", "hours": "24", "rate": "3000"},
            {"role": "Designer", "hours": "10", "rate": "5000"},
            {"role": "Project Manager", "hours": "8", "rate": "5000"},
        ],
        "materials": {
            "Paint": "120000",
            "Primer": "25000",
            "Sealer": "30000",
            "Brushes": "15000",
            "Rollers": "12000",
            "Masking Tape": "8000",
            "Protective Coverings": "10000",
            "Cleaning Materials": "6000",
            "Consumables": "8000",
            "Miscellaneous": "10000",
        },
        "equipment": {
            "Generator": "25000",
            "Projector": "15000",
            "Safety Equipment": "15000",
            "Extension Cables": "5000",
        },
        "transport": {
            "Fuel": "30000",
            "Logistics": "15000",
        },
        "project_management_percent": "10",
        "overhead_percent": "10",
        "risk_percent": "7.5",
        "profit_percent": "30",
        "payment_terms": "70% mobilization, 30% before final handover.",
        "timeline": "Design and production timeline to be agreed after approval.",
        "assumptions": (
            "Client provides access to the wall, timely feedback, and approval before "
            "production begins. Wall repairs outside minor preparation are not included "
            "unless stated."
        ),
        "exclusions": (
            "Major civil works, structural repairs, electrical work, permits, security, "
            "and additional revisions beyond the agreed scope are excluded unless agreed "
            "in writing."
        ),
        "warranty": (
            "Touch-up support for workmanship issues within 30 days of handover, excluding "
            "damage caused by water leakage, structural defects, vandalism, or third-party "
            "interference."
        ),
    }
    if seed:
        data.update({key: value for key, value in seed.items() if value not in (None, "")})
    return data


def calculate_mural_quote(
    *,
    business: Business,
    input_data: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], Decimal, Decimal, Decimal | None]:
    parsed = MuralQuoteInput.model_validate(default_mural_input(input_data))
    width = money(parsed.dimensions.width)
    height = money(parsed.dimensions.height)
    area = width * height
    sqft = area * Decimal("10.7639") if parsed.dimensions.unit == "m" else area
    sqm = area if parsed.dimensions.unit == "m" else area * Decimal("0.092903")

    design_total = sum_money(parsed.design_costs)
    labor_rows = []
    labor_total = ZERO
    for row in parsed.labor:
        role = str(row.get("role") or "Labor")
        hours = money(row.get("hours"))
        rate = money(row.get("rate"))
        total = hours * rate
        labor_total += total
        labor_rows.append(
            {"role": role, "hours": str(hours), "rate": str(rate), "total": str(round_money(total))}
        )
    materials_total = sum_money(parsed.materials)
    equipment_total = sum_money(parsed.equipment)
    transport_total = sum_money(parsed.transport)
    direct = design_total + labor_total + materials_total + equipment_total + transport_total
    pm = percent(direct, parsed.project_management_percent)
    overhead = percent(direct, parsed.overhead_percent)
    risk_base = direct + pm + overhead
    risk = percent(risk_base, parsed.risk_percent)
    subtotal = direct + pm + overhead + risk
    profit = percent(subtotal, parsed.profit_percent)
    total = subtotal + profit
    deposit = percent(total, Decimal("70"))

    calculation = {
        "area": {"sqft": str(round_money(sqft)), "sqm": str(round_money(sqm))},
        "design": str(round_money(design_total)),
        "labor": str(round_money(labor_total)),
        "labor_rows": labor_rows,
        "materials": str(round_money(materials_total)),
        "equipment": str(round_money(equipment_total)),
        "transport": str(round_money(transport_total)),
        "direct_costs": str(round_money(direct)),
        "project_management": str(round_money(pm)),
        "overhead": str(round_money(overhead)),
        "risk": str(round_money(risk)),
        "project_cost": str(round_money(subtotal)),
        "profit": str(round_money(profit)),
        "total": str(round_money(total)),
        "deposit_required": str(round_money(deposit)),
        "currency": "NGN",
    }
    proposal = {
        "prepared_by": business.name,
        "client_name": parsed.client_name,
        "organization": parsed.organization,
        "project_title": parsed.project_title,
        "project_type": parsed.project_type,
        "project_location": parsed.project_location,
        "deadline": parsed.deadline or "To be agreed",
        "summary": parsed.solution,
        "problem": parsed.problem,
        "objectives": parsed.objectives,
        "scope": (
            f"{business.name} will design and execute a custom {parsed.project_type} "
            f"mural at {parsed.project_location or 'the project site'}."
        ),
        "site_assessment": {
            "surface": f"{parsed.surface_type}, {parsed.surface_condition}",
            "access": parsed.access,
            "environment": parsed.environment,
            "area": calculation["area"],
        },
        "timeline": parsed.timeline,
        "payment_terms": parsed.payment_terms,
        "assumptions": parsed.assumptions,
        "exclusions": parsed.exclusions,
        "warranty": parsed.warranty,
    }
    return (
        calculation,
        proposal,
        round_money(subtotal),
        round_money(total),
        round_money(deposit),
    )


def sum_money(values: dict[str, Decimal] | dict[str, Any]) -> Decimal:
    return sum((money(value) for value in values.values()), ZERO)


def percent(value: Decimal, rate: Decimal) -> Decimal:
    return value * (money(rate) / Decimal("100"))


def money(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value or "0"))
    except Exception:
        return ZERO


def round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
