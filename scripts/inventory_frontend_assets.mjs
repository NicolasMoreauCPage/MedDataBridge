import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const root = resolve("app/static/js");
const templatesRoot = resolve("app/templates");
const assets = [];
const templateSources = [];

function collect(directory, extension, target) {
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) collect(path, extension, target);
    else if (path.endsWith(extension)) target.push(path);
  }
}

collect(root, ".js", assets);
collect(templatesRoot, ".html", templateSources);

const references = new Set();
const assetPatterns = [
  /\/static\/js\/([^"'?#\s]+\.js)/g,
  /path=['"]\/?js\/([^"'?#\s]+\.js)/g,
];
for (const template of templateSources) {
  const content = readFileSync(template, "utf8");
  for (const pattern of assetPatterns) {
    for (const match of content.matchAll(pattern)) references.add(match[1]);
  }
}

const referenced = [];
const unreferenced = [];
for (const asset of assets) {
  const name = relative(root, asset).replaceAll("\\", "/");
  (references.has(name) ? referenced : unreferenced).push(name);
}

console.log(`Assets JavaScript : ${assets.length}; référencés par les templates : ${referenced.length}; à examiner : ${unreferenced.length}.`);
if (unreferenced.length) {
  console.log("Assets non référencés par un template (peuvent être chargés dynamiquement) :");
  for (const asset of unreferenced) console.log(`- ${asset}`);
  process.exitCode = 1;
}
