import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";


test("scenario EJ configuration externalizes searchable UF selects", () => {
  const template = readFileSync(
    new URL("../../app/templates/scenarios/ej_config_form.html", import.meta.url),
    "utf8",
  );
  const source = readFileSync(
    new URL("../../app/static/js/scenario-ej-config-form.js", import.meta.url),
    "utf8",
  );
  assert.match(template, /scenario-ej-config/);
  assert.match(template, /js\/scenario-ej-config-form\.js/);
  assert.doesNotMatch(template, /<script>([\s\S]*?)<\/script>/);
  assert.doesNotMatch(template, /<style>/);
  assert.match(source, /Math\.min\(10, select\.options\.length\)/);
});
