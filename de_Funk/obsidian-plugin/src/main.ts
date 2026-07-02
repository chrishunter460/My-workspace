/**
 * de-funk Obsidian Plugin — main entry point.
 *
 * Registers:
 *   - de_funk code block processor
 *   - Filter sidebar (ItemView)
 *   - Settings tab
 */
import { Plugin } from "obsidian";
import { DEFAULT_SETTINGS, DeFunkSettingTab, type DeFunkSettings } from "./settings";
import { ApiClient } from "./api-client";
import { parseFrontmatter, parseFrontmatterFromText } from "./frontmatter";
import { clearPanels } from "./processors/config-panel";
import { createBlockProcessor } from "./processors/de-funk";
import { FilterSidebar, SIDEBAR_VIEW_TYPE } from "./filter-sidebar";
import { notifyFilterChanged, notifyControlChanged } from "./filter-bus";
import type { NoteFrontmatter } from "./frontmatter";

export default class DeFunkPlugin extends Plugin {
  settings: DeFunkSettings = DEFAULT_SETTINGS;
  private client!: ApiClient;
  private sidebar: FilterSidebar | null = null;
  private currentFrontmatter: NoteFrontmatter = { models: [], filters: {}, controls: [] };
  private _activeFilePath: string | null = null;
  private _suppressMetadataChange = false;

  async onload(): Promise<void> {
    await this.loadSettings();

    this.client = new ApiClient(this.settings);

    // Register settings tab
    this.addSettingTab(new DeFunkSettingTab(this.app, this));

    // Register sidebar view
    this.registerView(SIDEBAR_VIEW_TYPE, (leaf) => {
      this.sidebar = new FilterSidebar(
        leaf,
        this.client,
        this.handleFilterChange.bind(this),
        this.handleControlChange.bind(this),
      );
      return this.sidebar;
    });

    // Register de_funk code block processor
    this.registerMarkdownCodeBlockProcessor(
      "de_funk",
      createBlockProcessor(this.client, () => this.currentFrontmatter),
    );

    // Open sidebar on startup
    this.app.workspace.onLayoutReady(() => {
      this.activateSidebar();
    });

    // Clear control panels and update sidebar only when switching to a different file.
    // active-leaf-change fires on sidebar clicks too — when the sidebar is focused,
    // getActiveFile() returns null. Skip the clear in that case so controls keep working.
    this.registerEvent(
      this.app.workspace.on("active-leaf-change", () => {
        const file = this.app.workspace.getActiveFile();
        const path = file?.path ?? null;
        if (path !== null && path !== this._activeFilePath) {
          this._activeFilePath = path;
          clearPanels();
          this.updateFrontmatterFromActiveFile();
        }
      }),
    );

    // Re-render sidebar when frontmatter is edited in place (but not from our own writes)
    this.registerEvent(
      this.app.metadataCache.on("changed", (file) => {
        if (this._suppressMetadataChange) return;
        const activeFile = this.app.workspace.getActiveFile();
        if (activeFile && file.path === activeFile.path) {
          this.updateFrontmatterFromActiveFile();
          // Frontmatter changed (e.g. format codes) — re-render exhibits
          notifyControlChanged();
        }
      }),
    );

    // Add ribbon icon
    this.addRibbonIcon("bar-chart-2", "de-funk sidebar", () => {
      this.activateSidebar();
    });

    console.log("de-funk plugin loaded");
  }

  onunload(): void {
    this.app.workspace.detachLeavesOfType(SIDEBAR_VIEW_TYPE);
    clearPanels();
  }

  async loadSettings(): Promise<void> {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings(): Promise<void> {
    await this.saveData(this.settings);
    // Recreate client with updated settings
    this.client = new ApiClient(this.settings);
  }

  private updateFrontmatterFromActiveFile(): void {
    const activeFile = this.app.workspace.getActiveFile();
    if (!activeFile) return;

    // Read raw file to parse YAML ourselves — Obsidian's metadataCache
    // strips keys it doesn't recognise (context_filters, sort_by_measure, default, etc.)
    this.app.vault.cachedRead(activeFile).then((text) => {
      this._applyFrontmatter(parseFrontmatterFromText(text));
    });
  }

  private _applyFrontmatter(parsed: NoteFrontmatter): void {
    // Preserve in-memory filter selections when re-parsing the same note
    // (active-leaf-change fires on sidebar clicks, which would otherwise
    // reset currentValue back to the file default on every interaction)
    for (const [id, filter] of Object.entries(parsed.filters)) {
      const existing = this.currentFrontmatter.filters[id];
      if (existing !== undefined) {
        filter.currentValue = existing.currentValue;
      }
    }

    this.currentFrontmatter = parsed;
    this.sidebar?.updateFrontmatter(this.currentFrontmatter);
  }

  private handleControlChange(panelId: string, key: string, value: unknown): void {
    const activeFile = this.app.workspace.getActiveFile();
    if (!activeFile) return;

    this._suppressMetadataChange = true;
    this.app.fileManager.processFrontMatter(activeFile, (fm) => {
      const controls = fm["controls"];
      if (!Array.isArray(controls)) return;
      const ctrl = controls.find((c: Record<string, unknown>) => c["id"] === panelId);
      if (!ctrl) return;
      if (!ctrl["current"]) ctrl["current"] = {};
      ctrl["current"][key] = value;
    });
    // Reset suppression after Obsidian processes the write
    setTimeout(() => { this._suppressMetadataChange = false; }, 200);
  }

  private handleFilterChange(id: string, value: unknown): void {
    if (this.currentFrontmatter.filters[id]) {
      this.currentFrontmatter.filters[id].currentValue = value;
    }
    // Don't clearCache() here — filter changes produce new payloads that
    // naturally miss the cache. Clearing would force duplicate queries when
    // multiple exhibits re-render concurrently from the same bus notification.
    notifyFilterChanged();
    // Re-fetch any pickers that declared context_filters: true
    this.sidebar?.refreshContextFilters(id);
  }

  private async activateSidebar(): Promise<void> {
    const { workspace } = this.app;

    // If already open, just reveal it
    const existing = workspace.getLeavesOfType(SIDEBAR_VIEW_TYPE);
    if (existing.length > 0) {
      workspace.revealLeaf(existing[0]);
      return;
    }

    // Create a new leaf on the configured side
    const side = this.settings.sidebarPosition === "left" ? "left" : "right";
    const leaf = side === "left"
      ? workspace.getLeftLeaf(false)
      : workspace.getRightLeaf(false);

    if (leaf) {
      await leaf.setViewState({ type: SIDEBAR_VIEW_TYPE, active: true });
      workspace.revealLeaf(leaf);
    }

    this.updateFrontmatterFromActiveFile();
  }
}
