/**
 * Parse de_funk YAML blocks into validated API request payloads.
 * Translates the block's data/formatting/config into the wire format
 * the backend expects.
 */
import * as yaml from "js-yaml";
import type { DeFunkBlock, BlockData, FilterSpec, MeasureTuple, ColumnTuple } from "./contract";

/** Parse a de_funk code block string into a DeFunkBlock. */
export function parseBlock(source: string): DeFunkBlock {
  const parsed = yaml.load(source) as Record<string, unknown>;
  if (!parsed || typeof parsed !== "object") {
    throw new Error("de_funk block must be valid YAML");
  }
  if (!parsed["type"]) {
    throw new Error("de_funk block requires a 'type:' field");
  }
  return {
    type: parsed["type"] as string,
    layer: (parsed["layer"] as DeFunkBlock["layer"]) ?? "silver",
    data: (parsed["data"] as BlockData) ?? {},
    formatting: (parsed["formatting"] as DeFunkBlock["formatting"]) ?? {},
    config: (parsed["config"] as DeFunkBlock["config"]) ?? {},
  };
}

/** Build the API request payload from a parsed block + note-level state. */
export function buildRequest(
  block: DeFunkBlock,
  noteFilters: FilterSpec[],
  controlState: Record<string, unknown>,
): Record<string, unknown> {
  const { type, data, config } = block;

  // Resolve active filters — apply page_filter ignore rules
  const ignoreList = config?.page_filters?.ignore ?? [];
  const ignoreAll = ignoreList.includes("*");
  const activeNoteFilters = ignoreAll
    ? []
    : noteFilters.filter((f) => {
        const filterKey = f.field.split(".").pop() ?? f.field;
        return !ignoreList.includes(filterKey);
      });

  // Exhibit-level filters
  const exhibitFilters: FilterSpec[] = [];
  for (const [field, value] of Object.entries(config?.filters ?? {})) {
    const v = value as unknown;
    if (Array.isArray(v)) {
      exhibitFilters.push({ field, operator: "in", value: v });
    } else if (typeof v === "object" && v !== null) {
      exhibitFilters.push({ field, operator: "between", value: v as Record<string, unknown> });
    }
  }

  // Inline data-level filters (from YAML data.filters array)
  const inlineFilters: FilterSpec[] = [];
  if (Array.isArray(data.filters)) {
    for (const f of data.filters as Record<string, unknown>[]) {
      if (f && typeof f === "object" && f["field"]) {
        inlineFilters.push({
          field: f["field"] as string,
          operator: (f["operator"] ?? f["op"] ?? "eq") as FilterSpec["operator"],
          value: f["value"] as FilterSpec["value"],
        });
      }
    }
  }

  const allFilters = [...activeNoteFilters, ...exhibitFilters, ...inlineFilters];

  // Apply control state overrides to data fields
  const resolvedData = applyControlState(data, controlState);

  const payload: Record<string, unknown> = {
    type,
    ...resolvedData,
    filters: allFilters,
  };

  // Normalize cols: empty array → null (API accepts string, list, or null)
  if (Array.isArray(payload["cols"])) {
    const arr = payload["cols"] as unknown[];
    if (arr.length === 0) payload["cols"] = null;
  }

  // Normalize measures/metrics/columns from tuple arrays
  if (payload["measures"]) {
    payload["measures"] = normalizeTuples(payload["measures"] as unknown[]);
  }
  if (payload["metrics"]) {
    payload["metrics"] = normalizeTuples(payload["metrics"] as unknown[]);
  }
  if (payload["columns"]) {
    payload["columns"] = normalizeColumnTuples(payload["columns"] as unknown[]);
  }
  if (payload["windows"]) {
    payload["windows"] = normalizeWindowTuples(payload["windows"] as unknown[]);
  }

  return payload;
}

/** Infer a display format from a field name. */
const DOLLAR_FIELDS = new Set(["amount", "revenue", "revenue_ttm", "eps", "price", "market_cap",
  "total_paid", "total_appropriated", "budget_variance", "transaction_amount"]);

