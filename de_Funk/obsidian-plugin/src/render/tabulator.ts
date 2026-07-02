/**
 * Tabulator renderer for table.data and table.pivot exhibits.
 *
 * Replaces AG Grid with Tabulator (MIT) for:
 * - Native frozen columns (no workarounds)
 * - Collapsible row groups for multi-row pivots
 * - Built-in clipboard copy
 * - Column grouping (spanners)
 */
// @ts-ignore — no type declarations for tabulator-tables
import { TabulatorFull as Tabulator } from "tabulator-tables";
import type { DeFunkBlock, TableResponse } from "../contract";
import { formatValue } from "./format";

// Tabulator CSS — imported as text by esbuild, injected once
// @ts-ignore
import tabulatorBaseCss from "tabulator-tables/dist/css/tabulator_simple.min.css";
// @ts-ignore
import tabulatorDarkCss from "tabulator-tables/dist/css/tabulator_midnight.min.css";

let initialized = false;

function initTabulator(): void {
  if (initialized) return;
  initialized = true;

  const style = document.createElement("style");
  style.id = "de-funk-tabulator-styles";
  const isDark = document.body.classList.contains("theme-dark");
  style.textContent = isDark ? tabulatorDarkCss : tabulatorBaseCss;
  document.head.appendChild(style);
}

/**
 * Render a table.data or table.pivot response using Tabulator.
 */
