// `env`'s Cloudflare.Env shape comes from the ambient global declared in
// ../worker-configuration.d.ts (picked up automatically via tsconfig's
// "**/*.ts" include — see worker/index.ts's comment for why there's no
// explicit reference directive here).
import { env } from "cloudflare:workers";
import { drizzle } from "drizzle-orm/d1";
import * as schema from "./schema";

/**
 * Whether the Cloudflare D1 binding is currently configured. As of 2026-08-07
 * it is not (`.openai/hosting.json`'s `d1` field is `null`) — see
 * `.solo/risks.md` (Critical) and `.solo/prd.md` Open Question #5, which asks
 * whether this scaffolding should be provisioned for a real feature or
 * removed. Until that's decided, any new caller should check `hasDb()` first
 * rather than relying on `getDb()`'s throw for control flow.
 */
export function hasDb(): boolean {
  return Boolean(env.DB);
}

export function getDb() {
  if (!env.DB) {
    throw new Error(
      "Cloudflare D1 binding `DB` is unavailable. Set the `d1` field in .openai/hosting.json to `DB` or let your control plane inject the real binding values before using the database. Call hasDb() first if this code path should degrade gracefully instead of throwing."
    );
  }

  return drizzle(env.DB, { schema });
}
