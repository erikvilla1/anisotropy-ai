/** The site's requests the robot answers itself, never letting them reach the site (ADR-0138 amendments 2 and 3). The paths end the
 * address, so `/api/v1/coupon-jobs` is matched and `/api/v1/coupon-jobs/check` is not. */

/** The bank's model questions, the reader paths the page sends them to: a call there costs, whether or not the answer says so. */
export const MODEL_PATHS = /\/v1\/workspace\/(proposals|result-questions|result-answers|questions)$/;
/** The requests that start an analysis on the site, a coupon's run or a wing's check: each counts in the day's analyses of the check's
 * sign-in, which the deploy check shares (2026-11-25: after the robot's quick runs, the deploy of 2dbcf8f found the day's cap reached and
 * ran no job). */
export const ANALYSIS_PATHS = /\/v1\/(coupon-jobs|wings\/checks)$/;
/** The projects the site keeps for a sign-in: a page with none of its own in the browser opens the newest one kept (2026-11-25: the wing
 * page opened a wing with spar caps that an earlier run had added, so "Add spar caps" was not there and the wing's questions were asked of
 * another wing than the bank's). */
export const PROJECT_PATHS = /\/v1\/projects(\/[^/]+)?$/;

/** Why the robot answers a request itself, or null when it goes to the site. The projects are always answered as by an API that keeps
 * none, so every run starts as a new customer and stores nothing. A quick run also answers the model's routes and the requests that start
 * an analysis "unavailable": it spends nothing on the site and leaves the day's analyses to the deploy check. */
export function refusal(method: string, path: string, quick: boolean): "projects" | "model" | "analysis" | null {
  if (PROJECT_PATHS.test(path)) return "projects";
  if (!quick || method !== "POST") return null;
  if (MODEL_PATHS.test(path)) return "model";
  if (ANALYSIS_PATHS.test(path)) return "analysis";
  return null;
}

/** The answer of an API that keeps no projects, as the page reads it (`noProjectStore`, lib/studio-api.ts): a 503 marked "off". */
export const NO_PROJECTS = { status: 503, contentType: "application/json", headers: { "X-Anisotropy-Records": "off" },
  body: JSON.stringify({ detail: "no projects are kept for the site check" }) };
