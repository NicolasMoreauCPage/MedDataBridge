import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import test from "node:test";

test("frontend production assets stay within their documented budgets", () => {
  const output = execFileSync(process.execPath, ["scripts/check_frontend_budgets.mjs"], { encoding: "utf8" });
  assert.match(output, /Budgets frontend/);
});
