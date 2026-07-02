---
type: hook-catalog
auto_generated: true
---

# Hook Catalog

Auto-discovered from `src/de_funk/hooks/`. Use these `fn:` paths in model.md `hooks:` config.

## Generic Hooks (\_common/)

### `de_funk.hooks._common.log_build.log_complete`
- **Trigger**: post_build
- **Domain**: any
- Log build completion with duration.

### `de_funk.hooks._common.log_build.log_start`
- **Trigger**: before_build
- **Domain**: any
- Log build start with model name and timestamp.

## Domain Hooks

### analytics/

**`de_funk.hooks.analytics.workbook.log_start`**
- Log the start of workbook build.
- Usage: `{fn: de_funk.hooks.analytics.workbook.log_start}`

**`de_funk.hooks.analytics.workbook.train_and_save`**
- Train ML model on feature set and save via ArtifactStore.
- Usage: `{fn: de_funk.hooks.analytics.workbook.train_and_save}`

### corporate/

**`de_funk.hooks.corporate.cik_enrichment.fix_company_ids`**
- Enrich fact tables with CIK-based company_id from dim_company.
- Usage: `{fn: de_funk.hooks.corporate.cik_enrichment.fix_company_ids}`

### securities/

**`de_funk.hooks.securities.forecast.train_and_save`**
- Train forecast models defined in ml_models config and save via ArtifactStore.
- Usage: `{fn: de_funk.hooks.securities.forecast.train_and_save}`

**`de_funk.hooks.securities.technicals.compute_technicals`**
- Add technical indicators to fact_stock_prices.
- Usage: `{fn: de_funk.hooks.securities.technicals.compute_technicals}`

### temporal/

**`de_funk.hooks.temporal.calendar.generate_calendar`**
- Generate dim_calendar if this is the calendar node.
- Usage: `{fn: de_funk.hooks.temporal.calendar.generate_calendar}`
