/**
 * Filter sidebar panel — collapsible directory-tree layout.
 *
 * Layout:
 *   ▼ Note Filters
 *     ticker   [AAPL ▾]
 *     date     [2024-01-01]
 *   ▼ Controls
 *     ▼ controls          ← collapsible group per control id
 *       Group by  [stocks.ticker ▾]
 *       Measure   [stocks.adjusted_close ▾]
 *
 * Registered as an Obsidian leaf (ItemView) in the right/left sidebar.
 * Controls defined in note frontmatter `controls:` are rendered here and
 * drive exhibits via the config-panel pub/sub system.
 */
import type { WorkspaceLeaf } from "obsidian";
import { ItemView } from "obsidian";
import type { NoteFrontmatter, NoteFilter } from "./frontmatter";
import type { ApiClient } from "./api-client";
import { type ControlDef, parseMeasureDef } from "./frontmatter";
import { registerPanel, setControlSilent, notifyListeners, getState } from "./processors/config-panel";
import { notifyControlChanged } from "./filter-bus";

export const SIDEBAR_VIEW_TYPE = "de-funk-sidebar";

export class FilterSidebar extends ItemView {
  private frontmatter: NoteFrontmatter | null = null;
  private client: ApiClient;
  private onFilterChange: (id: string, value: unknown) => void;
  private onControlChange: (panelId: string, key: string, value: unknown) => void;
  // Map from filter id → refetch function, populated for context_filters pickers
  private contextRefetchers = new Map<string, () => void>();

  constructor(
    leaf: WorkspaceLeaf,
    client: ApiClient,
    onFilterChange: (id: string, value: unknown) => void,
    onControlChange: (panelId: string, key: string, value: unknown) => void,
  ) {
    super(leaf);
    this.client = client;
    this.onFilterChange = onFilterChange;
    this.onControlChange = onControlChange;
  }

  getViewType(): string { return SIDEBAR_VIEW_TYPE; }
  getDisplayText(): string { return "de-funk"; }
  getIcon(): string { return "bar-chart-2"; }

  async onOpen(): Promise<void> { this.render(); }
  async onClose(): Promise<void> { this.contentEl.empty(); }

  updateFrontmatter(fm: NoteFrontmatter): void {
    this.frontmatter = fm;
    this.contextRefetchers.clear();
    this.render();
  }

  /** Called by main.ts after any filter value changes. Re-fetches context_filters pickers. */
  refreshContextFilters(changedId: string): void {
    for (const [id, refetch] of this.contextRefetchers) {
      if (id !== changedId) refetch();
    }
  }

  private render(): void {
    const el = this.contentEl;
    el.empty();
    el.addClass("de-funk-sidebar");

    const fm = this.frontmatter;
    const hasFilters = fm && Object.keys(fm.filters).length > 0;
    const controlDefs = fm?.controls ?? [];
    const hasControls = controlDefs.length > 0;

    if (!hasFilters && !hasControls) {
      el.createEl("p", {
        text: "Open a note with de_funk filters or controls.",
        cls: "de-funk-sidebar-empty",
      });
      return;
    }

    // ── Refresh button ────────────────────────────────────────────────────
    const refreshBtn = el.createEl("button", {
      text: "↻ Refresh Exhibits",
      cls: "de-funk-refresh-btn",
    });
    refreshBtn.addEventListener("click", () => {
      console.log("[sidebar] manual refresh triggered");
      notifyControlChanged();
    });

    // ── Note Filters ──────────────────────────────────────────────────────
    if (hasFilters) {
      const section = el.createEl("details", { cls: "de-funk-section" });
      section.open = true;
      section.createEl("summary", { text: "Note Filters" });
      for (const filter of Object.values(fm!.filters)) {
        this.renderFilterControl(section, filter);
      }
    }

    // ── Controls (from control.config blocks in the note) ─────────────────
    if (hasControls) {
      const section = el.createEl("details", { cls: "de-funk-section" });
      section.open = true;
      section.createEl("summary", { text: "Controls" });
      for (const ctrl of controlDefs) {
        this.renderControlGroup(section, ctrl);
      }
    }
  }

  // ── Filter controls ──────────────────────────────────────────────────────

  private renderFilterControl(container: HTMLElement, filter: NoteFilter): void {
    const block = container.createDiv({ cls: "de-funk-filter-block" });
    block.createEl("div", { text: filter.id, cls: "de-funk-filter-label" });
    if (filter.type === "select") {
      this.renderTagSelect(block, filter);
    } else if (filter.type === "range") {
      this.renderRangeControl(block, filter);
    } else {
      this.renderDateRangeControl(block, filter);
    }
  }

