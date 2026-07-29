# Verification integrity

Do not bypass Git hooks, tests, linting, security checks, signatures, or review gates. Never use `--no-verify`, mutate global hook configuration, or install an automatic hook to enforce this policy.

Enforce verification through documented commands, CI, and repository-local validators. A failed or unavailable check must remain visible as `FAILED` or `NOT_EXECUTED`.
