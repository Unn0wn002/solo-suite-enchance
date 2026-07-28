#!/usr/bin/env node

/**
 * Convert Solo Suite's legacy Claude command markdown into native Codex skills.
 *
 * The converter deliberately makes every command-derived skill explicit-only.
 * Legacy commands were explicit entry points, and this stricter policy also keeps
 * mutating, secret-aware, browser-submit, deploy, migration, and sync workflows
 * from being selected implicitly.
 */

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const scriptFile = fileURLToPath(import.meta.url);
const packageRoot = path.resolve(path.dirname(scriptFile), "..");
const workspaceRoot = path.resolve(packageRoot, "..");
// Keep the Codex adapter pointed at the current Claude source tree by
// default.  A caller can still override this with --source-root for a
// reproducible historical conversion.
const defaultSourceRoot = path.join(workspaceRoot, "solo-suite-v1.0.27-work");

function parseArgs(argv) {
  const options = {
    sourceRoot: defaultSourceRoot,
    packageRoot,
    python: process.env.PYTHON || "python",
    initScript: path.join(
      process.env.CODEX_HOME || path.join(process.env.USERPROFILE || "", ".codex"),
      "skills",
      ".system",
      "skill-creator",
      "scripts",
      "init_skill.py",
    ),
    skipInit: false,
    plugins: [],
  };

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--source-root") options.sourceRoot = path.resolve(argv[++index]);
    else if (argument === "--package-root") options.packageRoot = path.resolve(argv[++index]);
    else if (argument === "--python") options.python = argv[++index];
    else if (argument === "--init-script") options.initScript = path.resolve(argv[++index]);
    else if (argument === "--skip-init") options.skipInit = true;
    else if (argument === "--plugin") options.plugins.push(argv[++index].toLowerCase());
    else throw new Error(`Unknown argument: ${argument}`);
  }
  return options;
}

function listCommands(sourceRoot, selectedPlugins = []) {
  const pluginsRoot = path.join(sourceRoot, "plugins");
  const commands = [];
  for (const plugin of fs.readdirSync(pluginsRoot).sort()) {
    if (selectedPlugins.length && !selectedPlugins.includes(plugin)) continue;
    const commandRoot = path.join(pluginsRoot, plugin, "commands");
    if (!fs.existsSync(commandRoot)) continue;
    for (const filename of fs.readdirSync(commandRoot).sort()) {
      if (!filename.endsWith(".md")) continue;
      commands.push({
        plugin,
        command: filename.slice(0, -3),
        sourceFile: path.join(commandRoot, filename),
      });
    }
  }
  return commands;
}

function parseCommand(sourceFile) {
  const source = fs.readFileSync(sourceFile, "utf8").replace(/\r\n/g, "\n");
  const match = source.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!match) throw new Error(`Invalid command frontmatter: ${sourceFile}`);

  const metadata = {};
  for (const line of match[1].split("\n")) {
    const field = line.match(/^([a-z0-9-]+):\s*(.*)$/i);
    if (field) metadata[field[1]] = field[2].trim();
  }
  if (!metadata.description) throw new Error(`Missing description: ${sourceFile}`);
  return { metadata, body: match[2].trimEnd() };
}

const acronyms = new Map([
  ["a11y", "A11y"],
  ["ai", "AI"],
  ["api", "API"],
  ["authz", "AuthZ"],
  ["ci", "CI"],
  ["db", "DB"],
  ["e2e", "E2E"],
  ["prd", "PRD"],
  ["qa", "QA"],
  ["rls", "RLS"],
  ["seo", "SEO"],
  ["ui", "UI"],
  ["ux", "UX"],
]);

