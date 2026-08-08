/** Cloudflare Worker entry point for the vinext-starter template. */
import { handleImageOptimization, DEFAULT_DEVICE_SIZES, DEFAULT_IMAGE_SIZES } from "vinext/server/image-optimization";
import handler from "vinext/server/app-router-entry";

// `Env` and `ExecutionContext` come from the ambient globals in
// ../worker-configuration.d.ts (Env) and @cloudflare/workers-types
// (ExecutionContext) — tsconfig's "**/*.ts" include picks up the ambient
// .d.ts automatically, no reference directive needed (and ESLint's
// @typescript-eslint/triple-slash-reference disallows `path`-style ones
// anyway).

// Image security config. SVG sources with .svg extension auto-skip the
// optimization endpoint on the client side (served directly, no proxy).
// To route SVGs through the optimizer (with security headers), set
// dangerouslyAllowSVG: true in next.config.js and uncomment below:
// const imageConfig: ImageConfig = { dangerouslyAllowSVG: true };

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    try {
      let response: Response;

      if (url.pathname === "/_vinext/image") {
        const allowedWidths = [...DEFAULT_DEVICE_SIZES, ...DEFAULT_IMAGE_SIZES];
        response = await handleImageOptimization(request, {
          fetchAsset: (path) => env.ASSETS.fetch(new Request(new URL(path, request.url))),
          transformImage: async (body, { width, format, quality }) => {
            const result = await env.IMAGES.input(body).transform(width > 0 ? { width } : {}).output({ format, quality });
            return result.response();
          },
        }, allowedWidths);
      } else {
        response = await handler.fetch(request, env, ctx);
      }

      return withSecurityHeaders(response);
    } catch (error) {
      reportError(error, request, env, ctx);
      throw error;
    }
  },
};

/**
 * Baseline, low-risk security headers with no chance of breaking rendering or
 * hydration. Deliberately does NOT set Content-Security-Policy yet — getting
 * a CSP right for this RSC/hydration payload shape needs a report-only pass
 * first, not a same-session guess. See .solo/tasks.md T23 and .solo/risks.md.
 */
function withSecurityHeaders(response: Response): Response {
  const headers = new Headers(response.headers);
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

/**
 * Minimum-viable error observability: no new dependency, no account/credential
 * required. Logs are always captured via Worker observability (already
 * enabled); the optional webhook gives a one-env-var upgrade path to real
 * alerting later without another code change. See .solo/monitoring.md.
 */
function reportError(error: unknown, request: Request, env: Env, ctx: ExecutionContext): void {
  const message = error instanceof Error ? error.stack ?? error.message : String(error);
  console.error(`[worker error] ${request.method} ${request.url}\n${message}`);

  if (env.MONITORING_WEBHOOK_URL) {
    ctx.waitUntil(
      fetch(env.MONITORING_WEBHOOK_URL, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          message,
          url: request.url,
          method: request.method,
          at: new Date().toISOString(),
        }),
      }).catch(() => {
        // Never let a monitoring failure affect the real response.
      })
    );
  }
}

export default worker;
