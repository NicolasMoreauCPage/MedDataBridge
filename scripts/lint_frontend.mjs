import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const roots = ["app/static/js", "scripts"];
const files = [];
const templates = [];

function collect(directory) {
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) collect(path);
    else if (path.endsWith(".js") || path.endsWith(".mjs")) files.push(path);
  }
}

for (const root of roots) collect(resolve(root));

function collectTemplates(directory) {
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) collectTemplates(path);
    else if (path.endsWith(".html")) templates.push(path);
  }
}

collectTemplates(resolve("app/templates"));

let failed = false;
for (const file of files) {
  const result = spawnSync(process.execPath, ["--check", file], { encoding: "utf8" });
  if (result.status !== 0) {
    failed = true;
    process.stderr.write(result.stderr || result.stdout);
  }
}

const directFetch = /\bawait\s+(?:window\.)?fetch\s*\(/;
for (const file of [...files, ...templates]) {
  if (file.endsWith("app/static/js/http.js")) continue;
  if (directFetch.test(readFileSync(file, "utf8"))) {
    failed = true;
    process.stderr.write(`Appel fetch direct interdit : ${file}\n`);
  }
}

// Les styles de page doivent vivre dans les feuilles partagées. Les blocs
// historiques restent explicitement recensés jusqu'à leur migration ; cette
// liste empêche qu'un nouveau template en ajoute un silencieusement.
const legacyTemplateStyleAllowlist = new Set([
  "app/templates/base.html",
  "app/templates/design_system_demo.html",
  "app/templates/documentation.html",
  "app/templates/endpoint_detail.html",
  "app/templates/patient_detail.html",
  "app/templates/scenarios/ej_config_form.html",
  "app/templates/scenarios_bulk_execute_v2.html",
  "app/templates/structure_interactive.html",
  "app/templates/structure_search.html",
]);

for (const template of templates) {
  if (!/<style(?:\s[^>]*)?>/i.test(readFileSync(template, "utf8"))) continue;
  const relativeTemplate = template.replace(`${resolve(".")}/`, "");
  if (legacyTemplateStyleAllowlist.has(relativeTemplate)) continue;
  failed = true;
  process.stderr.write(`Bloc <style> local non autorisé : ${relativeTemplate}\n`);
}

if (failed) process.exitCode = 1;
else console.log(`Syntaxe JavaScript vérifiée : ${files.length} fichiers ; client HTTP contrôlé dans ${templates.length} templates.`);