function titleCase(value) {
  return value
    .split("-")
    .map((word) => acronyms.get(word) || `${word.slice(0, 1).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

function yamlQuote(value) {
  return JSON.stringify(value);
}

function transformBody(body, skillRootNames) {
  let transformed = body;

  transformed = transformed.replace(
    /python3\s+"\$\{CLAUDE_PLUGIN_ROOT\}\/skills\/suite-integrity\/scripts\/self_check\.py"/g,
    'python "<skill-root>/../suite-integrity/scripts/self_check.py"',
  );
  transformed = transformed.replace(
    /First run the mechanical checker and treat its report as the evidence:/g,
    "First resolve `<skill-root>` to the directory containing this `SKILL.md`. Then run the mechanical checker and treat its report as the evidence:",
  );
  transformed = transformed
    .replace(/for:\s*\$ARGUMENTS/g, "for the user's supplied arguments and surrounding request.")
    .replace(/on:\s*\$ARGUMENTS/g, "on the user's supplied arguments and surrounding request.")
    .replace(/of:\s*\$ARGUMENTS/g, "of the user's supplied arguments and surrounding request.")
    .replace(/audit:\s*\$ARGUMENTS/g, "audit the user's supplied arguments and surrounding request.")
    .replace(/\.\s*\$ARGUMENTS/g, ". Apply it to the user's supplied arguments and surrounding request.")
    .replace(
      /Debug this problem:\s*\$ARGUMENTS/g,
      "Debug the problem described in the user's supplied arguments and surrounding request.",
    )
    .replace(/\$ARGUMENTS/g, "the user's supplied arguments and surrounding request");
  transformed = transformed.replace(/\/([a-z0-9-]+):([a-z0-9*-]+)/gi, (_match, plugin, command) => {
    return `$${plugin.toLowerCase()}-${command.toLowerCase()}`;
  });

  for (const name of skillRootNames) {
    const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    transformed = transformed.replace(
      new RegExp(`Use the ${escaped} orchestrator skill`, "gi"),
      `Use $${name}`,
    );
    transformed = transformed.replace(
      new RegExp(`Use the \\*\\*${escaped}\\*\\* skill`, "gi"),
      `Use $${name}`,
    );
    transformed = transformed.replace(
      new RegExp(`Use the ${escaped} skill`, "gi"),
      `Use $${name}`,
    );
    transformed = transformed.replace(
      new RegExp(`Use ${escaped} skill`, "gi"),
      `Use $${name}`,
    );
    transformed = transformed.replace(
      new RegExp(`\\*\\*${escaped}\\*\\*`, "g"),
      `$${name}`,
    );
  }

  transformed = transformed
    .replace(/slash commands/gi, "skill invocations")
    .replace(/slash command/gi, "skill invocation")
    .replace(/skills?\/commands?/gi, "skills")
    .replace(/commands it runs/gi, "skills it invokes")
    .replace(/which command to run/gi, "which skill to invoke")
    .replace(/which command to use/gi, "which skill to invoke")
    .replace(/Next Recommended Command/g, "Next Recommended Skill")
    .replace(/Next command/g, "Next skill")
    .replace(/next command/g, "next skill")
    .replace(/fix commands/gi, "fix invocations")
    .replace(/fix command/gi, "fix invocation")
    .replace(
      /^\/…$/gm,
      "No follow-up skill is implied here; choose the next validated skill for the current workflow.",
    );

  return transformed;
}

function mergeCommandWorkflow(specialistMarkdown, skillName, commandBody) {
  const marker = "## Explicit workflow behavior";
  const contractMarker = "## User-facing output contract";
  let base = specialistMarkdown.trimEnd();
  let contract = "";

  const existingMarker = base.indexOf(`\n${marker}\n`);
  if (existingMarker !== -1) {
    const contractIndex = base.indexOf(`\n${contractMarker}\n`, existingMarker);
    contract = contractIndex === -1 ? "" : base.slice(contractIndex).trim();
    base = base.slice(0, existingMarker).trimEnd();
  } else {
    const contractIndex = base.indexOf(`\n${contractMarker}\n`);
    if (contractIndex !== -1) {
      contract = base.slice(contractIndex).trim();
      base = base.slice(0, contractIndex).trimEnd();
    }
  }

  const paragraphs = commandBody.trim().split(/\n\s*\n/);
  if (paragraphs[0]?.includes(`$${skillName}`)) paragraphs.shift();
  const instructions = paragraphs.join("\n\n").trim();
  const merged = [
    base,
    "",
    marker,
    "",
    `When explicitly invoked as \`$${skillName}\`, apply this entrypoint behavior:`,
    "",
    instructions,
  ];
  if (contract) merged.push("", contract);
  return `${merged.join("\n").trimEnd()}\n`;
}

