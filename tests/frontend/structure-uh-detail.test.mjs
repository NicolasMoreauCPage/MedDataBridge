import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";


test("UH deletion uses one accessible delegated dialog", () => {
  const template = readFileSync(
    new URL("../../app/templates/structure/uh_detail.html", import.meta.url),
    "utf8",
  );
  const source = readFileSync(
    new URL("../../app/static/js/structure-uh-detail.js", import.meta.url),
    "utf8",
  );
  assert.match(template, /role="dialog" aria-modal="true"/);
  assert.match(template, /data-delete-action=/);
  assert.match(template, /js\/structure-uh-detail\.js/);
  assert.doesNotMatch(template, /\bonclick=/);
  assert.match(source, /event\.key === "Escape"/);
  assert.match(source, /trigger\?\.focus\(\)/);
});
