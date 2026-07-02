/**
 * Render graphical exhibits (plotly.*) using Plotly.js.
 */
import type { DeFunkBlock, GraphicalResponse } from "../contract";
// eslint-disable-next-line @typescript-eslint/no-require-imports
const Plotly = require("plotly.js-dist-min") as {
  newPlot: (el: HTMLElement, data: unknown[], layout: unknown, config?: unknown) => Promise<void>;
};

export async function renderGraphical(
  block: DeFunkBlock,
  response: GraphicalResponse,
  el: HTMLElement,
): Promise<void> {
  const { type, formatting = {} } = block;
  const height = formatting.height ?? 400;
  const showLegend = formatting.show_legend ?? true;
  const title = formatting.title ?? "";

  if (!response.series?.length) {
    el.createDiv({ cls: "de-funk-empty" }).setText("No data returned. Check filters or field references.");
    return;
  }

  const chartEl = el.createDiv({ cls: "de-funk-chart" });
  chartEl.style.height = `${height}px`;

  // Detect Obsidian's current theme mode to pick readable text/grid colours
  const isDark = document.body.classList.contains("theme-dark");
  const textColor  = isDark ? "#d4d4d4" : "#333333";
  const gridColor  = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.08)";
  const paperColor = "rgba(0,0,0,0)";  // always transparent

  const traces = buildTraces(type, response, formatting);
  const layout  = buildLayout(title, height, showLegend, formatting, textColor, gridColor, paperColor);

  try {
    await Plotly.newPlot(chartEl, traces, layout, { responsive: true, displayModeBar: false });
  } catch (err) {
    chartEl.setText(`Plotly render error: ${err}`);
  }

  if (response.truncated) {
    const warn = el.createDiv({ cls: "de-funk-truncation-warning" });
    warn.setText("Results were capped by the server response size limit. Apply a filter to narrow the data.");
  }
}

