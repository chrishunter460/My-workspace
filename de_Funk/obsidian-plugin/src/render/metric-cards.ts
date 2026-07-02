/**
 * Render cards.metric exhibits as KPI card tiles.
 */
import type { DeFunkBlock, MetricResponse } from "../contract";
import { formatValue } from "./format";

export function renderMetricCards(
  block: DeFunkBlock,
  response: MetricResponse,
  el: HTMLElement,
): void {
  const formatting = block.formatting ?? {};
  const title = formatting.title;
  const columns = (formatting as { columns?: number }).columns ?? 4;

  if (title) {
    el.createEl("h4", { text: title, cls: "de-funk-metrics-title" });
  }

  const grid = el.createDiv({ cls: "de-funk-metrics-grid" });
  grid.style.gridTemplateColumns = `repeat(${columns}, 1fr)`;

  for (const metric of response.metrics) {
    const card = grid.createDiv({ cls: "de-funk-metric-card" });
    card.createEl("div", {
      text: formatValue(metric.value, metric.format),
      cls: "de-funk-metric-value",
    });
    card.createEl("div", { text: metric.label, cls: "de-funk-metric-label" });
  }
}