function inferFormat(field: string): string | null {
  const col = field.split(".").pop() ?? "";
  if (DOLLAR_FIELDS.has(col)) return "$";
  return null;
}

/** Normalize a control value to a flat string or string[]. */
function asStringArray(v: unknown): string[] {
  if (Array.isArray(v)) return v.map(String);
  if (typeof v === "string") return [v];
  return [];
}

function applyControlState(
  data: BlockData,
  state: Record<string, unknown>,
): BlockData {
  if (!state || Object.keys(state).length === 0) return data;
  const result = { ...data };

  // dimension control drives group_by (charts) and rows (pivots)
  if (state["dimensions"] !== undefined) {
    const dims = asStringArray(state["dimensions"]);
    if (dims.length > 0) {
      const value = dims.length === 1 ? dims[0] : dims;
      (result as Record<string, unknown>)["group_by"] = value;
      (result as Record<string, unknown>)["rows"] = value;
    }
  }

  // cols control drives cols (pivots)
  if (state["cols"] !== undefined) {
    const cols = asStringArray(state["cols"]);
    (result as Record<string, unknown>)["cols"] = cols.length === 1 ? cols[0] : cols;
  }

  // measure control drives y (charts) and generates pivot measure tuples
  if (state["measures"] !== undefined) {
    const fields = asStringArray(state["measures"]);
    const meta = (state["_measure_meta"] ?? {}) as Record<string, { format?: string; aggregation?: string }>;

    // Charts: y accepts string or string[]
    (result as Record<string, unknown>)["y"] = fields.length === 1 ? fields[0] : fields;

    // Pivots: generate a measure tuple per selected field
    // Priority for format: frontmatter measure meta > field name inference > null
    // Priority for aggregation: frontmatter measure meta > "sum"
    (result as Record<string, unknown>)["measures"] = fields.map((field) => {
      const label = field.split(".").pop()?.replace(/_/g, " ") ?? field;
      const key = field.split(".").pop() ?? field;
      const m = meta[field];
      const fmt = m?.format ?? inferFormat(field);
      const agg = m?.aggregation ?? "sum";
      return { key, field, aggregation: agg, format: fmt, label };
    });
  }

  // sort_order control drives sort direction
  if (state["sort_order"] !== undefined) {
    const sort = (result as Record<string, unknown>)["sort"];
    if (sort && typeof sort === "object") {
      (sort as Record<string, unknown>)["dir"] = state["sort_order"];
    }
  }

  return result;
}

/** Normalize positional tuple arrays to MeasureTuple objects. */
function normalizeTuples(tuples: unknown[]): MeasureTuple[] {
  return tuples
    .filter((t) => t !== null && t !== undefined)
    .map((t) => {
      if (typeof t === "string" && t.trim().startsWith("#")) return null; // commented
      if (!Array.isArray(t)) return t as MeasureTuple;
      const [key, field, aggregation, format, label] = t as [
        string, unknown, string?, string?, string?
      ];
      return { key, field, aggregation: aggregation ?? null, format: format ?? null, label: label ?? null };
    })
    .filter(Boolean) as MeasureTuple[];
}

/** Normalize column tuple arrays to ColumnTuple objects. */
function normalizeColumnTuples(tuples: unknown[]): ColumnTuple[] {
  return tuples
    .filter((t) => t !== null && t !== undefined)
    .map((t) => {
      if (!Array.isArray(t)) return t as ColumnTuple;
      const [key, field, aggregation, format, label] = t as [
        string, string, string?, string?, string?
      ];
      return { key, field, aggregation: aggregation ?? null, format: format ?? null, label: label ?? null };
    }) as ColumnTuple[];
}

/** Normalize window tuple arrays [key, source, type, label] to WindowSpec objects. */
function normalizeWindowTuples(tuples: unknown[]): Array<{ key: string; source: string; type: string; label?: string | null }> {
  return tuples
    .filter((t) => t !== null && t !== undefined)
    .map((t) => {
      if (!Array.isArray(t)) return t as { key: string; source: string; type: string; label?: string | null };
      const [key, source, type, label] = t as [string, string, string, string?];
      return { key, source, type, label: label ?? null };
    });
}
