---
title: "Obsidian Plugin"
last_updated: "2026-03-30"
status: "draft"
source_files:
  - obsidian-plugin/src/api-client.ts
  - obsidian-plugin/src/contract.ts
  - obsidian-plugin/src/filter-bus.ts
  - obsidian-plugin/src/filter-sidebar.ts
  - obsidian-plugin/src/frontmatter.ts
  - obsidian-plugin/src/main.ts
  - obsidian-plugin/src/processors/config-panel-renderer.ts
  - obsidian-plugin/src/processors/config-panel.ts
  - obsidian-plugin/src/processors/de-funk.ts
  - obsidian-plugin/src/render/format.ts
  - obsidian-plugin/src/render/graphical.ts
  - obsidian-plugin/src/render/metric-cards.ts
  - obsidian-plugin/src/render/pivot.ts
  - obsidian-plugin/src/render/scroll.ts
  - obsidian-plugin/src/render/tabular.ts
  - obsidian-plugin/src/resolver.ts
  - obsidian-plugin/src/settings.ts
---

# Obsidian Plugin

> TypeScript plugin that renders exhibit blocks in Obsidian notes by calling the FastAPI backend.

## Purpose & Design Decisions

### What Problem This Solves

Users define analytical exhibits (charts, tables, pivots, KPI cards) as YAML blocks inside Obsidian markdown notes. Without this plugin, those blocks are just inert code fences. The plugin bridges Obsidian's rendering engine and the de_funk Python backend by:

- **Parsing** `de_funk` code blocks from YAML into typed request payloads.
- **Resolving** note-level frontmatter filters and sidebar control state into the API request.
- **Calling** the FastAPI backend (`POST /api/query`) and dispatching responses to the correct renderer (Plotly charts, HTML tables, GT pivots, metric cards).
- **Providing** a sidebar with interactive filter pickers (select, date range, numeric range) and control panels (dimension/measure selectors, sort toggles) that drive live re-rendering.

The plugin follows a **reactive pub/sub** pattern: when a filter or control changes in the sidebar, a global event bus (`filter-bus.ts`) notifies all active exhibit blocks, each of which re-fetches and re-renders with the new state.

### Connection to Python Backend

The plugin calls these API endpoints:

| Endpoint | Plugin File | What It Does |
|----------|------------|-------------|
| `POST /api/query` | `api-client.ts` | Execute exhibit queries (charts, tables, metrics) |
| `GET /api/dimensions/{ref}` | `api-client.ts` | Populate filter sidebar dropdowns |
| `GET /api/domains` | `api-client.ts` | Discover available domains |
| `POST /api/bronze/query` | `api-client.ts` | Query Bronze layer directly |
| `GET /api/health` | `api-client.ts` | Health check on startup |

The `ApiClient` class handles auth headers (`X-API-Key`), response caching (TTL-based), and in-flight request deduplication (concurrent identical POST requests share one fetch promise).

## File Reference

| File | Purpose |
|------|---------|
| `api-client.ts` | HTTP client for the FastAPI backend -- handles GET/POST with caching, in-flight deduplication, auth headers, and typed API methods (`query`, `bronzeQuery`, `getDimensions`, `getDomains`, `health`) |
| `contract.ts` | TypeScript type definitions mirroring the Python API data contract (`FilterSpec`, `BlockData`, `DeFunkBlock`, `GraphicalResponse`, `TableResponse`, `GreatTablesResponse`, `MetricResponse`, `DimensionValuesResponse`) |
| `filter-bus.ts` | Global pub/sub event bus -- `subscribeToFilterChanges()` registers render callbacks, `notifyFilterChanged()` / `notifyControlChanged()` fire all subscribers when sidebar state changes |
| `filter-sidebar.ts` | Obsidian `ItemView` sidebar panel -- renders filter pickers (tag select with search, date range, numeric range) and control groups (checkbox lists, dropdowns, toggles) from note frontmatter |
| `frontmatter.ts` | Parses note YAML frontmatter into `NoteFrontmatter` (models, filters, controls) -- uses `js-yaml` directly to preserve keys that Obsidian's metadataCache strips (e.g. `context_filters`, `sort_by_measure`, `default`) |
| `main.ts` | Plugin entry point (`DeFunkPlugin extends Plugin`) -- registers code block processor, sidebar view, settings tab, ribbon icon; handles active-leaf-change and metadata-change events |
| `processors/config-panel-renderer.ts` | Renders inline `control.config` blocks with dropdowns, toggles, and checkboxes (legacy inline path; sidebar controls are now preferred) |
| `processors/config-panel.ts` | In-memory state store for control panels -- `registerPanel()`, `getState()`, `subscribe()`, `updateControl()`, `setControlSilent()`, `clearPanels()` |
| `processors/de-funk.ts` | Main code block processor -- parses YAML, dispatches to the correct renderer based on block type (graphical, table.data, table.pivot, cards.metric, control.config), subscribes to filter bus for re-rendering |
| `render/format.ts` | Value formatter for display -- supports format codes `$`, `$K`, `$M`, `%`, `%2`, `number`, `decimal`, `decimal2`, `date`, `text` |
| `render/graphical.ts` | Plotly.js renderer for chart types (line, bar, scatter, area, pie, heatmap, box, candlestick/OHLCV) -- auto-detects Obsidian dark/light theme for colors |
| `render/metric-cards.ts` | Renders `cards.metric` exhibits as a CSS grid of KPI cards with formatted values and labels |
| `render/pivot.ts` | Renders `table.pivot` / `great_table` exhibits -- handles both flat GT HTML injection and expandable hierarchical pivots with click-to-expand subtotal rows |
| `render/scroll.ts` | Shared scroll utility -- `applyViewport()` sets a bounded max-height scroll container with `!important` styles to override Obsidian/GT CSS |
| `render/tabular.ts` | Renders `table.data` exhibits as HTML tables with pagination, CSV download, and optional Great Tables HTML injection |
| `resolver.ts` | Translates parsed YAML blocks + note filters + control state into API request payloads -- handles `page_filters` ignore rules, inline `data.filters`, control state overrides (dimensions->rows/group_by, measures->y/measures), and tuple normalization |
| `settings.ts` | Plugin settings UI -- `DeFunkSettings` interface (`serverUrl`, `apiKey`, `cacheTtlSeconds`, `sidebarPosition`) with `DeFunkSettingTab` for the Obsidian settings panel |