function discoverSkillNames(sourceRoot) {
  const names = new Set();
  const pluginsRoot = path.join(sourceRoot, "plugins");
  for (const plugin of fs.readdirSync(pluginsRoot)) {
    const skillsRoot = path.join(pluginsRoot, plugin, "skills");
    if (!fs.existsSync(skillsRoot)) continue;
    for (const entry of fs.readdirSync(skillsRoot, { withFileTypes: true })) {
      if (entry.isDirectory()) names.add(entry.name);
    }
  }
  return [...names].sort((left, right) => right.length - left.length);
}

function initializeSkill(options, skillName, skillsRoot, displayName, shortDescription) {
  const skillRoot = path.join(skillsRoot, skillName);
  if (fs.existsSync(skillRoot) || options.skipInit) {
    fs.mkdirSync(path.join(skillRoot, "agents"), { recursive: true });
    return false;
  }
  if (!fs.existsSync(options.initScript)) {
    throw new Error(`skill-creator init script not found: ${options.initScript}`);
  }

  const result = spawnSync(
    options.python,
    [
      options.initScript,
      skillName,
      "--path",
      skillsRoot,
      "--interface",
      `display_name=${displayName}`,
      "--interface",
      `short_description=${shortDescription}`,
      "--interface",
      `default_prompt=Use $${skillName} to run this workflow with the provided context.`,
    ],
    { encoding: "utf8" },
  );
  if (result.status !== 0) {
    throw new Error(
      `init_skill.py failed for ${skillName}:\n${result.stdout || ""}${result.stderr || ""}`,
    );
  }
  return true;
}

function toPortableRelative(from, target) {
  return path.relative(from, target).split(path.sep).join("/");
}