  private renderTagSelect(container: HTMLElement, filter: NoteFilter): void {
    const ref = filter.source;
    const cur = filter.currentValue;
    const selected: Set<string> = new Set(
      Array.isArray(cur) ? cur.map(String) : cur ? [String(cur)] : []
    );

    // Tag strip — shows selected values as removable chips
    const tagStrip = container.createDiv({ cls: "de-funk-tag-strip" });

    // Search bar — type to narrow visible rows
    const searchInput = container.createEl("input", {
      cls: "de-funk-picker-search",
      attr: { type: "text", placeholder: "Search…" },
    }) as HTMLInputElement;

    // Picker — scrollable list of all available values
    const picker = container.createDiv({ cls: "de-funk-picker" });
    picker.createEl("div", { cls: "de-funk-picker-loading", text: "Loading…" });

    const RENDER_CAP = 200;
    let allValues: string[] = [];

    const renderPickerRows = (query: string) => {
      picker.empty();
      const q = query.toLowerCase();
      const filtered = q ? allValues.filter((v) => v.toLowerCase().includes(q)) : allValues;
      const capped = filtered.slice(0, RENDER_CAP);

      for (const s of capped) {
        const row = picker.createEl("div", {
          cls: "de-funk-picker-row" + (selected.has(s) ? " de-funk-picker-selected" : ""),
          attr: { "data-val": s },
        });
        row.setText(s);
        row.addEventListener("click", () => {
          if (selected.has(s)) {
            selected.delete(s);
            row.classList.remove("de-funk-picker-selected");
            tagStrip.querySelector(`[data-val="${CSS.escape(s)}"]`)?.remove();
          } else {
            row.classList.add("de-funk-picker-selected");
            addTag(s);
          }
          notify();
        });
      }

      if (filtered.length > RENDER_CAP) {
        picker.createEl("div", {
          cls: "de-funk-picker-hint",
          text: `Showing ${RENDER_CAP} of ${filtered.length} — type to search`,
        });
      }
    };

    searchInput.addEventListener("input", () => {
      renderPickerRows(searchInput.value);
    });

    const notify = () => {
      this.onFilterChange(filter.id, [...selected]);
    };

    const removeTag = (val: string, rowEl: HTMLElement) => {
      selected.delete(val);
      rowEl.remove();
      const pickerRow = picker.querySelector(`[data-val="${CSS.escape(val)}"]`) as HTMLElement | null;
      if (pickerRow) pickerRow.classList.remove("de-funk-picker-selected");
      notify();
    };

    const addTag = (val: string) => {
      selected.add(val);
      const chip = tagStrip.createEl("span", { cls: "de-funk-tag", attr: { "data-val": val } });
      chip.createEl("span", { text: val, cls: "de-funk-tag-label" });
      const x = chip.createEl("span", { text: "×", cls: "de-funk-tag-remove" });
      x.addEventListener("click", () => removeTag(val, chip));
    };

    // Render initial tags for defaultValue
    for (const v of selected) addTag(v);

    /** Gather active select filter values from all OTHER filters (for context_filters). */
    const gatherContextFilters = (): Array<{ field: string; value: unknown }> => {
      const fm = this.frontmatter;
      if (!fm) return [];
      return Object.values(fm.filters)
        .filter((f) => f.id !== filter.id && f.type === "select")
        .flatMap((f) => {
          const val = f.currentValue ?? f.defaultValue;
          if (val === undefined || val === null) return [];
          const values = Array.isArray(val) ? val : [val];
          if (values.length === 0) return [];
          return [{ field: f.source, value: values }];
        });
    };

    const fetchValues = () => {
      const ctxFilters = filter.context_filters ? gatherContextFilters() : undefined;
      const layer = filter.layer ?? "silver";
      const fetchPromise = filter.sort_by_measure
        ? this.client.getDimensions(ref, filter.sort_by_measure, filter.sort_dir ?? "desc", ctxFilters, layer)
        : this.client.getDimensions(ref, undefined, "desc", ctxFilters, layer);

      fetchPromise.then((res) => {
        // Reset search on re-fetch
        searchInput.value = "";

        // When context re-fetches, drop selected values no longer in the new set
        const newValues = new Set(res.values.map(String));
        let changed = false;
        for (const s of [...selected]) {
          if (!newValues.has(s)) {
            selected.delete(s);
            tagStrip.querySelector(`[data-val="${CSS.escape(s)}"]`)?.remove();
            changed = true;
          }
        }
        if (changed) notify();

        allValues = res.values.map(String);
        renderPickerRows("");
      }).catch(() => {
        picker.empty();
        picker.createEl("div", { cls: "de-funk-picker-error", text: "Error loading values" });
      });
    };

    // Register refetch for context_filters pickers
    if (filter.context_filters) {
      this.contextRefetchers.set(filter.id, fetchValues);
    }

    fetchValues();
  }

