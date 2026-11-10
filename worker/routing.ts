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
  "ANISOTROPY_JOBS_PER_USER_PER_DAY",
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

/** The job queue (ADR-0056 amendment 3). The API's own container files a job and answers with its id in this header; the Worker sends
 * the id to the queue and drops the header. */
export const ENQUEUE_HEADER = "X-Anisotropy-Enqueue";
export const JOB_ROLE_VARIABLE = "ANISOTROPY_JOB_ROLE";

/** The solver containers' routes, which only the queue's consumer reaches: never forwarded from the site. */
export function isSolverPath(path: string): boolean {
  return path === "/v1/solver" || path.startsWith("/v1/solver/");
}

/** The API's own container: its variables, and the role `queue` when the Worker has the queue to hand jobs to (its binding). Without
 * the binding the API runs each job itself, one at a time, as before. */
export function apiEnvironment(env: object): Record<string, string> {
  const out = containerEnvironment(env);
  if (Reflect.get(env, "JOB_QUEUE") != null) out[JOB_ROLE_VARIABLE] = "queue";
  return out;
}

/** What a solver container does not get: the sign-in (no browser reaches it; the consumer's requests carry no token), the browser's
 * origins, the assistant and the per-user cap, which are the API container's business. */
const NOT_FOR_SOLVERS: readonly ContainerVariable[] = [
  "ANISOTROPY_ACCESS_TEAM_DOMAIN", "ANISOTROPY_ACCESS_AUD", "ANISOTROPY_ALLOWED_ORIGINS",
  "ANISOTROPY_ASSISTANT_PROVIDER", "ANISOTROPY_ASSISTANT_MODEL", "ANTHROPIC_API_KEY", "ANISOTROPY_JOBS_PER_USER_PER_DAY",
];

/** A solver container: the database, the store and the commit, and the role `solver`. */
export function solverEnvironment(env: object): Record<string, string> {
  const out = containerEnvironment(env);
  for (const name of NOT_FOR_SOLVERS) delete out[name];
  out[JOB_ROLE_VARIABLE] = "solver";
  return out;
}
