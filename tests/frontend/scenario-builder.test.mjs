import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../../app/static/js/scenario-builder.js", import.meta.url), "utf8");

test("scenario builder hides non-selected mode sections even when they use a layout class", () => {
  assert.match(source, /element\.hidden = !visible/);
  assert.match(source, /element\.style\.display = visible \? "" : "none"/);
});

test("scenario builder warns before abandoning unsaved input and preserves native form redirects", () => {
  assert.match(source, /function bindUnsavedChanges\(form\)/);
  assert.match(source, /Quitter sans enregistrer les modifications/);
  assert.match(source, /beforeunload/);
});

test("scenario builder redirects direct navigation to the first missing prerequisite", () => {
  assert.match(source, /const goTo = \(target\) =>/);
  assert.match(source, /for \(let step = 2; step < target; step \+= 1\)/);
  assert.match(source, /show\(step\);/);
});
