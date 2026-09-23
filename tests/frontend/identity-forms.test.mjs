import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";


test("patient identity forms share validation behaviors", () => {
  const change = readFileSync(
    new URL("../../app/templates/patient_change_identifier_form.html", import.meta.url),
    "utf8",
  );
  const merge = readFileSync(
    new URL("../../app/templates/patient_merge_form.html", import.meta.url),
    "utf8",
  );
  const source = readFileSync(
    new URL("../../app/static/js/patient-identity-actions.js", import.meta.url),
    "utf8",
  );
  assert.match(change, /data-patient-identifier-change/);
  assert.match(merge, /data-patient-merge/);
  assert.match(change, /js\/patient-identity-actions\.js/);
  assert.match(merge, /js\/patient-identity-actions\.js/);
  assert.doesNotMatch(change + merge, /<script>([\s\S]*?)<\/script>/);
  assert.match(source, /aria-invalid/);
});


test("contact association behavior is external and guarded", () => {
  const template = readFileSync(
    new URL("../../app/templates/contact_form.html", import.meta.url),
    "utf8",
  );
  const source = readFileSync(
    new URL("../../app/static/js/contact-form-workspace.js", import.meta.url),
    "utf8",
  );
  assert.match(template, /js\/contact-form-workspace\.js/);
  assert.doesNotMatch(template, /<script>([\s\S]*?)<\/script>/);
  assert.match(source, /if \(!type \|\| !patient \|\| !venue\) return/);
  assert.match(source, /patient\.required = isPatient/);
});
