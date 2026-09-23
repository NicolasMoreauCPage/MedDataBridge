import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";


const template = readFileSync(
  new URL("../../app/templates/admission_wizard.html", import.meta.url),
  "utf8",
);
const workspace = readFileSync(
  new URL("../../app/static/js/admission-wizard-workspace.js", import.meta.url),
  "utf8",
);


test("the admission wizard delegates location loading to its workspace", () => {
  assert.match(template, /admission-wizard-workspace\.js/);
  assert.doesNotMatch(template, /<script>(.|\n)*medbridgeHttp/);
  assert.match(workspace, /window\.medbridgeHttp\.get/);
  assert.match(workspace, /if \(!serviceSelect \|\| !ufSelect \|\| !bedSelector \|\| !bedInput\) return/);
});


test("dynamic bed choices expose selection and loading feedback", () => {
  assert.match(template, /id="lit_selector"[^>]+aria-live="polite"/);
  assert.match(workspace, /aria-pressed/);
  assert.match(workspace, /Recherche des lits disponibles/);
  assert.match(workspace, /Impossible de charger les lits disponibles/);
  assert.doesNotMatch(workspace, /\.innerHTML\s*=/);
});
