/**
 * TypeScript types mirroring the de_funk API data contract.
 * Matches src/de_funk/api/models/requests.py exactly.
 */

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

export interface FilterSpec {
  field: string;
  operator?: "in" | "eq" | "gte" | "lte" | "between" | "like";
  value: unknown[] | string | number | Record<string, unknown>;
}

export interface PageFilters {
  ignore?: string[];  // [] = inherit all, ["*"] = ignore all
}

export interface SortSpec {
  by?: string;
  order?: "asc" | "desc";
  values?: string[];
}

export interface MeasureTuple {
  key: string;
  field: string | Record<string, unknown>;  // domain.field or {fn: ...}
  aggregation?: string | null;
  format?: string | null;
  label?: string | null;
}

export interface ColumnTuple {
  key: string;
  field: string;
  aggregation?: string | null;
  format?: string | null;
  label?: string | null;
}

// ---------------------------------------------------------------------------
// Block config (parsed from YAML)
// ---------------------------------------------------------------------------

export interface BlockData {
  // graphical
  x?: string;
  y?: string | string[];
  group_by?: string;
  size?: string;
  color?: string;
  labels?: string;
  values?: string;
  z?: string;
  aggregation?: string;
  sort?: SortSpec;
  // box
  category?: string;
  open?: string;
  high?: string;
  low?: string;
  close?: string;
  // table.data
  columns?: Array<[string, string, string?, string?, string?]>;
  sort_by?: string;
  sort_order?: "asc" | "desc";
  // shared
  filters?: Array<Record<string, unknown>>;
  // pivot
  rows?: string | string[];
  cols?: string | string[] | null;
  layout?: "by_dimension" | "by_measure" | "by_column";
  measures?: Array<unknown>;
  buckets?: Record<string, unknown>;
  windows?: Array<unknown>;
  totals?: { rows?: boolean; cols?: boolean };
  // metrics
  metrics?: Array<unknown>;
}

export interface BlockFormatting {
  title?: string;
  description?: string;
  height?: number;
  show_legend?: boolean;
  interactive?: boolean;
  color_palette?: string;
  shading?: { on: string; palette: string };
  // table
  page_size?: number;
  download?: boolean;
  renderer?: "default";
  theme?: string;
  // plotly render options
  line_shape?: "linear" | "spline" | "hv";
  fill?: "none" | "tozeroy" | "tonexty";
  markers?: boolean;
  orientation?: "v" | "h";
  barmode?: "group" | "stack" | "relative";
  opacity?: number;
  marker_size?: number;
  hole?: number;
  color_scale?: string;
  show_values?: boolean;
  // cards
  columns?: number;
  // scroll
  max_height?: number;
}

export interface BlockConfig {
  id?: string;
  config_ref?: string;
  page_filters?: PageFilters;
  filters?: Record<string, unknown>;
}

export interface DeFunkBlock {
  type: string;
  layer?: "silver" | "bronze";
  data: BlockData;
  formatting?: BlockFormatting;
  config?: BlockConfig;
}

// ---------------------------------------------------------------------------
// API response types
// ---------------------------------------------------------------------------

export interface SeriesData {
  name: string;
  x: unknown[];
  y: unknown[];
  size?: unknown[];
}

export interface GraphicalResponse {
  series: SeriesData[];
  truncated?: boolean;
}

export interface TableColumn {
  key: string;
  label: string;
  format?: string;
}

export interface TableResponse {
  columns: TableColumn[];
  rows: unknown[][];
  truncated?: boolean;
}

export interface ExpandableData {
  columns: Array<{ key: string; label: string; format?: string }>;
  children: Record<string, unknown[][]>;
  total_rows: number;
}

export interface MetricValue {
  key: string;
  label: string;
  value: unknown;
  format?: string;
}

export interface MetricResponse {
  metrics: MetricValue[];
}

export interface DimensionValuesResponse {
  field: string;
  values: unknown[];
}

export type ApiResponse =
  | GraphicalResponse
  | TableResponse
  | MetricResponse;