function buildTraces(
  type: string,
  response: GraphicalResponse,
  formatting: DeFunkBlock["formatting"],
): unknown[] {
  const plotlyType = mapType(type);

  if (type === "plotly.pie" || type === "pie") {
    const [s] = response.series;
    return [{ type: "pie", labels: s?.x, values: s?.y, hole: formatting?.hole ?? 0 }];
  }

  if (type === "plotly.box" || type === "box" || type === "ohlcv" || type === "candlestick") {
    const rawRows = response.series as unknown as unknown[][];
    const meta = response as unknown as { mode?: string; grouped?: boolean };
    const isOhlcv = meta.mode === "ohlcv";
    const isGrouped = meta.grouped === true;
    const isCandlestick = type === "candlestick" || type === "ohlcv";
    const traceType = formatting?.box_mode === "violin" ? "violin" : "box";

    // Row layout:
    //   OHLCV:           [category, open, high, low, close]
    //   OHLCV + group:   [category, open, high, low, close, grp]
    //   generic:         [category, y]
    //   generic + group: [category, y, grp]
    const grpIdx = isOhlcv ? 5 : 2;

    if (isGrouped) {
      // Split rows by group → one trace per group
      const groups = new Map<string, unknown[][]>();
      for (const row of rawRows) {
        const grp = String(row[grpIdx]);
        if (!groups.has(grp)) groups.set(grp, []);
        groups.get(grp)!.push(row);
      }

      return [...groups.entries()].map(([grp, rows]) => {
        if (isOhlcv && isCandlestick) {
          return {
            type: "candlestick", name: grp,
            x: rows.map((r) => String(r[0])),
            open: rows.map((r) => r[1]), high: rows.map((r) => r[2]),
            low: rows.map((r) => r[3]), close: rows.map((r) => r[4]),
          };
        }
        if (isOhlcv) {
          const xs: string[] = []; const ys: number[] = [];
          for (const r of rows) {
            const cat = String(r[0]);
            xs.push(cat, cat, cat, cat);
            ys.push(r[1] as number, r[2] as number, r[3] as number, r[4] as number);
          }
          return { type: traceType, name: grp, x: xs, y: ys };
        }
        return {
          type: traceType, name: grp,
          x: rows.map((r) => String(r[0])), y: rows.map((r) => r[1] as number),
        };
      });
    }

    // Ungrouped
    if (isOhlcv && isCandlestick) {
      return [{
        type: "candlestick",
        x: rawRows.map((r) => String(r[0])),
        open: rawRows.map((r) => r[1]), high: rawRows.map((r) => r[2]),
        low: rawRows.map((r) => r[3]), close: rawRows.map((r) => r[4]),
      }];
    }
    if (isOhlcv) {
      const xs: string[] = []; const ys: number[] = [];
      for (const r of rawRows) {
        const cat = String(r[0]);
        xs.push(cat, cat, cat, cat);
        ys.push(r[1] as number, r[2] as number, r[3] as number, r[4] as number);
      }
      return [{ type: traceType, x: xs, y: ys }];
    }
    return [{
      type: traceType,
      x: rawRows.map((r) => String(r[0])), y: rawRows.map((r) => r[1] as number),
    }];
  }

  if (type === "plotly.heatmap" || type === "heatmap") {
    const s = response.series;
    const xs = [...new Set(s.flatMap((r) => r.x))];
    const ys = s.map((r) => r.name);
    const zs = s.map((r) => r.y);
    return [{ type: "heatmap", x: xs, y: ys, z: zs, colorscale: formatting?.color_scale ?? "Blues" }];
  }

  return response.series.map((s) => {
    const trace: Record<string, unknown> = {
      type: plotlyType,
      name: s.name,
      x: s.x,
      y: s.y,
    };

    if (type === "plotly.area" || type === "area") {
      trace["fill"] = formatting?.fill ?? "tozeroy";
      trace["opacity"] = formatting?.opacity ?? 0.4;
    }
    if (type === "plotly.scatter" || type === "scatter") {
      trace["mode"] = "markers";
      trace["marker"] = { size: formatting?.marker_size ?? 8, opacity: formatting?.opacity ?? 0.7 };
    }
    if (type === "plotly.line" || type === "line" || type === "line_chart") {
      trace["mode"] = formatting?.markers ? "lines+markers" : "lines";
      trace["line"] = { shape: formatting?.line_shape ?? "linear" };
    }
    if (type === "plotly.bar" || type === "bar") {
      trace["orientation"] = formatting?.orientation ?? "v";
    }
    if (type === "plotly.box" || type === "box" || type === "ohlcv") {
      trace["type"] = formatting?.box_mode === "violin" ? "violin" : "box";
    }
    return trace;
  });
}

function buildLayout(
  title: string,
  height: number,
  showLegend: boolean,
  formatting: DeFunkBlock["formatting"],
  textColor: string,
  gridColor: string,
  paperColor: string,
): unknown {
  return {
    title: { text: title, font: { size: 14, color: textColor } },
    height,
    showlegend: showLegend,
    barmode: formatting?.barmode ?? "group",
    paper_bgcolor: paperColor,
    plot_bgcolor: paperColor,
    font: { color: textColor },
    xaxis: { gridcolor: gridColor, zerolinecolor: gridColor, color: textColor },
    yaxis: { gridcolor: gridColor, zerolinecolor: gridColor, color: textColor },
    margin: { l: 50, r: 20, t: title ? 40 : 20, b: 50 },
  };
}

function mapType(type: string): string {
  const map: Record<string, string> = {
    "plotly.line": "scatter",
    "line": "scatter",
    "line_chart": "scatter",
    "plotly.bar": "bar",
    "bar": "bar",
    "bar_chart": "bar",
    "plotly.scatter": "scatter",
    "scatter": "scatter",
    "plotly.area": "scatter",
    "area": "scatter",
    "plotly.box": "box",
    "box": "box",
    "ohlcv": "box",
  };
  return map[type] ?? "scatter";
}
