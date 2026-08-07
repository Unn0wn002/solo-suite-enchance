/// <reference types="@cloudflare/workers-types" />

// Ambient Worker binding shape, shared by worker/index.ts (fetch handler's
// `env` parameter) and db/index.ts (imports `env` from `cloudflare:workers`,
// which @cloudflare/workers-types types as `Cloudflare.Env`, not the bare
// global `Env`). This file uses the same name and shape convention Wrangler's
// own `wrangler types` command generates — if that command is ever run,
// prefer its output over hand-maintaining this file, and delete this comment.

declare namespace Cloudflare {
  interface Env {
    ASSETS: Fetcher;
    DB: D1Database;
    IMAGES: {
      input(stream: ReadableStream): {
        transform(options: Record<string, unknown>): {
          output(options: { format: string; quality: number }): Promise<{ response(): Response }>;
        };
      };
    };
    /**
     * Optional POST target for the fire-and-forget error webhook in
     * worker/index.ts (e.g. a Slack/Discord incoming webhook, or a
     * monitoring provider's ingest URL). Unset by default. See
     * .solo/monitoring.md.
     */
    MONITORING_WEBHOOK_URL?: string;
  }
}

// The Worker fetch handler's `env` parameter uses the bare global `Env` name
// (matching Cloudflare's own `ExportedHandler<Env>` convention) — alias it to
// Cloudflare.Env so both spellings stay in sync automatically.
type Env = Cloudflare.Env;
