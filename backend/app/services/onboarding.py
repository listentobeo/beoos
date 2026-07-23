from dataclasses import dataclass
from typing import Any

from app.domain.onboarding import OnboardingQuestion


@dataclass(frozen=True)
class Question:
    key: str
    stage: int
    prompt: str
    response_type: str = "text"
    required: bool = True
    help_text: str = ""
    options: tuple[str, ...] = ()

    def view(self) -> OnboardingQuestion:
        return OnboardingQuestion(
            key=self.key,
            stage=self.stage,
            prompt=self.prompt,
            response_type=self.response_type,
            required=self.required,
            help_text=self.help_text,
            options=list(self.options),
        )


QUESTIONS = (
    Question("workspace.business_name", 1, "What is the business name?"),
    Question("workspace.industry", 1, "Which industry best describes the business?"),
    Question("workspace.timezone", 1, "What timezone does the business operate in?"),
    Question(
        "workspace.main_contact_channel",
        1,
        "What is the main customer contact channel?",
        "choice",
        options=("email", "whatsapp", "website_form", "phone", "other"),
    ),
    Question("workspace.website", 1, "What is the business website?", required=False),
    Question("workspace.owner_role", 1, "What is your role in the business?"),
    Question("profile.offer", 2, "What does the business sell?"),
    Question("profile.services", 2, "List the main services or products.", "list"),
    Question("profile.customers", 2, "Who are the typical customers?", "list"),
    Question("profile.locations", 2, "Where does the business operate?", "list"),
    Question("profile.hours", 2, "What are the business hours?", "object"),
    Question("profile.channels", 2, "Which communication channels are used?", "list"),
    Question("profile.pricing_source", 2, "Where does approved pricing come from?"),
    Question("profile.brand_voice", 2, "Describe the approved brand voice."),
    Question(
        "profile.prohibited_claims",
        2,
        "What must the business never claim or promise?",
        "list",
    ),
    Question(
        "problem.first",
        3,
        "Which business problem should BeoOS address first?",
        "choice",
        options=(
            "handle_customer_enquiries",
            "qualify_leads",
            "create_quotations",
            "schedule_follow_ups",
            "customer_support",
            "marketing_opportunities",
            "another_workflow",
        ),
        help_text="Enquiry intake is recommended for service businesses.",
    ),
    Question("workflow.arrival_channels", 4, "Where do enquiries arrive?", "list"),
    Question("workflow.trigger", 4, "What starts the workflow?"),
    Question("workflow.required_information", 4, "What information must be collected?", "list"),
    Question("workflow.missing_information", 4, "What information is usually missing?", "list"),
    Question("workflow.qualified", 4, "What makes a lead qualified?"),
    Question("workflow.low_priority", 4, "What makes a lead low priority?"),
    Question("workflow.immediate_quote", 4, "Which services can be quoted immediately?", "list"),
    Question("workflow.never_promise", 4, "What must never be promised?", "list"),
    Question("workflow.approval_situations", 4, "Which situations require approval?", "list"),
    Question("workflow.exceptions", 4, "What common exceptions occur?", "list"),
    Question("workflow.after_qualified", 4, "What happens after a qualified enquiry?"),
    Question("workflow.after_unqualified", 4, "What happens after an unqualified enquiry?"),
    Question("workflow.escalations", 4, "Who handles escalations?"),
    Question("workflow.response_time", 4, "How quickly should the business respond?"),
    Question("workflow.success", 4, "What outcome defines success?"),
    Question("workflow.costly_mistakes", 4, "Which mistakes are costly?", "list"),
    Question("workflow.never_automate", 4, "What should never be automated?", "list"),
    Question(
        "connections.required",
        5,
        "Select only the connectors required for this workflow.",
        "list",
        options=("gmail", "zoho", "whatsapp", "website_forms", "search_console", "paystack"),
        help_text=(
            "Each connector will show data access, actions, approvals, and disconnect controls."
        ),
    ),
    Question(
        "examples.cases",
        6,
        "Provide 3–10 good, bad, difficult, escalation, or incomplete examples.",
        "examples",
    ),
    Question("approval.actions", 7, "Which actions require approval?", "list"),
    Question("approval.approvers", 7, "Who can approve?", "list"),
    Question("approval.financial_thresholds", 7, "What financial thresholds apply?", "object"),
    Question("approval.confidence_thresholds", 7, "What confidence thresholds apply?", "object"),
    Question("approval.review_categories", 7, "Which categories must always be reviewed?", "list"),
    Question("approval.expiry", 7, "When should an approval request expire?"),
    Question("approval.fallback", 7, "What happens if nobody responds?"),
    Question(
        "preview.confirm",
        8,
        "Confirm that the draft specification is ready for controlled testing.",
        "choice",
        options=("confirmed", "needs_changes"),
    ),
)

QUESTION_BY_KEY = {question.key: question for question in QUESTIONS}

