# Module 3.6: AI Lead Scoring and Editable Quotes

Module 3.6 tightens the sales loop.

## What this adds

- AI-assisted lead scoring from existing message analysis.
- Hot / warm / cold lead temperature.
- Lead score from 0–100.
- Qualification summary and reasons.
- CRM cards show score and temperature.
- Quote creation moves linked leads to `quoted`.
- Public proposal acceptance moves linked leads to `deposit_pending`.
- Quote detail page includes basic editable mural inputs:
  - width;
  - height;
  - project location;
  - deadline;
  - payment terms.

## How scoring works

The AI provider, currently Replicate when configured, extracts service, budget, deadline, phone, urgency, and buying intent. BeoOS then applies deterministic scoring on top of that analysis so lead qualification is consistent and auditable.

## Why this matters

BeoOS can now help decide which leads deserve attention first instead of treating every message equally.
