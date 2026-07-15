# Module 3.8: Quote Template Designer and Flexible Line Items

Module 3.8 upgrades BeoOS quotations from a single strong mural calculator into a tenant quote system that can support many business types.

The original Beo Art Studio mural standard remains intact. The new layer adds reusable quote templates and flexible line-item pricing for other services, product bundles, bulk purchases, retainers, and inventory-backed offers.

## What this module adds

- Tenant quote templates.
- Flexible quote creation from line items.
- Template defaults for:
  - proposal summary;
  - scope;
  - payment terms;
  - timeline;
  - assumptions;
  - exclusions;
  - warranty/support note;
  - deposit percentage;
  - accent color/layout metadata.
- Custom quote calculations for:
  - quantity;
  - unit price;
  - discounts;
  - tax/VAT;
  - deposit amount.
- Quote deletion for test/duplicate quotes.

## Tenant model

Every quote template belongs to one `business_id`.

This means Beo Art Studio can keep mural-specific standards, while another tenant can create templates for:

- bulk product purchases;
- art supplies orders;
- consulting packages;
- installation jobs;
- maintenance retainers;
- school/training packages;
- any brick-and-mortar service quotation.

## Current frontend behavior

The Quotations page now contains:

1. A flexible quote creator.
2. A quote template manager.
3. The existing quote list and quote detail flow.

The detail page now displays itemized line items for custom quotes.

## What remains for the next quotation iteration

Module 3.9 should add:

- richer PDF export;
- tenant logo upload;
- quote layout/theme picker;
- drag-and-drop line items;
- catalogue item picker from the price catalogue;
- AI quote assistant that can create or update quotes from natural language;
- client-facing template styling on public quote pages.

This module stores the structure needed for those upgrades without forcing every quote into the Beo Art Studio mural format.
