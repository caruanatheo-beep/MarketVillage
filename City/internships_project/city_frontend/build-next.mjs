// Bundles the new interface (src/next) into city_assets/next/app.js.
import { build } from "esbuild-wasm";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const base = dirname(fileURLToPath(import.meta.url));
await build({
  absWorkingDir: base,
  entryPoints: [resolve(base, "src/next/main.tsx")],
  outfile: resolve(base, "../city_assets/next/app.js"),
  bundle: true, minify: true, format: "iife", target: "es2020", logLevel: "info",
});
