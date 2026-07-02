/**
 * Main de_funk code block processor.
 *
 * Registered with Obsidian's registerMarkdownCodeBlockProcessor("de_funk", ...).
 * Dispatches to the correct renderer based on the catalog key.
 */
import type { MarkdownPostProcessorContext } from "obsidian";
import type { ApiClient } from "../api-client";
import type { NoteFrontmatter } from "../frontmatter";
import { parseBlock, buildRequest } from "../resolver";
import { filtersToSpecs } from "../frontmatter";
import { getState, registerPanel } from "./config-panel";
import { subscribeToFilterChanges } from "../filter-bus";
import { renderGraphical } from "../render/graphical";
import { renderMetricCards } from "../render/metric-cards";
import { renderTabulator, renderTabulatorPivot } from "../render/tabulator";

const GRAPHICAL_TYPES = new Set([
  "plotly.line", "line", "line_chart",
  "plotly.bar", "bar", "bar_chart",
  "plotly.scatter", "scatter",
  "plotly.area", "area",
  "plotly.pie", "pie",
  "plotly.heatmap", "heatmap",
  "plotly.box", "box", "ohlcv", "candlestick",
]);
const TABLE_DATA_TYPES = new Set(["table.data", "data_table"]);
const PIVOT_TYPES = new Set(["table.pivot", "pivot", "pivot_table"]);
const METRIC_TYPES = new Set(["cards.metric", "kpi", "metric_cards"]);
const CONTROL_TYPES = new Set(["control.config", "config"]);

export function createBlockProcessor(client: ApiClient, getFrontmatter: () => NoteFrontmatter) {
  return async (source: string, el: HTMLElement, ctx: MarkdownPostProcessorContext) => {
    // In Live Preview (edit mode), skip custom rendering — Obsidian shows the raw block natively.
    // Check ancestor classes: reading view = .markdown-preview-view, edit = .markdown-source-view
    if (el.closest(".markdown-source-view")) {
      return;
    }

    el.addClass("de-funk-block");

    let block;
    try {
      block = parseBlock(source);
    } catch (err) {
      renderError(el, "Parse error", String(err));
      return;
    }

    const { type } = block;

    // Control blocks are sidebar-only — frontmatter controls: is the source of truth.
    // If a control.config block appears in the note body, silently register the panel
    // (so config_ref wiring works) but render nothing visible.
    if (CONTROL_TYPES.has(type)) {
      const panelId = block.config?.id ?? "controls";
      registerPanel(panelId);
      return;
    }

    // For exhibits with config_ref, read control state fresh on every render
    const configRef = block.config?.config_ref;

    let renderSeq = 0;

    const render = async () => {
      const seq = ++renderSeq;

      // Read control state fresh from the panel store every render
      const controlState = configRef ? getState(configRef) : {};

      // Skip render if config_ref is set but state is empty (sidebar hasn't initialized yet)
      if (configRef && Object.keys(controlState).length === 0) {
        console.log(`[de-funk] skipping render for '${configRef}' — no control state yet`);
        return;
      }

      const frontmatter = getFrontmatter();
      const noteFilters = filtersToSpecs(frontmatter.filters);
      const payload = buildRequest(block, noteFilters, controlState);
      console.log(`[de-funk] render '${configRef ?? 'no-ref'}' seq=${seq}`, {
        rows: payload["rows"], cols: payload["cols"],
        measures: (payload["measures"] as unknown[])?.length ?? 0,
        filters: (payload["filters"] as Array<{field: string; value: unknown}>)?.map(f => `${f.field}=${JSON.stringify(f.value)}`),
      });

      el.empty();
      el.addClass("de-funk-loading");

      try {
        const response = block.layer === "bronze"
          ? await client.bronzeQuery(payload)
          : await client.query(payload);

        // Discard stale responses — a newer render() has since been triggered
        if (seq !== renderSeq) return;

        el.removeClass("de-funk-loading");

        if (GRAPHICAL_TYPES.has(type)) {
          await renderGraphical(block, response as never, el);
        } else if (TABLE_DATA_TYPES.has(type)) {
          renderTabulator(block, response as never, el);
        } else if (PIVOT_TYPES.has(type)) {
          renderTabulatorPivot(block, response as never, el);
        } else if (METRIC_TYPES.has(type)) {
          renderMetricCards(block, response as never, el);
        } else {
          renderError(el, "Unknown type", `No renderer for '${type}'`);
        }

        renderActiveFooter(block, payload, el);
      } catch (err) {
        if (seq !== renderSeq) return;
        el.removeClass("de-funk-loading");
        renderError(el, "Query error", String(err));
      }
    };

    // Subscribe to the global event bus — handles BOTH filter and control changes.
    // Control state is read fresh from getState() inside render(), so no per-panel
    // listener needed. This bus survives Obsidian re-renders reliably.
    const unsubFilter = subscribeToFilterChanges(() => render());

    // Initial render (render() skips if config_ref set but state empty)
    await render();

    // Cleanup on unmount
    ctx.addChild({
      onunload: () => {
        unsubFilter();
      },
    } as never);
  };
}

function renderError(el: HTMLElement, title: string, message: string): void {
  const card = el.createDiv({ cls: "de-funk-error" });
  card.createEl("strong", { text: title });
  card.createEl("p", { text: message });
}

function renderActiveFooter(block: ReturnType<typeof parseBlock>, payload: Record<string, unknown>, el: HTMLElement): void {
  const footer = el.createDiv({ cls: "de-funk-footer" });
  const summary = buildFooterSummary(block, payload);
  const details = footer.createEl("details");
  details.createEl("summary", { text: `▶ Active: ${summary}` });
}

function buildFooterSummary(block: ReturnType<typeof parseBlock>, payload: Record<string, unknown>): string {
  const parts: string[] = [];
  if (block.config?.config_ref) parts.push(`config=${block.config.config_ref}`);
  const filters = payload["filters"] as Array<{ field: string; value: unknown }> | undefined;
  if (filters && filters.length > 0) {
    const filterStr = filters.map((f) => `${f.field.split(".").pop()}=${JSON.stringify(f.value)}`).join(" | ");
    parts.push(`filter: ${filterStr}`);
  }
  return parts.join(" | ") || "no active filters";
}
