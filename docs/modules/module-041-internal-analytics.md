# Module 4.1: Internal Analytics and Business Intelligence

Module 4.1 turns the operational data already inside BeoOS into a tenant-scoped business intelligence dashboard.

This module does not connect external marketing analytics yet. It reads BeoOS-owned data first:

- unified inbox conversations;
- Zoho/Gmail/FormSubmit/WhatsApp message volume;
- unread and approval queue health;
- CRM leads, source, stage, and temperature;
- quotation status and quote value;
- scheduled follow-up health;
- recent cross-module activity.

## Business outcome

Every business in BeoOS can now see whether its communication engine is producing real opportunities, where leads are coming from, what is stuck in approval, and how much quotation value is open or accepted.

For Beo Art Studio, this means the dashboard can answer practical questions:

- Are WhatsApp and website form enquiries increasing?
- How many conversations are waiting for approval?
- Are new enquiries turning into CRM leads?
- Are leads turning into quotations?
- What quotation value is still open?
- Which follow-ups are due now?

## Tenant model

Analytics are scoped by `business_id` and protected by the same Clerk-backed business membership guard used by the inbox, CRM, prices, and quotations.

One user can own multiple businesses, but each business receives isolated analytics. Beo Art Studio data does not mix with AIHDStudio or any future tenant.

## Backend

New endpoint:

```text
GET /api/v1/businesses/{business_id}/analytics/summary?window_days=30
```

The response includes:

- high-level totals;
- conversion rates;
- channel/provider distribution;
- thread status distribution;
- lead source/stage/temperature buckets;
- quote status and value buckets;
- follow-up status buckets;
- recent activity links.

## Frontend

New dashboard page:

```text
/dashboard/analytics
```

The page uses cards and lightweight bar visualizations instead of a heavy charting library, keeping the dashboard fast and mobile-friendly.

## What comes next

Module 4.2 should connect external growth analytics:

- Google Search Console;
- Blogger/content performance;
- Microsoft Clarity;
- landing page/form conversion data.

Those sources should feed the same analytics experience, but Module 4.1 deliberately starts with internal operating truth first.