CONNECTOR_DISCLOSURES: dict[str, dict[str, Any]] = {
    "gmail": {
        "data_accessed": ["inbound messages", "thread metadata", "recipient addresses"],
        "actions_permitted": ["read selected mailbox", "create draft"],
        "approval_required": ["send email"],
        "disconnect": "Remove the Gmail connection from Settings > Connections.",
        "problems": ["handle_customer_enquiries", "qualify_leads", "customer_support"],
    },
    "zoho": {
        "data_accessed": ["inbound messages", "thread metadata", "recipient addresses"],
        "actions_permitted": ["read selected mailbox", "create draft"],
        "approval_required": ["send email"],
        "disconnect": "Remove the Zoho connection from Settings > Connections.",
        "problems": ["handle_customer_enquiries", "qualify_leads", "customer_support"],
    },
    "whatsapp": {
        "data_accessed": ["messages sent to the connected business number", "contact phone"],
        "actions_permitted": ["read inbound messages", "create reply draft"],
        "approval_required": ["send WhatsApp reply"],
        "disconnect": "Disconnect the tenant WhatsApp account from Settings > WhatsApp.",
        "problems": ["handle_customer_enquiries", "qualify_leads", "customer_support"],
    },
    "website_forms": {
        "data_accessed": ["submitted form fields and consent metadata"],
        "actions_permitted": ["receive and classify submissions"],
        "approval_required": ["outbound response"],
        "disconnect": "Rotate or remove the website form endpoint configuration.",
        "problems": ["handle_customer_enquiries", "qualify_leads"],
    },
    "search_console": {
        "data_accessed": ["search queries", "pages", "clicks", "impressions"],
        "actions_permitted": ["read performance metrics"],
        "approval_required": ["publishing or editing content"],
        "disconnect": "Revoke Search Console access in Settings > Connections.",
        "problems": ["marketing_opportunities"],
    },
    "paystack": {
        "data_accessed": ["approved quote amount", "payment reference and status"],
        "actions_permitted": ["propose a payment-link request"],
        "approval_required": ["create payment link", "any refund"],
        "disconnect": "Remove the tenant Paystack connection from Settings > Connections.",
        "problems": ["create_quotations"],
    },
}


def connector_disclosures(selected_problem: str | None) -> dict[str, dict[str, Any]]:
    problem = selected_problem or "handle_customer_enquiries"
    return {
        key: value
        for key, value in CONNECTOR_DISCLOSURES.items()
        if problem in value["problems"]
    }


def applicable_questions(selected_problem: str | None) -> list[Question]:
    # The first reference interview is enquiry-focused. Other choices retain the common
    # stages and produce a draft requiring a later workflow-specific interview extension.
    if selected_problem in (None, "handle_customer_enquiries", "qualify_leads"):
        return list(QUESTIONS)
    return [item for item in QUESTIONS if item.stage != 4]


def next_question(
    answered_keys: set[str], selected_problem: str | None
) -> Question | None:
    for question in applicable_questions(selected_problem):
        if question.key not in answered_keys:
            return question
    return None


def completion(answered_keys: set[str], selected_problem: str | None) -> int:
    questions = applicable_questions(selected_problem)
    required = [item for item in questions if item.required]
    answered = sum(item.key in answered_keys for item in required)
    return min(100, round(answered * 100 / max(1, len(required))))


def build_draft_specification(answers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    problem = _scalar(answers.get("problem.first")) or "handle_customer_enquiries"
    return {
        "status": "draft_requires_owner_review",
        "profile": {
            "display_name": _scalar(answers.get("workspace.business_name")),
            "industry": _scalar(answers.get("workspace.industry")),
            "timezone": _scalar(answers.get("workspace.timezone")),
            "website": _scalar(answers.get("workspace.website")),
            "description": _scalar(answers.get("profile.offer")),
            "customer_types": _value(answers.get("profile.customers")),
            "locations": _value(answers.get("profile.locations")),
            "opening_hours": _value(answers.get("profile.hours")),
            "contact_channels": _value(answers.get("profile.channels")),
        },
        "services": _value(answers.get("profile.services")),
        "policies": {
            "brand_voice": _value(answers.get("profile.brand_voice")),
            "prohibited_claims": _value(answers.get("profile.prohibited_claims")),
            "never_promise": _value(answers.get("workflow.never_promise")),
            "never_automate": _value(answers.get("workflow.never_automate")),
        },
        "workflow": {
            "key": f"{problem}_v1",
            "objective": problem,
            "trigger_channels": _value(answers.get("workflow.arrival_channels")),
            "required_information": _value(answers.get("workflow.required_information")),
            "qualification": _value(answers.get("workflow.qualified")),
            "success_outcome": _value(answers.get("workflow.success")),
        },
        "tool_permission_proposal": {
            "connectors": _value(answers.get("connections.required")),
            "mode": "propose_only",
        },
        "approval_policy": {
            "actions": _value(answers.get("approval.actions")),
            "approvers": _value(answers.get("approval.approvers")),
            "financial_thresholds": _value(answers.get("approval.financial_thresholds")),
            "confidence_thresholds": _value(answers.get("approval.confidence_thresholds")),
            "expiry": _value(answers.get("approval.expiry")),
            "fallback": _value(answers.get("approval.fallback")),
        },
        "dataset_candidates": _value(answers.get("examples.cases")),
        "baseline_metrics": {"status": "pending_preview_evaluation"},
        "deployment_mode": "experimental",
        "prompt_generation": "prohibited_from_unreviewed_answers",
    }


def _value(answer: dict[str, Any] | None) -> Any:
    return answer.get("value") if answer else None


def _scalar(answer: dict[str, Any] | None) -> Any:
    value = _value(answer)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return value
