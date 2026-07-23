# Rollout plan

## Deployment modes

1. Experimental: offline examples only.
2. Shadow: production events, no external action.
3. Approval required: proposed actions require an authorized human.
4. Limited autonomy: evaluated, reversible, low-risk actions only.
5. Active: narrowly bounded actions after sustained evidence and explicit approval.

## Beo Art Studio

The first workflow is commission enquiry intake. Initial activation remains approval-required.
No autonomous pricing, discounts, delivery promises, payments, refunds, or external publishing
are permitted.

Promotion requires:

- at least 50 privacy-reviewed examples;
- a completed evaluation report;
- zero unsafe pricing or prohibited-promise failures in the release evaluation;
- documented escalation recall and correction rate;
- trace and recovery verification;
- owner approval and a recorded rollback version.

## Rollback

Workflow definitions are immutable by version. Rollback changes the deployed version and mode;
it does not delete traces or evaluations. Database migrations require tested downgrade paths,
but production data migrations prefer forward repair when destructive rollback would lose records.

