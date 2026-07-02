/**
 * Deploy the built plugin to the Obsidian vault.
 *
 * Looks for the vault path in (in order):
 *   1. OBSIDIAN_VAULT env variable
 *   2. .vault-path file in the plugin directory
 *   3. Default: ~/PycharmProjects/de_Funk (the repo IS the vault)
 */
import { copyFileSync, mkdirSync, existsSync, readFileSync } from "fs";
import { join, resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

function getVaultPath() {
  if (process.env.OBSIDIAN_VAULT) {
    return process.env.OBSIDIAN_VAULT;
  }
  const vaultFile = join(__dirname, ".vault-path");
  if (existsSync(vaultFile)) {
    return readFileSync(vaultFile, "utf8").trim();
  }
  // Default: repo root is the vault
  return resolve(__dirname, "../..");
}

const vaultPath = getVaultPath();
const pluginDir = join(vaultPath, ".obsidian", "plugins", "de-funk");

mkdirSync(pluginDir, { recursive: true });

const files = ["main.js", "manifest.json", "styles.css"];
for (const file of files) {
  const src = join(__dirname, "..", file);
  if (existsSync(src)) {
    copyFileSync(src, join(pluginDir, file));
    console.log(`  Copied ${file} → ${pluginDir}`);
  }
}

console.log(`\nPlugin deployed to: ${pluginDir}`);
console.log("Reload Obsidian (Ctrl+R) to pick up changes.");
