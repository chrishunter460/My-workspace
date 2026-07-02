/**
 * Parse note frontmatter — extract models: list and filters: definitions.
 * Used to build the note-level filter state and sidebar controls.
 */
import * as yaml from "js-yaml";
import type { FilterSpec } from "./contract";

export interface NoteFilter {
  id: string;
  source: string;           // domain.field
  multi: boolean;
  defaultValue?: unknown;
  currentValue?: unknown;
  type: "select" | "date_range" | "range";
  layer?: "silver" | "bronze"; // data layer — bronze uses /api/bronze/dimensions
  sort_by_measure?: string; // domain.field to order select values by (e.g. stocks.market_cap)
  sort_dir?: "asc" | "desc";
  context_filters?: boolean; // re-fetch values with active page filters applied
}

/**
 * Measure option — supports three forms in YAML:
 *   - "domain.field"                     → string shorthand
 *   - [domain.field, "$M"]              → [field, format] tuple
 *   - [domain.field, "$M", "avg"]       → [field, format, aggregation] tuple
 */
export interface MeasureDef {
  field: string;
  format: string | null;
  aggregation: string | null;
}

/** Normalize raw measure entry (string, tuple, or object) to MeasureDef. */
export function parseMeasureDef(raw: unknown): MeasureDef | null {
  if (typeof raw === "string") {
    return { field: raw, format: null, aggregation: null };
  }
  if (Array.isArray(raw) && raw.length >= 1) {
    return {
      field: String(raw[0]),
      format: raw[1] != null ? String(raw[1]) : null,
      aggregation: raw[2] != null ? String(raw[2]) : null,
    };
  }
  if (typeof raw === "object" && raw !== null && (raw as Record<string, unknown>)["field"]) {
    const r = raw as Record<string, unknown>;
    return {
      field: String(r["field"]),
      format: r["format"] != null ? String(r["format"]) : null,
      aggregation: r["aggregation"] != null ? String(r["aggregation"]) : null,
    };
  }
  return null;
}

export interface ControlDef {
  id: string;
  dimensions?: string[];
  cols?: string[];
  measures?: unknown[];  // raw from YAML — parsed via parseMeasureDef at render time
  sort_by?: string[];
  sort_order?: string[];
  color_palette?: string[];
  current?: Record<string, unknown>;
}

export interface NoteFrontmatter {
  title?: string;
  models: string[];
  filters: Record<string, NoteFilter>;
  controls: ControlDef[];
}

/** Parse the raw frontmatter object from Obsidian's metadataCache. */
export function parseFrontmatter(raw: Record<string, unknown> | null): NoteFrontmatter {
  if (!raw) return { models: [], filters: {}, controls: [] };

  const models: string[] = Array.isArray(raw["models"]) ? raw["models"] as string[] : [];

  const rawFilters = (raw["filters"] ?? {}) as Record<string, unknown>;
  const filters: Record<string, NoteFilter> = {};

  for (const [id, spec] of Object.entries(rawFilters)) {
    if (typeof spec !== "object" || spec === null) continue;
    const s = spec as Record<string, unknown>;
    const source = (s["source"] as string) ?? "";
    const multi = (s["multi"] as boolean) ?? false;
    const defaultValue = s["default"];
    const sort_by_measure = s["sort_by_measure"] as string | undefined;
    const sort_dir = (s["sort_dir"] as "asc" | "desc" | undefined) ?? "desc";
    const context_filters = (s["context_filters"] as boolean | undefined) ?? true;
    const layer = (s["layer"] as "silver" | "bronze" | undefined) ?? "silver";

    // Type is required — no inference from field names
    const explicitType = s["type"] as string | undefined;
    let filterType: NoteFilter["type"] = "select";
    if (explicitType === "range") {
      filterType = "range";
    } else if (explicitType === "date_range") {
      filterType = "date_range";
    } else if (explicitType === "select") {
      filterType = "select";
    } else {
      console.warn(`[de-funk] Filter "${id}" missing explicit type — defaulting to "select". Add type: select|date_range|range`);
    }

    filters[id] = {
      id,
      source,
      multi,
      defaultValue,
      currentValue: defaultValue,
      type: filterType,
      layer,
      sort_by_measure,
      sort_dir,
      context_filters,
    };
  }

  // Parse controls — supports array form [{id, dimensions, measures}] or dict form {id: {dimensions, measures}}
  const rawControls = raw["controls"];
  const controls: ControlDef[] = [];
  if (Array.isArray(rawControls)) {
    for (const c of rawControls) {
      if (typeof c === "object" && c !== null && (c as Record<string, unknown>)["id"]) {
        controls.push(c as ControlDef);
      }
    }
  } else if (typeof rawControls === "object" && rawControls !== null) {
    for (const [id, def] of Object.entries(rawControls as Record<string, unknown>)) {
      if (typeof def === "object" && def !== null) {
        controls.push({ id, ...(def as object) } as ControlDef);
      }
    }
  }

  return { title: raw["title"] as string | undefined, models, filters, controls };
}

/** Convert active filter state to FilterSpec array for API requests. */
export function filtersToSpecs(filters: Record<string, NoteFilter>): FilterSpec[] {
  const specs: FilterSpec[] = [];
  for (const f of Object.values(filters)) {
    const val = f.currentValue ?? f.defaultValue;
    if (val === undefined || val === null) continue;

    if (f.type === "select") {
      const values = Array.isArray(val) ? val : [val];
      if (values.length > 0) {
        specs.push({ field: f.source, operator: "in", value: values });
      }
    } else if (f.type === "date_range" && typeof val === "object") {
      specs.push({ field: f.source, operator: "between", value: val as Record<string, unknown> });
    } else if (f.type === "range" && typeof val === "object") {
      const rv = val as Record<string, unknown>;
      if (rv["from"] !== undefined || rv["to"] !== undefined) {
        specs.push({ field: f.source, operator: "between", value: rv });
      }
    }
  }
  return specs;
}

/** Parse frontmatter directly from raw markdown text.
 *
 * Obsidian's metadataCache strips keys it doesn't recognise (e.g.
 * context_filters, sort_by_measure, default). This parser extracts
 * the YAML block between the leading `---` fences and parses it with
 * js-yaml so all keys are preserved.
 */
export function parseFrontmatterFromText(text: string): NoteFrontmatter {
  const match = text.match(/^---\s*\n([\s\S]*?)\n---/);
  if (!match) return parseFrontmatter(null);
  try {
    const raw = yaml.load(match[1]) as Record<string, unknown> | null;
    return parseFrontmatter(raw);
  } catch (e) {
    console.error("[frontmatter] YAML parse error:", e);
    return parseFrontmatter(null);
  }
}
