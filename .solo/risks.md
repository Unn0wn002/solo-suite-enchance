# Risks — Solo Suite Enchance

- **Distribution drift:** platform-native plugin/skill/command trees can diverge. Mitigation: generated mirror, workflow/command parity, distribution parity, and native validation gates.
- **Permission drift:** host permissions can silently expand. Mitigation: checked-in project rules plus validation and review.
- **Security-tool drift:** rejected or high-risk upstream capabilities can regain activation paths. Mitigation: remediation ledger, control-artifact hashes, local surface scan, dependency audit, and pinned scanner suite.
- **Stale derived intelligence:** a committed Graphify snapshot can become inaccurate. Mitigation: graph output is optional derived data; any committed snapshot must pass the freshness checker.
- **Repository contamination:** consuming-project application source, runtime data, secrets, or deployment metadata can be copied into this distribution. Mitigation: explicit repository boundary in README/project memory and periodic root/tree audits.