## How to Use

### Block Syntax

See [docs/obsidian-plugin.md](../obsidian-plugin.md) for full block syntax reference.

### Plugin Settings

Configure the plugin in Obsidian Settings > de-funk:

| Setting | Default | Description |
|---------|---------|-------------|
| Server URL | `http://localhost:8765` | URL of the running FastAPI backend |
| API Key | (blank) | Optional `X-API-Key` header for authenticated deployments |
| Cache TTL | 30 seconds | How long to cache query results; 0 disables caching |
| Sidebar position | right | Which side the filter/controls panel opens on |

### Data Flow

1. User opens a note with `de_funk` code blocks and frontmatter filters/controls.
2. `main.ts` parses the frontmatter via `frontmatter.ts` (using `js-yaml` for full key preservation).
3. The sidebar renders filter pickers and control groups from the parsed frontmatter.
4. Each `de_funk` code block is processed by `processors/de-funk.ts`:
   - Parse YAML via `resolver.ts:parseBlock()`.
   - Build API request via `resolver.ts:buildRequest()` with note filters + control state.
   - Call `client.query()` or `client.bronzeQuery()`.
   - Dispatch response to the appropriate renderer.
5. When a filter/control changes in the sidebar, `filter-bus.ts` fires all subscribers.
6. Each exhibit re-runs its render closure (re-reads fresh control state, re-builds payload, re-fetches).

## Triage & Debugging

### Symptom Table

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Block shows "Query error: GET /api/health -> 0: Failed to fetch" | Backend server not running | Start the API server: `python -m scripts.serve.run_api` |
| Block shows "Query error: POST /api/query -> 500: ..." | Backend query execution failed (bad SQL, missing table) | Check the Python server logs (`logs/de_funk.log`) for the full traceback |
| Block shows "Parse error: de_funk block must be valid YAML" | Malformed YAML in the code block | Check indentation, colons, and quoting in the block YAML |
| Block shows "Parse error: de_funk block requires a 'type:' field" | Missing `type:` key in the block | Add `type: plotly.line` (or `table.data`, `table.pivot`, `cards.metric`, etc.) |
| Block shows "No renderer for 'X'" | Unrecognized block type | Use a supported type: `plotly.line`, `plotly.bar`, `table.data`, `table.pivot`, `cards.metric`, etc. |
| Sidebar shows "Open a note with de_funk filters or controls." | Active note has no `filters:` or `controls:` in frontmatter | Add filter/control definitions to the note's YAML frontmatter |
| Filter dropdown shows "Error loading values" | `GET /api/dimensions/{ref}` failed | Check that the domain.field reference in the filter `source:` is valid and the backend is running |
| Chart renders with wrong theme colors (dark text on dark background) | Obsidian theme class detection failed | The plugin checks `document.body.classList.contains("theme-dark")`; ensure your theme adds this class |
| Exhibits do not update when filter changes | Filter bus subscription was lost | This can happen if Obsidian re-renders the block DOM; the unsubscribe cleanup runs on unmount, but if the block element is reused stale callbacks may accumulate. Refresh the note (Ctrl+E toggle or reopen). |
| Stale data after backend changes | Response cache not expired | Click the sidebar Refresh button, or set Cache TTL to 0 in settings |
| Frontmatter keys like `context_filters` or `sort_by_measure` are ignored | Obsidian's metadataCache strips unrecognized keys | This should not happen -- the plugin uses `parseFrontmatterFromText()` which parses raw YAML via `js-yaml`. If it does, check that the frontmatter YAML is valid (no tabs, correct indentation). |
| Control changes not reflected in exhibits | Block missing `config_ref:` or panel ID mismatch | Ensure the exhibit block has `config: { config_ref: "controls" }` matching the control `id:` in frontmatter |
| Exhibit renders in Reading View but not Live Preview | Live Preview intentionally skipped | The processor checks for `.markdown-source-view` ancestor and returns early. Switch to Reading View to see rendered exhibits. |
