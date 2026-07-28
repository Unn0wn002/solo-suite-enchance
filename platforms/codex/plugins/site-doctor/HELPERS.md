# Running bundled helpers from an installed Site Doctor plugin

Helper paths are resolved from the selected skill, never from the process
working directory:

1. Start with the absolute path of the active `SKILL.md`.
2. Resolve symlinks/`..`, then take `Path(skill_file).resolve().parents[2]` as
   `plugin_root` (`.../site-doctor/skills/<skill>/SKILL.md` →
   `.../site-doctor`). Verify that `.codex-plugin/plugin.json` and
   `scripts/run_helper.py` exist below that same root.
3. Select the first available interpreter in this order: `python3`, `python`,
   then Windows `py -3`. On POSIX use `command -v`; in PowerShell use
   `Get-Command`. If none exists, stop and report that Python 3 is required.
4. Invoke the launcher by absolute path and pass every argument separately:

   ```text
   python3 <plugin_root>/scripts/run_helper.py <helper-id> <arguments...>
   python  <plugin_root>/scripts/run_helper.py <helper-id> <arguments...>
   py -3   <plugin_root>/scripts/run_helper.py <helper-id> <arguments...>
   ```

Do not interpolate user input into a shell command. The launcher accepts only
an internal helper allowlist, resolves the final file below its own plugin
root, and reuses the selected Python interpreter.

Individual skill folders are **not standalone packages**. Network helpers
depend on the shared `lib/url_guard.py`, and every documented invocation uses
the plugin-level launcher. Copy/install the intact `site-doctor` plugin rather
than copying one skill folder.
