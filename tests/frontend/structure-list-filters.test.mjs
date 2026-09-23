import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";


const templates = [
  "eg_list.html",
  "poles_list.html",
  "services_list.html",
  "ufs.html",
  "uh.html",
  "lits_list.html",
  "chambres_list.html",
];


test("structure lists share one declarative filter workspace", () => {
  for (const name of templates) {
    const source = readFileSync(
      new URL(`../../app/templates/structure/${name}`, import.meta.url),
      "utf8",
    );
    assert.match(source, /data-structure-list data-filter-base=/, name);
    assert.match(source, /data-filter-param=/, name);
    assert.match(source, /js\/structure-list-filters\.js/, name);
    assert.doesNotMatch(source, /\bon(change|keydown|click)=/, name);
    assert.doesNotMatch(source, /function apply(?:Uf)?Filters/, name);
  }
});


test("shared filters preserve named query parameters", () => {
  const source = readFileSync(
    new URL("../../app/static/js/structure-list-filters.js", import.meta.url),
    "utf8",
  );
  assert.match(source, /new URLSearchParams/);
  assert.match(source, /control\.dataset\.filterParam/);
  assert.match(source, /event\.key !== "Enter"/);
  assert.match(source, /window\.location\.assign/);
});
