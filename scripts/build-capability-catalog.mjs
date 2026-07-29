import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(process.argv[2] || ".");
const inventory = JSON.parse(
  readFileSync(resolve(root, "capability-inventory.json"), "utf8"),
);
const codexMap = JSON.parse(
  readFileSync(resolve(root, "platforms/codex/command-map.json"), "utf8"),
);
const codexBySource = new Map(codexMap.map((item) => [item.source_path, item]));

const roles = [
  ["Product Manager", ["storymap-skill", "before-you-build", "conductor", "business-analytics", "startup-business-analyst"], ["project", "growth", "spec"]],
  ["UI/UX Designer", ["ui-design", "accessibility-compliance", "brand-landingpage", "documentation-generation"], ["design", "browser", "seo", "docs"]],
  ["Software Architect", ["c4-architecture", "cloud-infrastructure", "backend-development", "database-design", "full-stack-orchestration"], ["project", "repo", "stack", "spec", "dev"]],
  ["Frontend Developer", ["javascript-typescript", "frontend-mobile-development", "developer-essentials", "application-performance", "accessibility-compliance"], ["dev", "design", "browser"]],
  ["GSAP Animation Developer", ["gsap-core", "gsap-timeline", "gsap-scrolltrigger", "gsap-plugins", "gsap-utils", "gsap-react", "gsap-performance", "gsap-frameworks"], ["dev", "design", "browser"]],
  ["Backend Developer", ["backend-development", "api-scaffolding", "backend-api-security", "api-testing-observability", "javascript-typescript", "python-development"], ["dev", "security", "spec", "test"]],
  ["Database Engineer", ["database-design", "database-migrations", "database-cloud-optimization", "data-validation-suite"], ["stack", "security", "site-doctor", "test"]],
  ["QA Engineer", ["qa-orchestra", "unit-testing", "tdd-workflows", "performance-testing-review", "deployment-validation"], ["test", "browser", "site-doctor", "gate"]],
  ["Security Reviewer", ["security-scanning", "security-compliance", "backend-api-security", "frontend-mobile-security", "verification-integrity", "tool-permission-governance"], ["security", "git", "gate", "site-doctor"]],
  ["DevOps Engineer", ["cicd-automation", "deployment-strategies", "deployment-validation", "cloud-infrastructure", "kubernetes-operations", "observability-monitoring", "incident-response"], ["release", "stack", "site-doctor", "git", "gate"]],
  ["Technical Writer", ["code-documentation", "documentation-generation", "documentation-standards", "c4-architecture"], ["docs", "project", "spec"]],
  ["Data Analyst", ["business-analytics", "data-engineering", "data-validation-suite", "startup-business-analyst"], ["growth", "stack", "site-doctor", "spec"]],
  ["Token Reduction and Repository Intelligence", ["Graphify", "Bounded Native Search", "Official Documentation Lookup", "Repomix"], ["repo", "ai"]],
];

const lines = [
  "# Solo Suite Enchance Capability Catalog",
  "",
  "This is the human-readable companion to `capability-inventory.json`. It",
  "lists every native plugin, skill, and command currently shipped by the",
  "three adapters, then maps the learned upstream role capabilities to the",
  "native Solo Suite route.",
  "",
  "## Compatibility legend",
  "",
  "| Surface | Claude | Antigravity | Codex |",
  "| --- | --- | --- | --- |",
  "| Plugin packages | yes, native | yes, Claude-compatible mirror | yes, Codex-native package |",
  "| Skills | yes, 80 | yes, 80 | yes, 185 skill files |",
  "| Commands | yes, 126 slash commands | yes, 126 slash commands | yes, 126 explicit skill mappings |",
  "| Capability routing | `/project:capability-map` | `/project:capability-map` | `$capability-routing` |",
  "",
  "The upstream names below are fully learned and routed, but they are not",
  "pretended to be separate native packages when the current suite implements",
  "the behavior through an equivalent Solo Suite plugin.",
  "",
  "## Native plugin, skill, and command inventory",
  "",
];

for (const plugin of inventory.plugins) {
  lines.push(`### ${plugin.name}`);
  lines.push("");
  lines.push("- Plugin compatibility: Claude yes / Antigravity yes / Codex yes");
  lines.push(`- Implementation idea: ${plugin.implementationIdea}`);
  lines.push(`- Skills (${plugin.claude.skills.length}):`);
  for (const skill of plugin.claude.skills) {
    lines.push(`  - \`${skill}\``);
  }
  lines.push(`- Commands (${plugin.claude.commands.length}):`);
  for (const command of plugin.claude.commands) {
    const sourcePath = `plugins/${plugin.name}/commands/${command}`;
    const mapping = codexBySource.get(sourcePath);
    const commandName = command.replace(/\.md$/i, "");
    lines.push(
      `  - Claude/Antigravity: \`/${plugin.name}:${commandName}\` / Codex: \`${mapping?.codex_invocation || `$${plugin.name}-${commandName}`}\``,
    );
  }
  lines.push("");
}

lines.push("## Learned role capability mapping");
lines.push("");
lines.push("| Role | Learned upstream capabilities | Native Solo Suite route | Status |");
lines.push("| --- | --- | --- | --- |");
for (const [role, learned, native] of roles) {
  lines.push(
    `| ${role} | ${learned.map((item) => `\`${item}\``).join(", ")} | ${native.map((item) => `\`${item}\``).join(", ")} | Learned + routed; exact upstream package remains attribution/reference material |`,
  );
}

lines.push("");
lines.push("## Repository-intelligence commands");
lines.push("");
lines.push("- Graphify: `graphify update .`, `graphify query \"...\"`, `graphify explain \"...\"`, `graphify path \"A\" \"B\"`");
lines.push("- Native search: bounded symbol lookup with `rg`, followed by client-native workspace editing");
lines.push("- Official docs: current, version-specific primary documentation through reviewed host web access");
lines.push("- Repomix: bounded repository snapshots and handoffs");
lines.push("- Rejected: Aider, Serena, Context7, and Code Review Graph have no activation path");
lines.push("");
lines.push("## Recommended entry points");
lines.push("");
lines.push("1. Use `/project:capability-map` or `$capability-routing`.");
lines.push("2. Read the generated `.solo/capability-plan.md`.");
lines.push("3. Activate only the listed owner and supporting plugins.");
lines.push("4. Pass the declared artifact to the next handoff and gate.");

writeFileSync(resolve(root, "CAPABILITY_CATALOG.md"), `${lines.join("\n")}\n`, "utf8");
console.log(`Wrote ${resolve(root, "CAPABILITY_CATALOG.md")}`);
