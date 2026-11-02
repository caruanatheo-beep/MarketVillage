import { build } from "esbuild-wasm";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { checkLayout } from "./check-layout.mjs";

const base = dirname(fileURLToPath(import.meta.url));
try { await checkLayout(); }
catch (error) { console.error(`Layout validation failed: ${error.message}`); process.exit(1); }
await build({
  absWorkingDir: base,
  entryPoints: [resolve(base, "src/main.tsx")],
  outfile: resolve(base, "../city_assets/city.js"),
  bundle: true,
  minify: true,
  format: "iife",
  target: "es2020",
  logLevel: "info",
});
