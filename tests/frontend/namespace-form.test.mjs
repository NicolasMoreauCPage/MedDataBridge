import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";


test("namespace forms share OID extraction and prefix mode behavior", () => {
  const generic = readFileSync(
    new URL("../../app/templates/namespace_form.html", import.meta.url),
    "utf8",
  );
  const ej = readFileSync(
    new URL("../../app/templates/ej_namespace_form.html", import.meta.url),
    "utf8",
  );
  const source = readFileSync(
    new URL("../../app/static/js/namespace-form-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(generic, /js\/namespace-form-workspace\.js/);
  assert.match(ej, /js\/namespace-form-workspace\.js/);
  assert.doesNotMatch(generic + ej, /<script>([\s\S]*?)<\/script>/);
  assert.doesNotMatch(generic, /\bonchange=/);
  assert.match(source, /value\.startsWith\("urn:oid:"\)/);
  assert.match(source, /prefixMode\.addEventListener\("change"/);
});
