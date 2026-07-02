import esbuild from "esbuild";
import process from "process";
import builtins from "builtin-modules";

const prod = process.argv[2] === "production";

const context = await esbuild.context({
  entryPoints: ["src/main.ts"],
  bundle: true,
  loader: { ".css": "text" },
  external: [
    "obsidian",
    "electron",
    "@codemirror/autocomplete",
    "@codemirror/collab",
    "@codemirror/commands",
    "@codemirror/language",
    "@codemirror/lint",
    "@codemirror/search",
    "@codemirror/state",
    "@codemirror/view",
    "@lezer/common",
    "@lezer/highlight",
    "@lezer/lr",
    ...builtins,
  ],
  format: "cjs",
  target: "es2021",
  logLevel: "info",
  sourcemap: prod ? false : "inline",
  treeShaking: true,
  outfile: "main.js",
});

if (prod) {
  await context.rebuild();
  // Copy to Obsidian vault plugins directory
  const fs = await import("fs");
  const path = await import("path");
  const pluginDir = path.default.resolve("..", ".obsidian", "plugins", "de-funk");
  try {
    fs.default.copyFileSync("main.js", path.default.join(pluginDir, "main.js"));
    console.log(`Copied main.js → ${pluginDir}/main.js`);
    fs.default.copyFileSync("styles.css", path.default.join(pluginDir, "styles.css"));
    console.log(`Copied styles.css → ${pluginDir}/styles.css`);
  } catch { /* vault dir may not exist */ }
  process.exit(0);
} else {
  await context.watch();
}
