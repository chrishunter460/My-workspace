# Endpoint Templates

This folder contains templates for creating new API endpoint configurations.
Files prefixed with `_` are skipped by the MarkdownConfigLoader.

## Available Templates

| Template | Use Case | Spark Reader |
|----------|----------|--------------|
| `_endpoint-json-object.md` | Flat JSON objects (one per file) | `spark.read.json()` |
| `_endpoint-json-nested-map.md` | Nested map with keys as IDs/dates | `spark.read.json()` + `explode()` |
| `_endpoint-json-array-reports.md` | Arrays of reports (annual/quarterly) | `spark.read.json()` + `explode()` |
| `_endpoint-csv.md` | CSV/TSV bulk downloads | `spark.read.csv()` |

## Spark Reader Selection

The `json_structure` field determines how Spark reads raw JSON files:

```
json_structure: object        → Direct struct access
json_structure: nested_map    → explode(map) → (key, value) rows
json_structure: array_reports → explode(array) → individual records
json_structure: array         → explode(array) → individual records
```

For CSV endpoints, use `download_method: csv` instead.

## Creating a New Endpoint

1. Copy the appropriate template
2. Remove the `_` prefix from filename
3. Place in `Data Sources/Endpoints/{Provider}/{Category}/`
4. Fill in all required fields
5. Define schema with field mappings and type coercions

## Schema Format

```yaml
schema:
  # [field_name, type, source_field, nullable, description, {options}]
  - [ticker, string, Symbol, false, "Stock ticker symbol"]
  - [price, double, Price, true, "Current price", {coerce: double}]
  - [trade_date, date, Date, false, "Trade date", {transform: "to_date(yyyy-MM-dd)"}]
  - [year, int, _computed, false, "Year", {expr: "extract(year from trade_date)"}]
```

### Source Field Special Values

| Source | Meaning |
|--------|---------|
| `FieldName` | Map from API field to output field |
| `_key` | Value comes from dict key (nested_map structure) |
| `_param` | Value comes from request parameter |
| `_computed` | Value computed via `expr` option |
| `_generated` | Value generated (e.g., constant via `default`) |
| `_na` | Field not available from this API |

### Options

| Option | Description | Example |
|--------|-------------|---------|
| `coerce` | Type coercion for source value | `{coerce: double}` |
| `transform` | String transform | `{transform: "zfill(10)"}` |
| `expr` | SQL expression for computed fields | `{expr: "(high + low) / 2"}` |
| `default` | Default value if null | `{default: "stocks"}` |
