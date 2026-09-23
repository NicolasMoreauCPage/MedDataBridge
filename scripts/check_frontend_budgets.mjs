import { readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const JS_ROOT = resolve("app/static/js");
const CSS_BUNDLE = resolve("app/static/css/output.css");
const MAX_CSS_BYTES = 200 * 1024;
const MAX_PRODUCT_JS_BYTES = 400 * 1024;
const MAX_PRODUCT_ASSET_BYTES = 64 * 1024;
const MAX_VENDOR_ASSET_BYTES = 256 * 1024;

const assets = [];
function collect(directory) {
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) collect(path);
    else if (path.endsWith(".js")) assets.push(path);
  }
}

collect(JS_ROOT);
const failures = [];
const productAssets = assets.filter((path) => !path.endsWith(".min.js"));
const productJsBytes = productAssets.reduce((total, path) => total + statSync(path).size, 0);
const cssBytes = statSync(CSS_BUNDLE).size;

if (cssBytes > MAX_CSS_BYTES) {
  failures.push(`CSS généré : ${cssBytes} octets (budget ${MAX_CSS_BYTES}).`);
}
if (productJsBytes > MAX_PRODUCT_JS_BYTES) {
  failures.push(`JavaScript produit : ${productJsBytes} octets (budget ${MAX_PRODUCT_JS_BYTES}).`);
}
for (const path of assets) {
  const size = statSync(path).size;
  const limit = path.endsWith(".min.js") ? MAX_VENDOR_ASSET_BYTES : MAX_PRODUCT_ASSET_BYTES;
  if (size > limit) {
    failures.push(`${relative(JS_ROOT, path)} : ${size} octets (budget ${limit}).`);
  }
}

console.log(
  `Budgets frontend : CSS ${cssBytes}/${MAX_CSS_BYTES} octets ; JavaScript produit ${productJsBytes}/${MAX_PRODUCT_JS_BYTES} octets.`,
);
if (failures.length) {
  process.stderr.write(`Budgets dépassés :\n- ${failures.join("\n- ")}\n`);
  process.exitCode = 1;
}