  private renderRangeControl(container: HTMLElement, filter: NoteFilter): void {
    const row = container.createDiv({ cls: "de-funk-range-row" });
    const cur = (filter.currentValue ?? filter.defaultValue) as Record<string, unknown> | undefined;

    const fromInput = row.createEl("input", {
      cls: "de-funk-range-input",
      attr: { type: "number", placeholder: "From" },
    }) as HTMLInputElement;

    row.createEl("span", { text: "–", cls: "de-funk-range-sep" });

    const toInput = row.createEl("input", {
      cls: "de-funk-range-input",
      attr: { type: "number", placeholder: "To" },
    }) as HTMLInputElement;

    if (cur?.["from"] !== undefined) fromInput.value = String(cur["from"]);
    if (cur?.["to"] !== undefined) toInput.value = String(cur["to"]);

    const notify = () => {
      const val: Record<string, number> = {};
      if (fromInput.value) val["from"] = Number(fromInput.value);
      if (toInput.value) val["to"] = Number(toInput.value);
      this.onFilterChange(filter.id, Object.keys(val).length > 0 ? val : undefined);
    };

    fromInput.addEventListener("change", notify);
    toInput.addEventListener("change", notify);
  }

  private renderDateRangeControl(container: HTMLElement, filter: NoteFilter): void {
    const input = container.createEl("input", { cls: "de-funk-filter-date" }) as HTMLInputElement;
    input.type = "date";
    const cur = filter.currentValue as Record<string, string> | undefined;
    if (cur?.["from"]) input.value = String(cur["from"]);
    input.addEventListener("change", () => {
      this.onFilterChange(filter.id, { from: input.value });
    });
  }

  // ── Control groups (from frontmatter controls:) ───────────────────────────

  private renderControlGroup(container: HTMLElement, ctrl: ControlDef): void {
    // Register the panel immediately so exhibits can subscribe during render
    registerPanel(ctrl.id, {});
    const saved = ctrl.current ?? {};

    const group = container.createEl("details", { cls: "de-funk-control-group" });
    group.open = true;
    group.createEl("summary", { text: ctrl.id });

    if (ctrl.dimensions && ctrl.dimensions.length > 0) {
      this.renderControlCheckboxList(group, ctrl.id, "dimensions", "Rows", ctrl.dimensions, saved["dimensions"]);
    }
    if (ctrl.cols && ctrl.cols.length > 0) {
      this.renderControlCheckboxList(group, ctrl.id, "cols", "Columns", ctrl.cols, saved["cols"]);
    }
    if (ctrl.measures && ctrl.measures.length > 0) {
      // Parse measure tuples: "field" | [field, format] | [field, format, agg]
      const parsed = ctrl.measures.map(parseMeasureDef).filter(Boolean) as Array<{ field: string; format: string | null; aggregation: string | null }>;
      const measureFields = parsed.map(m => m.field);
      const measureMeta: Record<string, { format?: string | null; aggregation?: string | null }> = {};
      for (const m of parsed) {
        measureMeta[m.field] = { format: m.format, aggregation: m.aggregation };
      }
      setControlSilent(ctrl.id, "_measure_meta", measureMeta);
      this.renderControlCheckboxList(group, ctrl.id, "measures", "Measures", measureFields, saved["measures"]);
    }
    if (ctrl.sort_by && ctrl.sort_by.length > 0) {
      this.renderControlDropdown(group, ctrl.id, "sort_by", "Sort by", ctrl.sort_by, saved["sort_by"]);
    }
    if (ctrl.sort_order && ctrl.sort_order.length > 0) {
      this.renderControlToggle(group, ctrl.id, "sort_order", "Order", ctrl.sort_order, saved["sort_order"]);
    }
    if (ctrl.color_palette && ctrl.color_palette.length > 0) {
      this.renderControlDropdown(group, ctrl.id, "color_palette", "Palette", ctrl.color_palette, saved["color_palette"]);
    }

    // Notify listeners ONCE after all controls are initialized
    notifyListeners(ctrl.id);
  }

