/** What the Worker decides without the Cloudflare runtime (ADR-0056): which paths are the API's and what the container gets, and
 * which of the Worker's secrets and variables the container receives as its environment. Pure, so `tests/worker-routing.test.ts`
 * runs it in Node. */

export const API_PREFIX = "/api";

/** The container's path for a request to the site, or null when the request is not the API's. The site is built with
 * `NEXT_PUBLIC_ANISOTROPY_API_URL=/api`, so it calls `/api/v1/...`; the container's FastAPI listens at `/v1/...` and `/healthz`. */
export function apiPath(pathname: string): string | null {
  if (pathname === API_PREFIX) return "/";
  if (!pathname.startsWith(`${API_PREFIX}/`)) return null;
  return pathname.slice(API_PREFIX.length);
}

/** The settings the API reads (api/src/anisotropy_api/settings.py), each a Worker secret or variable of the same name. The
 * container gets only the ones that are set and non-blank; the API refuses an inconsistent set itself (ADR-0003). */
export const CONTAINER_VARIABLES = [
  "DATABASE_URL", "DATABASE_URL_UNPOOLED", "ANISOTROPY_RUN_RECORDS",
  "ANISOTROPY_ACCESS_TEAM_DOMAIN", "ANISOTROPY_ACCESS_AUD", "ANISOTROPY_ALLOWED_ORIGINS",
  "ANISOTROPY_R2_BUCKET", "ANISOTROPY_R2_ENDPOINT", "ANISOTROPY_R2_ACCESS_KEY_ID", "ANISOTROPY_R2_SECRET_ACCESS_KEY",
  "ANISOTROPY_ASSISTANT_PROVIDER", "ANISOTROPY_ASSISTANT_MODEL", "ANTHROPIC_API_KEY",
  "ANISOTROPY_GIT_COMMIT",
] as const;

export type ContainerVariable = (typeof CONTAINER_VARIABLES)[number];

export function containerEnvironment(env: object): Record<string, string> {
  const out: Record<string, string> = {};
  for (const name of CONTAINER_VARIABLES) {
    const value: unknown = Reflect.get(env, name);
    if (typeof value === "string" && value.trim() !== "") out[name] = value;
  }
  return out;
}
