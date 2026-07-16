# Module 4.2: Marketing Intelligence Layer

Module 4.2 turns external growth signals into precise marketing actions per business tenant.

This module is deliberately not a blind auto-blogger. It first answers:

- what pages already get attention;
- what queries have impressions but weak clicks;
- what topics deserve content clusters;
- what pages need better conversion paths;
- what the marketer should fix, refresh, or create next.

## Business outcome

Each BeoOS tenant can connect or import growth data and receive a practical marketing command center.

For Beo Art Studio, this means BeoOS can separate authority service pages from educational blog posts:

- service pages remain the source of truth for offers and pricing;
- blog posts support discovery and education;
- Search Console shows what people are asking;
- Microsoft Clarity explains where visitors hesitate or drop off;
- Blogger/content metrics show which educational posts deserve updates or internal links.

## Current production slice

The first build supports manual/API-style imports into:

```text
POST /api/v1/businesses/{business_id}/marketing/import
GET  /api/v1/businesses/{business_id}/marketing/summary?window_days=90
```

Accepted import sources:

- `search_console`
- `blogger`
- `clarity`
- `website`
- `manual`

Accepted row fields:

```json
{
  "page_url": "https://example.com/service-page",
  "query": "portrait painting price in lagos",
  "title": "Portrait Pricing",
  "impressions": 240,
  "clicks": 6,
  "ctr": 0.025,
  "average_position": 9.4,
  "sessions": 120,
  "leads": 3,
  "engagement_rate": 0.44,
  "scroll_depth": 0.61,
  "avg_time_seconds": 72
}
```

The dashboard page is:

```text
/dashboard/marketing
```

It shows:

- imported signal totals;
- priority action items;
- search query opportunities;
- content clusters;
- page opportunities;
- a JSON import panel for early testing and future connector payloads.

## Tenant model

Every marketing metric is scoped by `business_id`.

One user can run multiple businesses inside BeoOS, but Beo Art Studio data does not mix with AIHDStudio or any future tenant.

## API connector roadmap

The current model is ready for official connectors. The connector layer should populate the same `marketing_metrics` table instead of creating separate dashboards.

Planned connectors:

### Google Search Console

Used for:

- top queries;
- impressions;
- clicks;
- CTR;
- average position;
- page URL performance.

Future env:

```env
GOOGLE_SEARCH_CONSOLE_CLIENT_ID=
GOOGLE_SEARCH_CONSOLE_CLIENT_SECRET=
```

### Blogger

Used for:

- post titles;
- post URLs;
- publish/update recency;
- imported view/performance data where available;
- mapping educational posts to service-page clusters.

Future env:

```env
GOOGLE_BLOGGER_CLIENT_ID=
GOOGLE_BLOGGER_CLIENT_SECRET=
```

### Microsoft Clarity

Used for:

- page sessions;
- engagement/friction signals;
- scroll depth;
- rage click/dead click signals when available;
- conversion friction recommendations.

Future env:

```env
MICROSOFT_CLARITY_PROJECT_ID=
MICROSOFT_CLARITY_API_TOKEN=
```

## What this module should not do yet

Do not auto-publish to Blogger until:

- brand bible is approved;
- source data is clean;
- pricing/catalogue and service pages are authoritative;
- review workflow is active;
- content risk rules are defined per tenant.

The correct next step after this module is an AI-assisted content brief generator, not direct publishing.
