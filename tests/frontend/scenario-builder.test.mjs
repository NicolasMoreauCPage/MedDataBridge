import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../../app/static/js/scenario-builder.js", import.meta.url), "utf8");

test("scenario builder hides non-selected mode sections even when they use a layout class", () => {
  assert.match(source, /element\.hidden = !visible/);
  assert.match(source, /element\.style\.display = visible \? "" : "none"/);
});
