# Decisions — Solo Suite Enchance

## 2026-08-25 — Repository separation

Decision: Solo Suite remains an AI tooling/distribution repository only. The obsolete bundled landing-site implementation, application runtime configuration, database scaffolding, deployment metadata, site assets/tests, and derived website graph data are removed.

Rationale: application repositories may consume Solo Suite, but coupling a specific application implementation into the distribution creates misleading deployment/dependency/security state and cross-project data contamination.

## 2026-08-25 — Graphify output is derived

Decision: do not commit a pre-generated `graphify-out/` snapshot in the distribution repository. Graphify remains audited, version-pinned, explicit and project-local. If a snapshot is present, freshness validation remains fail-closed; absence means the optional derived snapshot has not been initialized.

## 2026-08-25 — Dependency surface

Decision: root npm dependencies are removed because the remaining repository-level JavaScript tooling/tests use Node built-ins. Native platform Python validation keeps its own reviewed pinned requirements.
