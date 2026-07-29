import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

async function exists(relativePath) {
  await access(new URL(relativePath, root));
}

test("capability inventory covers the current platform surface", async () => {
  const inventory = JSON.parse(
    await readFile(new URL("../capability-inventory.json", import.meta.url), "utf8"),
  );

  assert.deepEqual(inventory.counts, {
    plugins: 19,
    claudeSkills: 80,
    claudeCommands: 126,
    codexSkillFiles: 185,
  });
  assert.equal(inventory.plugins.length, inventory.counts.plugins);

  for (const plugin of inventory.plugins) {
    assert.equal(plugin.skillImplementationIdeas.length, plugin.claude.skills.length);
    assert.equal(plugin.commandImplementationIdeas.length, plugin.claude.commands.length);
    for (const skill of plugin.claude.skills) {
      await exists(`platforms/claude/plugins/${plugin.name}/skills/${skill}`);
      await exists(`platforms/antigravity/plugins/${plugin.name}/skills/${skill}`);
    }
    for (const command of plugin.claude.commands) {
      await exists(`platforms/claude/plugins/${plugin.name}/commands/${command}`);
      await exists(`platforms/antigravity/plugins/${plugin.name}/commands/${command}`);
    }
  }
});

test("learned capability routing is available on every platform", async () => {
  await exists("capability-inventory.json");
  await exists("CAPABILITY_ROADMAP.md");
  await exists("platforms/claude/plugins/project/skills/capability-routing/SKILL.md");
  await exists("platforms/claude/plugins/project/commands/capability-map.md");
  await exists("platforms/codex/plugins/project/skills/capability-routing/SKILL.md");
  await exists("platforms/codex/plugins/project/skills/capability-routing/agents/openai.yaml");
  await exists("platforms/antigravity/plugins/project/skills/capability-routing/SKILL.md");
  await exists("platforms/antigravity/plugins/project/commands/capability-map.md");
});
