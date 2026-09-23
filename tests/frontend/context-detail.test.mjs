import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";


test("endpoint context filters are external and scoped", () => {
  const template = readFileSync(
    new URL("../../app/templates/endpoint_detail.html", import.meta.url),
    "utf8",
  );
  const source = readFileSync(
    new URL("../../app/static/js/endpoint-detail-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(template, /js\/endpoint-detail-workspace\.js/);
  assert.doesNotMatch(template, /<script>([\s\S]*?)<\/script>/);
  assert.doesNotMatch(template, /<style>/);
  assert.match(source, /option\.hidden = !visible/);
});


test("GHT cloning uses an accessible delegated dialog", () => {
  const template = readFileSync(
    new URL("../../app/templates/ght_detail.html", import.meta.url),
    "utf8",
  );
  const source = readFileSync(
    new URL("../../app/static/js/ght-detail-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(template, /role="dialog" aria-modal="true"/);
  assert.match(template, /data-clone-base=/);
  assert.match(template, /js\/ght-detail-workspace\.js/);
  assert.doesNotMatch(template, /\bonclick=/);
  assert.match(source, /event\.key === "Escape"/);
  assert.match(source, /trigger\?\.focus\(\)/);
});
