# Account Meter Billing

[![Odoo](https://img.shields.io/badge/Odoo-19.0-714b67?logo=odoo)](https://www.odoo.com)
[![License](https://img.shields.io/badge/license-LGPL--3-blue)](__manifest__.py)

Adds meter-reading columns (Previous, New, Actual) to invoice lines and
automatically maps the computed consumption to the standard Quantity field.
Designed for utility, water, electricity, or gas billing workflows where
charges are based on meter differential rather than discrete units.

## Table of Contents

- [Overview](#4-overview)
- [Quick Start](#5-quick-start)
- [Architecture & Design Decisions](#6-architecture--design-decisions)
- [Complete Processing Flow](#7-complete-processing-flow)
- [API Reference](#8-api-reference)
- [Model / Audit Log](#9-model--audit-log)
- [Error Scenarios & Recovery](#10-error-scenarios--recovery)
- [Configuration](#11-configuration)
- [Sandbox Testing](#12-sandbox-testing)
- [Security](#13-security)
- [Dependencies](#14-dependencies)
- [Installation](#15-installation)
- [Performance Characteristics](#16-performance-characteristics)
- [Development & Testing](#17-development--testing)
- [Troubleshooting](#18-troubleshooting)
- [License](#19-license)

## Overview

| Capability | How it works |
|---|---|---|
| Historical meter lookup | `meter_previous` searches last posted invoice for same partner+product |
| Current reading entry | `meter_new` is an editable float stored on the invoice line |
| Automatic consumption | `meter_actual` = new - previous, floored at 0 |
| Quantity sync | `meter_actual` written to `quantity` so subtotals reflect usage |
| PDF report columns | Previous, New, Actual columns render before Quantity in invoice PDF |

This module is for businesses that bill based on meter readings -- utility
companies, property managers, co-working spaces, or any recurring service
where consumption is measured at interval endpoints. The module does **not**
add an independent meter registry; it treats each invoice line as a snapshot
in a chain of readings for that partner-product pair.

## Quick Start

1. **Install the module** -- Apps > Update Apps List > Install "Account Meter
   Billing".
2. **Create a customer invoice** -- Accounting > Customers > Invoices > Create.
3. **Add an invoice line** -- pick a product that represents a metered service
   (e.g., "Water - per m3").
4. **Enter the New reading** -- type a value in the `New` column. The
   `Previous` and `Actual` fields update automatically.
5. **Post the invoice** -- the reading is saved. On the next invoice for the
   same partner and product, `Previous` populates from this invoice's `New`.

## Architecture & Design Decisions

### Why store computed fields instead of computing on the fly

`meter_previous` and `meter_actual` are both `compute=True, store=True`.
Storing means the values survive recomputation and are available in SQL
reports, search domains, and the PDF renderer without re-running the search
query every time. The tradeoff is slightly higher database storage -- three
extra floats per invoice line -- which is negligible for the vast majority of
Odoo deployments.

### Why map `meter_actual` to `quantity` inside the compute method

```python
@api.depends('meter_new', 'meter_previous')
def _compute_meter_actual(self):
    for line in self:
        actual = max(line.meter_new - line.meter_previous, 0.0)
        line.meter_actual = actual
        line.quantity = actual
```

Writing `line.quantity = actual` inside the `_compute_meter_actual` method
means that every price, tax, and subtotal computation works automatically --
no need to override `_compute_price` or modify the `account.move` validation
logic. The quantity is the actual consumption, so the line total becomes
`actual * unit_price`. This is the least-surprise path for Odoo's existing
accounting pipeline.

### Why exclude the current line from the historical lookup

```python
if line.id:
    domain.append(('id', '!=', line.id))
```

When editing an already-saved invoice line, the search for the last posted
reading would otherwise find the line itself (because it has `meter_new > 0`),
producing a self-referencing previous value. The `id !=` exclusion prevents
this cycle.

### Why filter by `move_type` in the lookup domain

```python
if line.move_id.move_type:
    domain.append(('move_id.move_type', '=', line.move_id.move_type))
```

A partner may receive both customer invoices (`out_invoice`) and vendor bills
(`in_invoice`). Restricting the search to the same `move_type` prevents a
vendor bill reading from leaking into a customer invoice's `Previous` field.

## Complete Processing Flow

### Flow A -- Invoice line creation / editing

```
User selects product and partner
  │
  ├── _compute_meter_previous fires
  │     ├── domain: same partner, same product, posted, same move_type
  │     ├── order by invoice_date desc, id desc
  │     ├── limit 1
  │     └── meter_previous = result.meter_new or 0.0
  │
  ├── User enters meter_new value
  │     └── _compute_meter_actual fires
  │           ├── meter_actual = max(meter_new - meter_previous, 0.0)
  │           └── quantity = meter_actual
  │
  └── Invoice posted
        └── move_id.state -> 'posted'
              └── This line becomes the "previous" source
                    for the next identical partner+product invoice
```

Steps:

1. User opens a new invoice or edits an existing draft.
2. Adding an invoice line triggers `_compute_meter_previous` via the
   `product_id` and `move_id.partner_id` dependencies.
3. `_compute_meter_previous` searches `account.move.line` for the most recent
   posted invoice line with the same partner, product, and `move_type` that
   has `meter_new > 0`.
4. The found line's `meter_new` is copied to the current line's
   `meter_previous`. If no prior line exists, `meter_previous` is 0.
5. User types a value into `meter_new`.
6. `_compute_meter_actual` runs: `actual = max(new - previous, 0)`. Both
   `meter_actual` and `quantity` are set to this value.
7. Subtotal, tax, and total are recomputed by the standard `account.move`
   pipeline using the updated `quantity`.

### Flow B -- PDF report rendering

```
Invoice print action
  │
  └── account.report_invoice_document rendered
        ├── th line: "Previous" | "New" | "Actual" | "Quantity"
        └── td line: line.meter_previous | line.meter_new
                     | line.meter_actual | line.quantity
```

Steps:

1. User clicks Print > Invoice on a posted invoice.
2. Odoo renders the QWeb template `account.report_invoice_document`.
3. The two xpath insertions add three `<th>` elements before `th_quantity` and
   three `<td>` elements before `td_quantity`.
4. Each cell is populated via `t-field` on the `line` record.

## API Reference

Not applicable. This module has **no HTTP controllers**, no REST endpoints,
and no webhook listeners. All behavior is triggered through Odoo's standard
model layer (field computes, view inheritance, QWeb template inheritance).

Integrators interact with the module entirely through Odoo's ORM and UI --
either via the web client or through `models.env` in server-side code.

## Model / Audit Log

### `account.move.line` (inherited)

| Field | Type | Purpose |
|---|---|---|
| `meter_previous` | `Float` (computed, stored) | Last reading from prior posted invoice, same partner+product |
| `meter_new` | `Float` (editable, stored) | Reading entered for the current billing cycle |
| `meter_actual` | `Float` (computed, stored) | Net consumption = new - previous, floored at 0 |

**Key methods:**

| Method | Signature | Description |
|---|---|---|
| `_compute_meter_previous` | `(self)` | Finds latest posted `meter_new` for same partner, product, move_type |
| `_compute_meter_actual` | `(self)` | Sets `meter_actual` and `quantity` to `max(new - previous, 0)` |

**Constraints:** None. The module does not add any SQL or Python constraints.

## Error Scenarios & Recovery

| Scenario | What happens | Recovery |
|---|---|---|
| No prior invoice exists | `meter_previous` = 0.0; `meter_actual` = `meter_new` | Correct -- first invoice has no prior |
| `meter_new` < `meter_previous` | `meter_actual` = 0.0 (negative floored) | Verify reading. Zero via prior invoice if meter was reset |
| Prior invoice in draft | `meter_previous` = 0.0 (needs `state=posted`) | Post prior invoice, re-save current line |
| Same product, diff move_type | `move_type` filter prevents vendor bills leaking into customer invoices | No action needed |
| Invoice line deleted after posting | Deleted line unavailable as prior source | Keep one posted invoice with `meter_new > 0` |

## Configuration

**No model-based configuration or system parameters are required.**

The module has zero configuration options. All behavior is governed by the
field compute logic described in the Model section. There are no
`res.config.settings` entries, no `ir.config_parameter` keys, and no
environment variables.

## Sandbox Testing

Not applicable. The module contains no sandbox, mock server, or external
service simulator. All logic runs entirely within the Odoo ORM layer.

## Security

| Layer | Mechanism |
|---|---|---|
| Field access | Standard Odoo ACLs apply. No custom rules. Fields visible to users with `account.move.line` access |
| Data isolation | `meter_previous` search respects the same record rules as `account.move.line` |

**Production consideration:** No additional hardening is needed. The module
inherits the existing `account` module's security posture.

## Dependencies

| Module | Purpose |
|---|---|
| `account` | Provides the `account.move.line` model and invoice views that this module extends |

No external Python packages are required.

## Installation

```
account_meter_billing/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── account_move_line.py
└── views/
    ├── account_move_views.xml
    └── report_invoice.xml
```

**Install via Odoo Apps:**

```bash
# Copy module to addons directory
cp -r account_meter_billing /path/to/odoo/addons/

# Update app list (Odoo CLI)
./odoo-bin -d <database> -u account_meter_billing --addons-path /path/to/addons

# Or via the UI
# 1. Activate Developer Mode (Settings > Activate Developer Mode)
# 2. Apps > Update Apps List
# 3. Search "Account Meter Billing" > Install
```

## Performance Characteristics

| Metric | Typical Value |
|---|---|
| Extra storage per invoice line | 3 x `Float` (24 bytes each, plus ORM overhead) |
| `_compute_meter_previous` latency | < 5ms per line (single indexed search with `limit=1`) |
| `_compute_meter_actual` latency | < 1ms per line (pure arithmetic, no I/O) |
| Bulk invoice creation | Each line triggers one search query; no batching optimization |

**Bottlenecks:** The `_compute_meter_previous` method issues one `search()`
call per invoice line. For import scripts creating thousands of lines at once,
this can add up. Future optimization could batch the lookup in a single query.

## Development & Testing

```bash
# Run module tests (if tests/ directory exists)
./odoo-bin -d <database> --test-tags account_meter_billing --stop-after-init
```

| File | Coverage | Notes |
|---|---|---|
| `tests/` | Not present | No test files shipped with this version |

**Known limitations:**

- No automated test suite is included.
- The `meter_previous` field does not retroactively update when an older
  invoice is posted after a newer one already exists. Create invoices in
  chronological order.
- Negative consumption (`meter_new < meter_previous`) is silently floored to
  zero rather than raising a warning.

## Troubleshooting

| Symptom | Likely Cause | Solution |
|---|---|---|
| `meter_previous` stays 0 | No prior posted invoice for this partner+product | Post prior invoice, re-save current line |
| `meter_actual` is 0 unexpectedly | `meter_new` <= `meter_previous` | Verify reading. Create zeroing invoice with prior `meter_new` if reset |
| `Quantity` shows wrong value | Compute overwrites manual `quantity` edits | Edit `meter_new` instead |
| PDF columns missing | Another module modifies same report template | Check `ir.ui.view` inheritance order in debug mode |

## License

LGPL-3. See `__manifest__.py` for details.
