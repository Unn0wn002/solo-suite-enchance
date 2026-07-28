---
name: solo-self-check
description: "Verify the whole suite and .solo/ memory are healthy — manifests, commands, skills, counts, references, memory files. Use when the user explicitly invokes $solo-self-check or asks for this solo self-check workflow."
---

# Solo Self Check

Follow this workflow using the user's supplied context. Preserve stated gates, evidence requirements, safety constraints, and output contracts.

Use $suite-integrity. Apply it to the user's supplied arguments and surrounding request.

First resolve `<skill-root>` to the directory containing this `SKILL.md`. Then run the mechanical checker and treat its report as the evidence:

```
python "<skill-root>/../suite-integrity/scripts/self_check.py" <suite_root> <project_root>
```

It verifies: all plugin.json valid · every command has title/purpose/inputs/output format · every skill has SKILL.md · README counts match reality · marketplace.json plugin/skills counts and sources are correct · no duplicate command names · no broken command/skill cross-references (bolded and unbolded) · marketplace descriptions reference only existing commands · CHANGELOG/metadata/docx versions agree · agentsrooms templates pass the static room validator (graph + gates) · which of the 16 `.solo/` memory files are missing.

Then interpret: group failures by cause, fix the mechanical ones (stale counts, dangling refs) immediately, and turn the rest into `.solo/tasks.md` entries. A clean run = the suite is healthy.

State plainly in the summary that this is **static structure checking — a clean run is not proof of runtime health** (helpers are not executed against real targets; judgment quality is not validated). Supports installed-plugin mode when run inside a single plugin directory.

## Output

## User-facing output contract

Outside required machine-readable artifacts, end every response with exactly these seven labeled sections: **Summary**, **Findings / Work done**, **Risks**, **Required fixes**, **Suggested tasks** (stable T-IDs for `.solo/tasks.md`), **Verification**, and **Next skill** (the exact `$skill` invocation).