function convert(options) {
  const commands = listCommands(options.sourceRoot, options.plugins);
  const dependencySkillNames = discoverSkillNames(options.sourceRoot);
  const mapping = [];
  let initialized = 0;
  let merged = 0;

  for (const item of commands) {
    const parsed = parseCommand(item.sourceFile);
    const skillName = `${item.plugin}-${item.command}`;
    if (skillName.length > 64) throw new Error(`Skill name exceeds 64 characters: ${skillName}`);

    const displayName = `${titleCase(item.plugin)} ${titleCase(item.command)}`;
    const shortDescription = `Run the ${displayName} Codex workflow`;
    if (shortDescription.length < 25 || shortDescription.length > 64) {
      throw new Error(`short_description length invalid for ${skillName}: ${shortDescription.length}`);
    }

    const skillsRoot = path.join(options.packageRoot, "plugins", item.plugin, "skills");
    const skillRoot = path.join(skillsRoot, skillName);
    const skillMarkdownPath = path.join(skillRoot, "SKILL.md");
    const specialistExists = (
      dependencySkillNames.includes(skillName) && fs.existsSync(skillMarkdownPath)
    );
    if (initializeSkill(options, skillName, skillsRoot, displayName, shortDescription)) initialized += 1;

    const nativeDescription = parsed.metadata.description
      .replace(/\/([a-z0-9-]+):([a-z0-9*-]+)/gi, (_match, plugin, command) => {
        return `$${plugin.toLowerCase()}-${command.toLowerCase()}`;
      })
      .replace(/slash commands/gi, "skill invocations")
      .replace(/slash command/gi, "skill invocation");
    const description = `${nativeDescription} Use when the user explicitly invokes $${skillName} or asks for this ${item.plugin} ${item.command} workflow.`;
    const body = transformBody(parsed.body, dependencySkillNames);
    const skillMarkdown = [
      "---",
      `name: ${skillName}`,
      `description: ${yamlQuote(description)}`,
      "---",
      "",
      `# ${displayName}`,
      "",
      "Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.",
      "",
      body,
      "",
    ].join("\n");

    const openaiYaml = [
      "interface:",
      `  display_name: ${yamlQuote(displayName)}`,
      `  short_description: ${yamlQuote(shortDescription)}`,
      `  default_prompt: ${yamlQuote(`Use $${skillName} to run this workflow with the provided context.`)}`,
      "policy:",
      "  allow_implicit_invocation: false",
      "",
    ].join("\n");

    fs.mkdirSync(path.join(skillRoot, "agents"), { recursive: true });
    if (specialistExists) {
      const specialistMarkdown = fs.readFileSync(skillMarkdownPath, "utf8");
      fs.writeFileSync(
        skillMarkdownPath,
        mergeCommandWorkflow(specialistMarkdown, skillName, body),
        "utf8",
      );
      const agentPath = path.join(skillRoot, "agents", "openai.yaml");
      if (!fs.existsSync(agentPath)) fs.writeFileSync(agentPath, openaiYaml, "utf8");
      merged += 1;
    } else {
      fs.writeFileSync(skillMarkdownPath, skillMarkdown, "utf8");
      fs.writeFileSync(path.join(skillRoot, "agents", "openai.yaml"), openaiYaml, "utf8");
    }

    mapping.push({
      legacy_invocation: `/${item.plugin}:${item.command}`,
      skill_invocation: `$${skillName}`,
      codex_invocation: `$${skillName}`,
      plugin: item.plugin,
      command: item.command,
      skill_name: skillName,
      // Record the path inside the original archive, not a workstation-only
      // relative path to the temporary extracted source tree.
      source_path: toPortableRelative(options.sourceRoot, item.sourceFile),
      target_path: toPortableRelative(options.packageRoot, path.join(skillRoot, "SKILL.md")),
      allow_implicit_invocation: false,
    });
  }

  let finalMapping = mapping;
  const mapPath = path.join(options.packageRoot, "command-map.json");
  if (options.plugins.length && fs.existsSync(mapPath)) {
    const existing = JSON.parse(fs.readFileSync(mapPath, "utf8"));
    finalMapping = [
      ...existing.filter((item) => !options.plugins.includes(item.plugin)),
      ...mapping,
    ].sort((left, right) => left.legacy_invocation.localeCompare(right.legacy_invocation));
  }

  fs.writeFileSync(
    mapPath,
    `${JSON.stringify(finalMapping, null, 2)}\n`,
    "utf8",
  );

  const mapLines = [
    "# Command to Skill Map",
    "",
    "Invoke the specific native Codex skill shown in the second column; the legacy Claude syntax is retained only for migration lookup.",
    "",
    "| Legacy invocation | Codex skill | Target |",
    "| --- | --- | --- |",
    ...finalMapping.map(
      (entry) => `| \`${entry.legacy_invocation}\` | \`${entry.skill_invocation}\` | \`${entry.target_path}\` |`,
    ),
    "",
  ];
  fs.writeFileSync(path.join(options.packageRoot, "COMMAND-MAP.md"), mapLines.join("\n"), "utf8");

  return {
    commands: commands.length,
    initialized,
    merged,
    written: mapping.length,
    totalMappings: finalMapping.length,
  };
}

try {
  const result = convert(parseArgs(process.argv.slice(2)));
  process.stdout.write(`${JSON.stringify(result)}\n`);
} catch (error) {
  process.stderr.write(`${error.stack || error.message}\n`);
  process.exitCode = 1;
}
