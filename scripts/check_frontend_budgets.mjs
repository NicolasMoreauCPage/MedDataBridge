import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const JS_ROOT = resolve("app/static/js");
const CSS_ROOT = resolve("app/static/css");
const CSS_BUNDLE = resolve("app/static/css/output.css");
const MAX_CSS_BYTES = 200 * 1024;
const MAX_PRODUCT_CSS_BYTES = 240 * 1024;
const MAX_CSS_ASSET_BYTES = 64 * 1024;
const MAX_PRODUCT_JS_BYTES = 420 * 1024;
const MAX_PRODUCT_ASSET_BYTES = 64 * 1024;
const MAX_VENDOR_ASSET_BYTES = 256 * 1024;
const MAX_SCREEN_PRODUCT_JS_BYTES = 128 * 1024;

function collect(directory, extension) {
  const matches = [];
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) matches.push(...collect(path, extension));
    else if (path.endsWith(extension)) matches.push(path);
  }
  return matches;
}

function scriptAssets(templatePath) {
  const content = readFileSync(templatePath, "utf8");
  const pattern = /(?:\/static\/|path=['"]\/?)(js\/[^'"?#\s]+\.js)/g;
  return [...content.matchAll(pattern)].map((match) => match[1]);
}

const assets = collect(JS_ROOT, ".js");
const cssAssets = collect(CSS_ROOT, ".css");
const templates = collect(resolve("app/templates"), ".html");
const failures = [];
const productAssets = assets.filter((path) => !path.endsWith(".min.js"));
const productJsBytes = productAssets.reduce((total, path) => total + statSync(path).size, 0);
const cssBytes = statSync(CSS_BUNDLE).size;
const productCssBytes = cssAssets.reduce((total, path) => total + statSync(path).size, 0);

if (cssBytes > MAX_CSS_BYTES) {
  failures.push(`CSS généré : ${cssBytes} octets (budget ${MAX_CSS_BYTES}).`);
}
if (productCssBytes > MAX_PRODUCT_CSS_BYTES) {
  failures.push(`CSS produit : ${productCssBytes} octets (budget ${MAX_PRODUCT_CSS_BYTES}).`);
}
for (const path of cssAssets.filter((path) => path !== CSS_BUNDLE)) {
  const size = statSync(path).size;
  if (size > MAX_CSS_ASSET_BYTES) {
    failures.push(`${relative(CSS_ROOT, path)} : ${size} octets (budget ${MAX_CSS_ASSET_BYTES}).`);
  }
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

const jsAssetSizes = new Map(
  assets.map((path) => [`js/${relative(JS_ROOT, path).replaceAll("\\\\", "/")}`, statSync(path).size]),
);
const sharedAssets = scriptAssets(resolve("app/templates/base.html"));
const screenBudgets = templates
  .filter((path) => !path.endsWith("/base.html"))
  .map((path) => {
    const content = readFileSync(path, "utf8");
    const pageAssets = content.includes('{% extends "base.html" %}')
      ? [...sharedAssets, ...scriptAssets(path)]
      : scriptAssets(path);
    const uniqueAssets = [...new Set(pageAssets)];
    const bytes = uniqueAssets
      .filter((asset) => !asset.endsWith(".min.js"))
      .reduce((total, asset) => total + (jsAssetSizes.get(asset) || 0), 0);
    return { template: relative(resolve("app/templates"), path), bytes };
  })
  .sort((left, right) => right.bytes - left.bytes);
for (const screen of screenBudgets) {
  if (screen.bytes > MAX_SCREEN_PRODUCT_JS_BYTES) {
    failures.push(
      `Écran ${screen.template} : ${screen.bytes} octets de JavaScript produit (budget ${MAX_SCREEN_PRODUCT_JS_BYTES}).`,
    );
  }
}

console.log(
  `Budgets frontend : bundle CSS ${cssBytes}/${MAX_CSS_BYTES} octets ; CSS total ${productCssBytes}/${MAX_PRODUCT_CSS_BYTES} octets ; JavaScript produit ${productJsBytes}/${MAX_PRODUCT_JS_BYTES} octets.`,
);
console.log(
  `Budgets par écran : ${screenBudgets.length} templates mesurés ; maximum ${screenBudgets[0]?.bytes || 0}/${MAX_SCREEN_PRODUCT_JS_BYTES} octets (${screenBudgets[0]?.template || "—"}).`,
);
if (failures.length) {
  process.stderr.write(`Budgets dépassés :\n- ${failures.join("\n- ")}\n`);
  process.exitCode = 1;
}
