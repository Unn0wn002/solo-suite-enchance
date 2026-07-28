---
description: List required env vars and secrets per environment
argument-hint: [optional area]
---
Use the **software-architect** skill to define an environment/config contract (lighter inline if that plugin isn't installed). $ARGUMENTS

List every required env var and secret, what it's for, and which environments (dev/preview/prod) it belongs to — **names only, never values**. Separate public vs secret; cross-check the code and `.env.example`. Pairs with `/security:secrets-fix` and `/stack:audit-vercel`.


Write the contract to **`.solo/env-contract.md`** — names only, never values.

## Output
End with the 7-part contract: **Summary · Findings/Work done · Risks · Required fixes · Suggested tasks** (→ `.solo/tasks.md`, stable T-IDs) **· Verification · Next command** (exact slash command).
