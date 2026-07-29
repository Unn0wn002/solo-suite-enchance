import { readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const root = resolve(process.argv[2] || ".");
const canonicalPath = join(root, "platforms", "claude", "parity", "capabilities.json");
const manifest = JSON.parse(readFileSync(canonicalPath, "utf8"));

const commandMap = manifest.commands.map((item) => ({
  legacy_invocation: item.legacy_invocation,
  skill_invocation: item.skill_invocation,
  codex_invocation: item.codex_invocation,
  plugin: item.plugin,
  command: item.command,
  skill_name: item.skill_name,
  source_path: item.source_path,
  target_path: item.target_path,
  allow_implicit_invocation: item.allow_implicit_invocation,
}));

writeFileSync(
  join(root, "platforms", "codex", "command-map.json"),
  `${JSON.stringify(commandMap, null, 2)}\n`,
  "utf8",
);

console.log(
  `Synchronized ${commandMap.length} Codex command mappings; platform parity manifests remain platform-owned`,
);
