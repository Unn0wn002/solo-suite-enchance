import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import { gzipSync } from "node:zlib";
import path from "node:path";
import test from "node:test";

/**
 * Transfer-size budget enforcement.
 *
 * Audit #2 scored performance engineering 25/100 because nothing in this
 * repository measured anything — `performance-optimization`, `/webperf`, and
 * `site-doctor:perf` all existed, but a skill with no instrument produces
 * advice, not evidence. This test is the instrument.
 *
 * Deliberately dependency-free: Node's own `zlib` gives real gzip sizes, so
 * this adds measurement without adding `size-limit`, `bundlesize`, or a
 * headless browser to the supply chain. Per AGENTS.md's tooling rule, an
 * existing capability was extended rather than a new dependency introduced.
 *
 * Scope limit, stated so a passing run is not over-read: this measures bytes
 * over the wire. It says nothing about LCP, INP, or CLS — those still have no
 * measurement here (MASTER_AUDIT.md H-1).
 */

const assetsDir = new URL("../dist/client/assets/", import.meta.url);
const budgetFile = new URL("../performance-budget.json", import.meta.url);

const kb = (bytes) => `${(bytes / 1024).toFixed(1)} KB`;

async function measure() {
  const names = await readdir(assetsDir);
  const totals = { js: 0, css: 0, largest: 0, largestName: "", files: 0 };

  for (const name of names) {
    const ext = path.extname(name);
    if (ext !== ".js" && ext !== ".css") continue;

    const gzipBytes = gzipSync(await readFile(new URL(name, assetsDir))).byteLength;
    totals[ext === ".js" ? "js" : "css"] += gzipBytes;
    totals.files += 1;
    if (gzipBytes > totals.largest) {
      totals.largest = gzipBytes;
      totals.largestName = name;
    }
  }

  return totals;
}

test("client bundle stays within the declared transfer-size budget", async () => {
  const { budgets } = JSON.parse(await readFile(budgetFile, "utf8"));
  const measured = await measure();

  // A build that emitted nothing would otherwise pass every budget below.
  assert.ok(
    measured.files > 0,
    `no .js/.css assets found in dist/client/assets — run \`npm run build\` first`,
  );

  const checks = [
    ["JS (gzip)", measured.js, budgets.jsGzipBytes],
    ["CSS (gzip)", measured.css, budgets.cssGzipBytes],
    ["total (gzip)", measured.js + measured.css, budgets.totalGzipBytes],
    [`largest file (gzip, ${measured.largestName})`, measured.largest, budgets.largestFileGzipBytes],
  ];

  // Report every measurement, not just failures — the numbers are the point.
  for (const [label, actual, budget] of checks) {
    const headroom = (((budget - actual) / budget) * 100).toFixed(1);
    console.log(`    ${label}: ${kb(actual)} / ${kb(budget)} budget (${headroom}% headroom)`);
  }

  for (const [label, actual, budget] of checks) {
    assert.ok(
      actual <= budget,
      `${label} is ${kb(actual)}, over the ${kb(budget)} budget by ${kb(actual - budget)}. ` +
        `See performance-budget.json's "whenExceeded" before raising the budget.`,
    );
  }
});