  private renderControlCheckboxList(
    container: HTMLElement,
    panelId: string,
    key: string,
    label: string,
    options: string[],
    savedValue?: unknown,
  ): void {
    const block = container.createDiv({ cls: "de-funk-control-block" });
    block.createEl("div", { text: label, cls: "de-funk-filter-label" });

    // Resolve initial selection: frontmatter current > in-memory > first option
    const inMemory = getState(panelId)[key];
    const fromSaved = Array.isArray(savedValue) ? savedValue as string[]
      : typeof savedValue === "string" ? [savedValue] : null;
    const fromMemory = Array.isArray(inMemory) ? inMemory as string[]
      : typeof inMemory === "string" ? [inMemory] : null;
    const initial = fromSaved ?? fromMemory ?? [options[0]];
    const selected = new Set<string>(initial.filter((v) => options.includes(v)));

    const notify = () => {
      const value = [...selected];
      console.log(`[sidebar] control changed: ${panelId}.${key} =`, value);
      setControlSilent(panelId, key, value);
      notifyControlChanged();
      setTimeout(() => this.onControlChange(panelId, key, value), 500);
    };

    // Tag strip — shows selected values as removable chips
    const tagStrip = block.createDiv({ cls: "de-funk-tag-strip" });

    // Search bar
    const searchInput = block.createEl("input", {
      cls: "de-funk-picker-search",
      attr: { type: "text", placeholder: "Search…" },
    }) as HTMLInputElement;

    // Scrollable picker list
    const picker = block.createDiv({ cls: "de-funk-picker" });

    const displayName = (opt: string) => opt.includes(".") ? opt.split(".").pop()! : opt;

    searchInput.addEventListener("input", () => {
      const q = searchInput.value.toLowerCase();
      picker.querySelectorAll<HTMLElement>(".de-funk-picker-row").forEach((row) => {
        const val = (row.getAttribute("data-val") ?? "").toLowerCase();
        row.style.display = val.includes(q) ? "" : "none";
      });
    });

    const removeTag = (val: string) => {
      selected.delete(val);
      tagStrip.querySelector(`[data-val="${CSS.escape(val)}"]`)?.remove();
      const pickerRow = picker.querySelector(`[data-val="${CSS.escape(val)}"]`) as HTMLElement | null;
      if (pickerRow) pickerRow.classList.remove("de-funk-picker-selected");
      notify();
    };

    const addTag = (val: string) => {
      selected.add(val);
      const chip = tagStrip.createEl("span", { cls: "de-funk-tag", attr: { "data-val": val } });
      chip.createEl("span", { text: displayName(val), cls: "de-funk-tag-label" });
      const x = chip.createEl("span", { text: "×", cls: "de-funk-tag-remove" });
      x.addEventListener("click", () => removeTag(val));
    };

    // Render initial tags
    for (const v of selected) addTag(v);

    // Render picker rows
    for (const opt of options) {
      const s = opt;
      const row = picker.createEl("div", {
        cls: "de-funk-picker-row" + (selected.has(s) ? " de-funk-picker-selected" : ""),
        attr: { "data-val": s },
      });
      row.setText(displayName(s));

      row.addEventListener("click", () => {
        if (selected.has(s)) {
          selected.delete(s);
          row.classList.remove("de-funk-picker-selected");
          tagStrip.querySelector(`[data-val="${CSS.escape(s)}"]`)?.remove();
        } else {
          row.classList.add("de-funk-picker-selected");
          addTag(s);
        }
        notify();
      });
    }

    // Set initial control state (silent — notifyListeners called after all controls render)
    setControlSilent(panelId, key, [...selected]);
  }

  private renderControlDropdown(
    container: HTMLElement,
    panelId: string,
    key: string,
    label: string,
    options: string[],
    savedValue?: string,
  ): void {
    const row = container.createDiv({ cls: "de-funk-control-row" });
    row.createEl("label", { text: label, cls: "de-funk-filter-label" });
    const select = row.createEl("select", { cls: "de-funk-filter-select" });

    for (const opt of options) {
      const display = opt.includes(".") ? opt.split(".").pop()! : opt;
      select.createEl("option", { value: opt, text: display });
    }

    // Priority: frontmatter current > in-memory state > first option
    const inMemory = getState(panelId)[key] as string | undefined;
    const initial = (savedValue && options.includes(savedValue)) ? savedValue
      : (inMemory && options.includes(inMemory)) ? inMemory
      : options[0] ?? null;

    if (initial) {
      select.value = initial;
      setControlSilent(panelId, key, initial);
    }

    select.addEventListener("change", () => {
      setControlSilent(panelId, key, select.value);
      notifyControlChanged();
      setTimeout(() => this.onControlChange(panelId, key, select.value), 500);
    });
  }

  private renderControlToggle(
    container: HTMLElement,
    panelId: string,
    key: string,
    label: string,
    values: string[],
    savedValue?: string,
  ): void {
    const row = container.createDiv({ cls: "de-funk-control-row" });
    row.createEl("label", { text: label, cls: "de-funk-filter-label" });

    const existing = savedValue ?? getState(panelId)[key] as string | undefined;
    let idx = existing ? Math.max(values.indexOf(existing), 0) : 0;
    const btn = row.createEl("button", { text: values[idx], cls: "de-funk-toggle-btn" });

    setControlSilent(panelId, key, values[idx]);

    btn.addEventListener("click", () => {
      idx = (idx + 1) % values.length;
      btn.textContent = values[idx];
      setControlSilent(panelId, key, values[idx]);
      notifyControlChanged();
      setTimeout(() => this.onControlChange(panelId, key, values[idx]), 500);
    });
  }
}
