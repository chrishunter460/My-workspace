/**
 * Renders a control.config block inline and registers it with the sidebar.
 */
import type { ApiClient } from "../api-client";
import type { DeFunkBlock } from "../contract";
import { registerPanel, updateControl } from "./config-panel";

export function renderConfigPanel(block: DeFunkBlock, el: HTMLElement, client: ApiClient): void {
  const id = block.config?.id ?? "controls";
  const data = block.data;
  const title = block.formatting?.title ?? id;

  registerPanel(id, {});

  const container = el.createDiv({ cls: "de-funk-config-panel" });
  container.createEl("h4", { text: title });

  // Dimension selector
  if (data["dimensions"]) {
    const dims = data["dimensions"] as string[];
    addDropdown(container, id, "dimensions", "Group by", dims, client);
  }

  // Measure selector
  if (data["measures"]) {
    const measures = data["measures"] as string[];
    addDropdown(container, id, "measures", "Measure", measures, client);
  }

  // Sort order toggle
  if (data["sort_order"]) {
    addToggle(container, id, "sort_order", "Sort", ["asc", "desc"]);
  }

  // Show legend checkbox
  if (data["show_legend"]) {
    const spec = data["show_legend"] as { type: string; default?: boolean };
    addCheckbox(container, id, "show_legend", "Show legend", spec.default ?? true);
  }

  // Show totals checkbox
  if (data["show_totals"]) {
    const spec = data["show_totals"] as { type: string; default?: boolean };
    addCheckbox(container, id, "show_totals", "Show totals", spec.default ?? true);
  }

  // Color palette dropdown
  if (data["color_palette"]) {
    const spec = data["color_palette"] as { available: string[] };
    addDropdown(container, id, "color_palette", "Color palette", spec.available, client, false);
  }

  // Generic selects
  if (Array.isArray(data["select"])) {
    for (const sel of data["select"] as Array<{ id: string; label: string; source: string; multi?: boolean }>) {
      addAsyncDropdown(container, id, sel.id, sel.label, sel.source, client, sel.multi ?? false);
    }
  }
}

function addDropdown(
  container: HTMLElement,
  panelId: string,
  key: string,
  label: string,
  options: string[],
  _client: ApiClient,
  isFirst = true,
): void {
  const row = container.createDiv({ cls: "de-funk-control-row" });
  row.createEl("label", { text: label });
  const select = row.createEl("select");
  for (const opt of options) {
    const o = select.createEl("option", { value: opt, text: opt.split(".").pop() ?? opt });
    if (isFirst && opt === options[0]) o.selected = true;
  }
  select.addEventListener("change", () => {
    updateControl(panelId, key, select.value);
  });
  // Set initial state
  updateControl(panelId, key, options[0] ?? null);
}

function addToggle(
  container: HTMLElement,
  panelId: string,
  key: string,
  label: string,
  values: string[],
): void {
  let idx = 0;
  const row = container.createDiv({ cls: "de-funk-control-row" });
  row.createEl("label", { text: label });
  const btn = row.createEl("button", { text: values[0] });
  btn.addEventListener("click", () => {
    idx = (idx + 1) % values.length;
    btn.textContent = values[idx];
    updateControl(panelId, key, values[idx]);
  });
  updateControl(panelId, key, values[0]);
}

function addCheckbox(
  container: HTMLElement,
  panelId: string,
  key: string,
  label: string,
  defaultVal: boolean,
): void {
  const row = container.createDiv({ cls: "de-funk-control-row" });
  const cb = row.createEl("input", { type: "checkbox" } as never);
  (cb as HTMLInputElement).checked = defaultVal;
  row.createEl("label", { text: label });
  cb.addEventListener("change", () => {
    updateControl(panelId, key, (cb as HTMLInputElement).checked);
  });
  updateControl(panelId, key, defaultVal);
}

function addAsyncDropdown(
  container: HTMLElement,
  panelId: string,
  key: string,
  label: string,
  source: string,
  client: ApiClient,
  _multi: boolean,
): void {
  const row = container.createDiv({ cls: "de-funk-control-row" });
  row.createEl("label", { text: label });
  const select = row.createEl("select");
  select.createEl("option", { value: "", text: "Loading..." });

  client.getDimensions(source).then((res) => {
    select.empty();
    for (const val of res.values) {
      select.createEl("option", { value: String(val), text: String(val) });
    }
    if (res.values.length > 0) {
      updateControl(panelId, key, res.values[0]);
    }
  }).catch(() => {
    select.empty();
    select.createEl("option", { value: "", text: "Error loading" });
  });

  select.addEventListener("change", () => {
    updateControl(panelId, key, select.value);
  });
}
