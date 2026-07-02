import type { App } from "obsidian";
import { PluginSettingTab, Setting } from "obsidian";
import type DeFunkPlugin from "./main";

export interface DeFunkSettings {
  serverUrl: string;
  apiKey: string;
  cacheTtlSeconds: number;
  sidebarPosition: "left" | "right";
}

export const DEFAULT_SETTINGS: DeFunkSettings = {
  serverUrl: "http://localhost:8765",
  apiKey: "",
  cacheTtlSeconds: 30,
  sidebarPosition: "right",
};

export class DeFunkSettingTab extends PluginSettingTab {
  plugin: DeFunkPlugin;

  constructor(app: App, plugin: DeFunkPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    containerEl.createEl("h2", { text: "de-funk Settings" });

    new Setting(containerEl)
      .setName("Server URL")
      .setDesc("URL of the de_funk FastAPI backend (run: python -m scripts.serve.run_api)")
      .addText((text) =>
        text
          .setPlaceholder("http://localhost:8765")
          .setValue(this.plugin.settings.serverUrl)
          .onChange(async (value) => {
            this.plugin.settings.serverUrl = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("API Key")
      .setDesc("Optional — set X-API-Key header if your server requires auth")
      .addText((text) =>
        text
          .setPlaceholder("(leave blank for local use)")
          .setValue(this.plugin.settings.apiKey)
          .onChange(async (value) => {
            this.plugin.settings.apiKey = value.trim();
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Cache TTL (seconds)")
      .setDesc("How long to cache query results. 0 = disable cache.")
      .addText((text) =>
        text
          .setValue(String(this.plugin.settings.cacheTtlSeconds))
          .onChange(async (value) => {
            const n = parseInt(value, 10);
            if (!isNaN(n) && n >= 0) {
              this.plugin.settings.cacheTtlSeconds = n;
              await this.plugin.saveSettings();
            }
          })
      );

    new Setting(containerEl)
      .setName("Sidebar position")
      .setDesc("Which side the filter/controls panel opens on")
      .addDropdown((drop) =>
        drop
          .addOption("left", "Left")
          .addOption("right", "Right")
          .setValue(this.plugin.settings.sidebarPosition)
          .onChange(async (value) => {
            this.plugin.settings.sidebarPosition = value as "left" | "right";
            await this.plugin.saveSettings();
          })
      );
  }
}
