# BeoOS controlled workflow user guide

## Start with one business problem

Create the business workspace with its identity, timezone, contact channels, and owner. Continue
progressively: approve the business profile and policies, select one operational problem, document
its trigger and exceptions, connect only the tools that workflow needs, provide reviewed examples,
set approval rules, preview the workflow, and deploy it in shadow mode.

Do not enter every process during signup. BeoOS creates a draft specification; an owner or
administrator must review it before activation.

## Choosing the first workflow

Prefer work that is frequent, measurable, easy to review, and low risk. Beo Art Studio uses
`beo_art_commission_enquiry_v1`: it normalizes website, email, WhatsApp, and manual enquiries;
looks up approved prices; identifies missing information; proposes CRM and follow-up actions; and
routes risky promises or pricing decisions to approval.

## Connections and permissions

Each connection is tenant-owned. The onboarding disclosure states what data it reads, what action
it permits, whether approval is required, and how to disconnect it. Connect only channels needed
by the selected workflow. Removing a connector stops future access but does not silently erase
audit records or legally required transaction history.

## Approval rules

Use the approval queue for discounts, custom pricing, rush commitments, refunds, angry-customer
responses, legal/privacy issues, unusual materials, international delivery, mass messages, or
external publishing. An approver can approve, edit and approve, reject, request information,
escalate, or cancel. Edits preserve the original output and record a correction reason.

Approval does not bypass tool permission. BeoOS revalidates the tenant, workflow, role,
permission, and idempotency key when execution resumes.

## Reviewing AI output

Check facts, official price evidence, missing information, policy checks, proposed action, and
customer impact. The trace page shows trigger, context sources, calculations, AI summary, tool
calls, approval, result, cost, latency, retries, and recovery without exposing private model
reasoning.

Operator answers label sources and distinguish facts, inferences, recommendations, and missing
information. Conversation history helps continuity but is not authoritative business memory.

## Corrections and datasets

A correction is not automatically “learning.” Approved edits may become dataset candidates only
after source validation, redaction, privacy review, and explicit dataset approval. One-off,
contradictory, unclear, private, or sensitive examples are rejected or quarantined.

Before deployment, run the candidate workflow output against an active dataset. Promotion requires
configured thresholds, a passing evaluation report, an approver, and a rollback version.

## Deployment modes

- `experimental`: offline/local testing only.
- `shadow`: production input, no automatic external action.
- `approval_required`: proposed actions wait for a human.
- `limited_autonomy`: evaluated reversible low-risk actions only.
- `active`: sustained evaluated performance; policies and permissions still apply.

## Outcomes and value

Record customer replies, qualification, quote creation/acceptance, deposit confirmation, won/lost
orders, response time, and loss reason. The value dashboard separates measured evidence from
onboarding estimates across revenue, cost, speed, quality, risk, and adoption.

## Recovery and payments

The Recovery page lists retryable jobs, failed tool calls, and unknown external states. Never
retry an unknown external action until the provider state is reconciled. Paystack payments become
confirmed only from a valid signed webhook or authenticated provider verification with matching
reference, amount, and currency.

## Disconnecting

Disconnect the provider in Business settings, revoke its token at the provider, and verify no
workflow still depends on that tool. Review queued jobs and pending approvals before removal.
Contact support for retention or deletion requests; transaction and security records may have
different legal retention periods.
