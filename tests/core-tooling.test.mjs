import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("core repository-intelligence manifest exposes only approved tools", async () => {
  const manifest = JSON.parse(
    await readFile(new URL("../core-tooling.json", import.meta.url), "utf8"),
  );
  assert.deepEqual(
    manifest.tools.map((tool) => tool.id),
    ["graphify", "repomix"],
  );
  for (const tool of manifest.tools) {
    assert.match(tool.repository, /^https:\/\/github\.com\//);
    assert.ok(tool.install);
    assert.ok(tool.verify);
  }
  assert.equal(manifest.tools[0].version, "0.9.27");
  assert.equal(manifest.tools[0].install, "python scripts/bootstrap-graphify.py --install");
  assert.deepEqual(
    manifest.policy.rejected,
    ["aider", "serena", "context7", "code-review-graph"],
  );
});

test("core repository-intelligence guide documents all three agent integrations", async () => {
  const guide = await readFile(
    new URL("../CORE_REPOSITORY_INTELLIGENCE.md", import.meta.url),
    "utf8",
  );
  for (const name of ["Graphify", "Repomix", "Claude", "Codex", "Antigravity", "rejected"]) {
    assert.match(guide, new RegExp(name));
  }
});
