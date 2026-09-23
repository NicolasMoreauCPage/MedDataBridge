import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const root = new URL("../../app/templates/", import.meta.url);
const allowedLegacyStyleBlocks = new Set([
  "base.html",
  "design_system_demo.html",
  "documentation.html",
  "patient_detail.html",
  "scenarios_bulk_execute_v2.html",
  "structure_interactive.html",
  "structure_search.html",
]);

function collectTemplates(directory, prefix = "") {
  return readdirSync(directory).flatMap((entry) => {
    const path = join(directory, entry);
    const relative = join(prefix, entry);
    return statSync(path).isDirectory()
      ? collectTemplates(path, relative)
      : relative.endsWith(".html") ? [relative] : [];
  });
}

test("new templates cannot introduce local style blocks", () => {
  const templateDirectory = root.pathname;
  const styledTemplates = collectTemplates(templateDirectory).filter((relative) =>
    /<style(?:\s[^>]*)?>/i.test(readFileSync(join(templateDirectory, relative), "utf8")),
  );
  assert.deepEqual(styledTemplates.sort(), [...allowedLegacyStyleBlocks].sort());
});

test("migrated workspaces use prefixed design-system components", () => {
  const css = readFileSync(new URL("../../app/static/css/design-system.css", import.meta.url), "utf8");
  const analytics = readFileSync(new URL("../../app/templates/analytics_dashboard.html", import.meta.url), "utf8");
  const hprim = readFileSync(new URL("../../app/templates/hprim/messages_dashboard.html", import.meta.url), "utf8");
  const base = readFileSync(new URL("../../app/templates/base.html", import.meta.url), "utf8");

  assert.match(css, /\.analytics-kpi-card/);
  assert.match(css, /\.hprim-messages-shell/);
  assert.match(analytics, /analytics-kpi-card/);
  assert.doesNotMatch(analytics, /<style/i);
  assert.match(hprim, /hprim-messages-shell/);
  assert.doesNotMatch(hprim, /<style/i);
  assert.doesNotMatch(base, /href="\/design-system"/);
});

test("shell and documentation templates keep executable JavaScript in dedicated assets", () => {
  const cases = [
    ["base.html", "theme-preflight.js"],
    ["design_system_demo.html", "design-system-demo.js"],
    ["documentation.html", "documentation.js"],
    ["standards_docs.html", "standards-docs.js"],
  ];

  cases.forEach(([templateName, assetName]) => {
    const template = readFileSync(new URL(templateName, root), "utf8");
    assert.match(template, new RegExp(assetName.replace(".", "\\.")));
    assert.doesNotMatch(template, /<script>/);
  });

  const demo = readFileSync(new URL("design_system_demo.html", root), "utf8");
  assert.doesNotMatch(demo, /\bonclick=/);
});
