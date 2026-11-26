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
/** One project by its id, as the page keeps it (`PUT`) and reads it back (`GET`). */
const ONE_PROJECT = /\/v1\/projects\/[^/]+$/;
/** A plan asked for on a kept project (ADR-0144): one call to the site's model, and one more when its first plan fails the checks. */
export const PLAN_PATHS = /\/v1\/projects\/[^/]+\/plans$/;
/** A plan approved, or a step of an approved plan reported: what applies a plan's changes and starts its run. The robot approves nothing,
 * so these never reach the site, whatever the run and whatever the page does. */
export const APPROVE_PATHS = /\/v1\/projects\/[^/]+\/plans\/[^/]+\/(?:approve|steps\/[^/]+)$/;

export type Refused = "projects" | "model" | "analysis" | "approve";

/** Why the robot answers a request itself, or null when it goes to the site. The projects are always answered as by an API that keeps
 * none, so every run starts as a new customer and stores nothing; a quick run also answers the model's routes and the requests that start
 * an analysis "unavailable": it spends nothing on the site and leaves the day's analyses to the deploy check.
 *
 * `keep`: the browser of a full run's planner questions (ADR-0144, step 4), where the page's own project is kept by its id so the site can
 * plan on it. The list of projects is still answered "none", so the page never opens another run's project; a plan may be asked for, and
 * nothing that starts an analysis or approves a plan reaches the site. A plan is approved nowhere, in any run. */
export function refusal(method: string, path: string, quick: boolean, keep = false): Refused | null {
  if (APPROVE_PATHS.test(path)) return "approve";
  const kept = keep && !quick;
  if (PROJECT_PATHS.test(path)) return kept && ONE_PROJECT.test(path) && (method === "PUT" || method === "GET") ? null : "projects";
  if (method !== "POST") return null;
  if (PLAN_PATHS.test(path)) return kept ? null : "projects"; // no project kept, so no planner: the page reads the sentence as before
  if (ANALYSIS_PATHS.test(path) && (quick || kept)) return "analysis";
  if (quick && MODEL_PATHS.test(path)) return "model";
  return null;
}

/** The answer of an API that keeps no projects, as the page reads it (`noProjectStore`, lib/studio-api.ts): a 503 marked "off". */
export const NO_PROJECTS = { status: 503, contentType: "application/json", headers: { "X-Anisotropy-Records": "off" },
  body: JSON.stringify({ detail: "no projects are kept for the site check" }) };

/** The answer to an approval or a step report: refused, as a plan approved already would be (the page shows it and applies nothing). */
export const NO_APPROVAL = { status: 409, contentType: "application/json", body: JSON.stringify({ detail: "The site check approves no plan." }) };

/** What a planner question came to on the site, from the requests it made: `planned`, a plan card to grade; `none-here`, the site said no
 * planner is there (the project not kept, the route not found, or no model to plan with), and the page read the sentence as before;
 * `failed`, the planner answered with an error, which the page shows as "No plan right now"; `not-sent`, the page never asked for one. */
export type PlanOutcome = "planned" | "none-here" | "failed" | "not-sent";

export function planOutcome(heard: { kept: number[]; plans: { status: number; state: string | null }[] }): PlanOutcome {
  const asked = heard.plans.at(-1);
  if (asked) {
    if (asked.status === 404 || asked.status === 503 || (asked.status === 200 && asked.state === "unavailable")) return "none-here";
    return asked.status === 200 && asked.state ? "planned" : "failed";
  }
  return heard.kept.some((status) => status === 503 || status === 404) ? "none-here" : "not-sent";
}