export function renderTabulator(
  block: DeFunkBlock,
  response: TableResponse,
  el: HTMLElement,
): void {
  initTabulator();

  const formatting = block.formatting ?? {};
  const title = formatting.title;
  const maxH = formatting.max_height ?? 500;

  if (title) {
    el.createEl("h4", { text: title, cls: "de-funk-table-title" });
  }

  const { columns, rows } = response;

  if (!columns || !rows || rows.length === 0) {
    el.createDiv({ cls: "de-funk-empty", text: "No data returned" });
    return;
  }

  // Detect pivot-style columns (key contains "||" separator)
  const hasPivotCols = columns.some(c => c.key.includes("||"));

  // Build row data — normalize "TOTAL" → "Total"
  const rowData = rows.map((row) => {
    const obj: Record<string, unknown> = {};
    columns.forEach((col, idx) => {
      const v = row[idx];
      obj[col.key] = typeof v === "string" && v.toUpperCase() === "TOTAL" ? "Total" : v;
    });
    return obj;
  });

  // Identify row key columns (non-pivot descriptive columns)
  const rowKeys = hasPivotCols
    ? columns.filter(c => !c.key.includes("||")).map(c => c.key)
    : [];

  // Separate grand total rows
  const isGrandTotal = (r: Record<string, unknown>) =>
    rowKeys.length > 0 && rowKeys.every(k => String(r[k]).toLowerCase() === "total");

  const dataRows = rowData.filter(r => !isGrandTotal(r));
  const totalRows = rowData.filter(isGrandTotal);

  // Check for subtotal rows (some but not all row keys are "Total")
  const hasSubtotals = dataRows.some(r =>
    rowKeys.some(k => String(r[k]).toLowerCase() === "total")
  );

  // Build Tabulator column definitions
  let columnDefs: Record<string, unknown>[];

  if (hasPivotCols) {
    // Pivot: group data columns by measure, freeze row labels
    const groups: Record<string, Record<string, unknown>[]> = {};
    const rowCols: Record<string, unknown>[] = [];

    columns.forEach((col) => {
      if (col.key.includes("||")) {
        const [measure, value] = col.key.split("||", 2);
        if (!groups[measure]) groups[measure] = [];
        groups[measure].push({
          title: value || col.label,
          field: col.key,
          minWidth: 90,
          hozAlign: "right",
          headerSort: true,
          resizable: true,
          formatter: (cell: { getValue: () => unknown }) => {
            const v = cell.getValue();
            if (col.format) return formatValue(v, col.format);
            return typeof v === "number" ? v.toLocaleString() : String(v ?? "");
          },
        });
      } else {
        rowCols.push({
          title: col.label || col.key,
          field: col.key,
          frozen: true,
          width: 200,
          minWidth: 150,
          maxWidth: 300,
          headerSort: true,
          resizable: true,
          cssClass: "de-funk-row-label",
        });
      }
    });

    // Build column groups (spanners) — skip spanner when only one measure
    const measureKeys = Object.keys(groups);
    if (measureKeys.length === 1) {
      // Single measure — flatten, no spanner header
      columnDefs = [...rowCols, ...groups[measureKeys[0]]];
    } else {
      const groupDefs = Object.entries(groups).map(([measure, children]) => ({
        title: measure.replace(/_/g, " ").toUpperCase(),
        columns: children,
      }));
      columnDefs = [...rowCols, ...groupDefs];
    }
  } else {
    // Flat table
    columnDefs = columns.map((col, idx) => ({
      title: col.label || col.key,
      field: col.key,
      frozen: idx === 0,
      width: idx === 0 ? 200 : undefined,
      minWidth: idx === 0 ? 150 : 80,
      maxWidth: idx === 0 ? 300 : undefined,
      hozAlign: typeof rows[0]?.[idx] === "number" ? "right" as const : undefined,
      headerSort: true,
      resizable: true,
      formatter: col.format
        ? (cell: { getValue: () => unknown }) => formatValue(cell.getValue(), col.format ?? null)
        : undefined,
    }));
  }

  // Grid container
  const gridDiv = el.createDiv({ cls: "de-funk-tabulator" });
  const gridHeight = Math.min(maxH, rows.length * 28 + 80);
  gridDiv.style.cssText = `height:${gridHeight}px; width:100%;`;

  // Tabulator options
  const options: Record<string, unknown> = {
    data: dataRows,
    columns: columnDefs,
    layout: "fitDataFill",
    height: gridHeight,
    movableColumns: false,
    clipboard: true,
    clipboardCopyRowRange: "active",
    selectable: false,
    // Row styling for total/subtotal rows
    rowFormatter: (row: { getData: () => Record<string, unknown>; getElement: () => HTMLElement }) => {
      const data = row.getData();
      const totalValues = Object.values(data).filter(
        v => typeof v === "string" && v.toLowerCase() === "total"
      );
      if (totalValues.length > 0) {
        const el = row.getElement();
        el.style.backgroundColor = "rgba(128,128,128,0.08)";
        el.style.fontWeight = "600";
      }
    },
  };

  // N-level tree for multi-row pivots with NULL collapse
  if (hasPivotCols && rowKeys.length > 1) {
    // Compute tree path for each row: non-NULL, non-"Total" row key values
    function getPath(r: Record<string, unknown>): string[] {
      return rowKeys
        .map(k => r[k])
        .filter(v => v !== null && v !== undefined
          && String(v) !== "" && String(v).toLowerCase() !== "total")
        .map(v => String(v));
    }

    // Add a display label field to each row (last element of its path)
    for (const r of dataRows) {
      const path = getPath(r);
      (r as Record<string, unknown>)._label = path.length > 0 ? path[path.length - 1] : "Total";
      (r as Record<string, unknown>)._pathLen = path.length;
      (r as Record<string, unknown>)._pathKey = path.join("||");
    }

    // Sort by path so parents come before children
    dataRows.sort((a, b) => {
      const pa = (a as Record<string, unknown>)._pathKey as string;
      const pb = (b as Record<string, unknown>)._pathKey as string;
      return pa.localeCompare(pb);
    });

    // Build nested tree recursively
    type TreeNode = Record<string, unknown> & { _children?: TreeNode[] };

    function buildTree(rows: Record<string, unknown>[], depth: number): TreeNode[] {
      if (rows.length === 0) return [];

      // Group rows by their value at the current effective depth
      const groups: Record<string, { subtotal: Record<string, unknown> | null; children: Record<string, unknown>[] }> = {};
      const order: string[] = [];

      for (const r of rows) {
        const path = getPath(r);
        if (path.length <= depth) continue; // shouldn't happen

        const key = path[depth];
        if (!groups[key]) {
          groups[key] = { subtotal: null, children: [] };
          order.push(key);
        }

        if (path.length === depth + 1) {
          // This row's path ends here — it's the subtotal/parent for this group.
          // Multiple rows can end at the same depth when some row keys are "Total"
          // and others are NULL — both get filtered by getPath(). Prefer the row
          // with "Total" values (the real subtotal) over the null-detail row.
          const hasTotal = rowKeys.some(k => String(r[k]).toLowerCase() === "total");
          if (!groups[key].subtotal || hasTotal) {
            groups[key].subtotal = r;
          }
        } else {
          // This row goes deeper — it's a child
          groups[key].children.push(r);
        }
      }

      const result: TreeNode[] = [];
      for (const key of order) {
        const g = groups[key];
        // Use subtotal row as parent, or create a synthetic one from the first child
        const parent: TreeNode = g.subtotal
          ? { ...g.subtotal }
          : { ...g.children[0], _label: key };

        if (g.children.length > 0) {
          parent._children = buildTree(g.children, depth + 1);
        }

        result.push(parent);
      }

      return result;
    }

    const treeData = buildTree(dataRows, 0);

    options.data = treeData;
    options.dataTree = true;
    options.dataTreeStartExpanded = false;

    // Replace individual row key columns with a single "Label" column
    const labelCol: Record<string, unknown> = {
      title: "Label",
      field: "_label",
      frozen: true,
      width: 250,
      minWidth: 150,
      maxWidth: 400,
      headerSort: false,
      resizable: true,
      cssClass: "de-funk-row-label",
    };

    // Remove the row key columns, add the label column
    columnDefs = columnDefs.filter(c => {
      const field = (c as Record<string, unknown>).field as string | undefined;
      return !field || !rowKeys.includes(field);
    });
    columnDefs.unshift(labelCol);

    // Update options — the filter created a new array so the original reference is stale
    options.columns = columnDefs;
  }

  // Sorting — skip client-side sort when backend has subtotals anchored
  if (hasPivotCols && !hasSubtotals) {
    const lastCol = columns.filter(c => c.key.includes("||")).pop();
    if (lastCol) {
      options.initialSort = [{ column: lastCol.key, dir: "desc" }];
    }
  }

  // Create table
  const table = new Tabulator(gridDiv, options);

  // Add grand total rows to bottom after table renders
  if (totalRows.length > 0) {
    table.on("tableBuilt", () => {
      totalRows.forEach((r: Record<string, unknown>) => {
        // Set _label for tree mode where row key columns are hidden
        if (!r._label) r._label = "Total";
        table.addRow(r, false).then((row: { getElement: () => HTMLElement }) => {
          const el = row.getElement();
          el.style.backgroundColor = "rgba(128,128,128,0.15)";
          el.style.fontWeight = "600";
        });
      });
    });
  }

  // Copy-to-clipboard button
  const copyBtn = el.createEl("button", { text: "Copy Table", cls: "de-funk-download" });
  copyBtn.addEventListener("click", () => {
    table.copyToClipboard("active");
    copyBtn.setText("Copied!");
    setTimeout(() => copyBtn.setText("Copy Table"), 1500);
  });

  // Truncation warning
  if (response.truncated) {
    const warn = el.createDiv({ cls: "de-funk-truncation-warning" });
    warn.setText("Results were capped by the server row limit. Apply a filter to narrow the data.");
  }
}

/**
 * Render a pivot table using Tabulator.
 */
export function renderTabulatorPivot(
  block: DeFunkBlock,
  response: TableResponse,
  el: HTMLElement,
): void {
  renderTabulator(block, response, el);
}
