---
description: Verify suite manifests, references, and .solo memory
argument-hint: [optional project path, or - to skip memory checks]
---
Use the **suite-integrity** skill. $ARGUMENTS

First run the mechanical checker and treat its report as the evidence:

```
python3 "${CLAUDE_PLUGIN_ROOT}/skills/suite-integrity/scripts/self_check.py" <suite_root> <project_root>
```

It verifies: all plugin.json valid · every command has title/purpose/inputs/output format · every skill has SKILL.md · README counts match reality · marketplace.json plugin/skill/command counts and sources are correct · no duplicate command names · no broken command/skill cross-references (bolded and unbolded) · marketplace descriptions reference only existing commands · CHANGELOG/metadata/docx versions agree · agentsrooms templates pass the static room validator (graph + gates) · which of the 16 `.solo/` memory files are missing.

Then interpret: group failures by cause, fix the mechanical ones (stale counts, dangling refs) immediately, and turn the rest into `.solo/tasks.md` entries. A clean run = the suite is healthy.

State plainly in the summary that this is **static structure checking — a clean run is not proof of runtime health** (helpers are not executed against real targets; judgment quality is not validated). Supports installed-plugin mode when run inside a single plugin directory.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
