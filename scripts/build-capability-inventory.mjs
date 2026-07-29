import { mkdirSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";

const root = resolve(process.argv[2] || ".");
const claudePlugins = join(root, "platforms", "claude", "plugins");
const codexPlugins = join(root, "platforms", "codex", "plugins");
const outPath = join(root, "capability-inventory.json");

const ideas = {
  ai: "Make AgentRooms, output auditing, and evidence contracts the governance layer for every multi-role run.",
  browser: "Add a repeatable responsive, console, form, and accessibility smoke matrix for website changes.",
  design: "Route design-system, interaction, responsive, and accessibility work from shared acceptance criteria.",
  dev: "Add frontend, backend, TypeScript, Python, and GSAP implementation adapters without duplicating role logic.",
  docs: "Generate ADRs, OpenAPI, changelogs, setup guides, and runbooks from approved project artifacts.",
  "full-team": "Orchestrate phase-owned seats with explicit inputs, outputs, workspace rules, and handoff evidence.",
  gate: "Unify acceptance, security, performance, accessibility, and deployment evidence into one release decision.",
  git: "Make branch, commit, review, issue sync, and release-note work respect the no-bypass safety contract.",
  growth: "Connect conversion audits and experiments to measurable hypotheses, events, and decision logs.",
  project: "Add story-map and before-build risk checks before PRD, architecture, and task breakdown.",
  release: "Attach reproducible build provenance, deployment strategy, rollback, and CI evidence to every release.",
  repo: "Route Graphify, bounded native search, primary official documentation, and filtered Repomix handoffs without activating rejected tools.",
  security: "Run threat modeling, abuse cases, authorization matrices, secret checks, and RLS evidence before release.",
  seo: "Treat technical SEO, structured data, GEO, content, image, and sitemap checks as acceptance criteria.",
  "site-doctor": "Make health audits composable across accessibility, content, APIs, dependencies, infrastructure, and observability.",
  solo: "Keep project memory, decisions, handoffs, and next-step selection stable across every platform.",
  spec: "Turn feature briefs and API contracts into the shared input for design, architecture, implementation, and QA.",
  stack: "Capture the real hosting, database, auth, CDN, analytics, email, and payment stack before vendor-specific audits.",
  test: "Use acceptance criteria as a QA contract and combine unit, integration, E2E, edge-case, and performance checks.",
};

const sources = {
  project: [
    "EC Solo Suite Learns/repositories/storymap-skill",
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/before-you-build",
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/conductor",
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/business-analytics",
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/startup-business-analyst",
  ],
  design: [
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/ui-design",
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/accessibility-compliance",
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/brand-landingpage",
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/documentation-generation",
  ],
  dev: [
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/backend-development",
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/javascript-typescript",
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/frontend-mobile-development",
    "EC Solo Suite Learns/repositories/gsap-skills",
  ],
  "site-doctor": [
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/security-scanning",
    "EC Solo Suite Learns/repositories/wshobson-agents/plugins/deployment-validation",
    "EC Solo Suite Learns/repositories/qa-orchestra",
  ],
  repo: [
    "EC Solo Suite Learns/repositories/graphify",
    "EC Solo Suite Learns/repositories/repomix",
  ],
};

function walk(directory) {
  if (!statSync(directory, { throwIfNoEntry: false })) return [];
  const files = [];
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) files.push(...walk(path));
    else files.push(path);
  }
  return files;
}

function namesUnder(directory, filename, stripDirectory) {
  return walk(directory)
    .filter((path) => path.endsWith(filename))
    .map((path) => relative(stripDirectory, path).replaceAll("\\", "/"));
}

const plugins = readdirSync(claudePlugins, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) => entry.name)
  .sort()
  .map((name) => {
    const claudeRoot = join(claudePlugins, name);
    const codexRoot = join(codexPlugins, name);
    const claudeSkills = namesUnder(join(claudeRoot, "skills"), "SKILL.md", join(claudeRoot, "skills"));
    const claudeCommands = namesUnder(join(claudeRoot, "commands"), ".md", join(claudeRoot, "commands"));
    const codexSkills = namesUnder(join(codexRoot, "skills"), "SKILL.md", join(codexRoot, "skills"));
    const implementationIdea = ideas[name] || "Review this plugin against the shared phase, handoff, evidence, and memory contracts.";

    return {
      name,
      claude: {
        skills: claudeSkills,
        commands: claudeCommands,
      },
      codex: {
        skillFiles: codexSkills.length,
      },
      antigravity: {
        mirrorOf: "claude",
      },
      implementationIdea,
      skillImplementationIdeas: claudeSkills.map((path) => ({
        path,
        idea: "Use this skill as an explicit owner surface; declare inputs, outputs, handoff, and evidence before work begins.",
      })),
      commandImplementationIdeas: claudeCommands.map((path) => {
        const command = path.replace(/\.md$/i, "");
        return {
          path,
          invocation: `/${name}:${command}`,
          idea: "Invoke this workflow at its phase boundary, write the promised artifact to .solo or the project workspace, and leave evidence for the next gate.",
        };
      }),
      learnedSources: sources[name] || [],
    };
  });

const inventory = {
  product: "Solo Suite Enchance",
  generatedAt: new Date().toISOString(),
  counts: {
    plugins: plugins.length,
    claudeSkills: plugins.reduce((sum, plugin) => sum + plugin.claude.skills.length, 0),
    claudeCommands: plugins.reduce((sum, plugin) => sum + plugin.claude.commands.length, 0),
    codexSkillFiles: plugins.reduce((sum, plugin) => sum + plugin.codex.skillFiles, 0),
  },
  sourcePolicy: {
    upstreamCorpus: "C:/Users/unn0w/Downloads/EC Solo Suite Learns",
    attribution: "Review licenses and preserve upstream attribution before promotion.",
    activation: "Use phase-driven routing; do not activate every plugin for every task.",
  },
  plugins,
};

mkdirSync(resolve(root), { recursive: true });
writeFileSync(outPath, `${JSON.stringify(inventory, null, 2)}\n`, "utf8");
console.log(`Wrote ${outPath} (${plugins.length} plugins, ${inventory.counts.claudeSkills} Claude skills, ${inventory.counts.claudeCommands} Claude commands)`);
