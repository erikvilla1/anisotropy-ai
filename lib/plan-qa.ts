/**
 * The QA step of a plan (ADR-0144): the result's own checks read into pass, warning or stop, each with its evidence named. The reference
 * solver's agreement (the job's line, ADR-0030), the mesh study (ADR-0068), the balance of the reactions and the loads, and where the
 * answer is read: the gauge section past its stand-off (ADR-0108), a plate away from its held corners (ADR-0108 amendment 2), or the
 * whole model. Nothing here computes a number of the result: every line prints the package's own values, and a verdict only compares
 * them with a bound written below.
 */
import type { Fields, JobStatus } from "./studio-api";
import { BASIS_WORDS } from "./studio-answer";
import { printed } from "./studio-colors";
import { customerText, verificationOf } from "./studio-copy";

export type QaVerdict = "pass" | "warning" | "stop";
export type QaCheck = { id: "reference" | "mesh" | "equilibrium" | "place"; verdict: QaVerdict; line: string };
export type QaReading = { verdict: QaVerdict; headline: string; checks: QaCheck[] };

/** The reactions and the loads balance when what is left over is at most this share of the load: roundoff, a millionth. Past a
 * thousandth the solve is suspect and the answer is not given. */
const BALANCED = 1e-6;
const UNBALANCED = 1e-3;

const RANK: Record<QaVerdict, number> = { pass: 0, warning: 1, stop: 2 };
const worst = (checks: QaCheck[]): QaVerdict => checks.reduce<QaVerdict>((w, c) => (RANK[c.verdict] > RANK[w] ? c.verdict : w), "pass");
const listed = (names: string[]) => (names.length < 2 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`);

/** Whether the result can be checked: the run is done and its fields are read, with the mesh study when the run wrote one. */
export function qaReady(job: Pick<JobStatus, "state" | "outputs"> | null, fields: Fields | null): boolean {
  return !!job && job.state === "done" && !!fields && (!("convergence" in job.outputs) || !!fields.summary.convergence);
}

/** The reference solver: the job's line of how many recorded values agree, as the results card says it. */
function reference(job: Pick<JobStatus, "result">, fields: Fields): QaCheck {
  const found = verificationOf(job.result, fields.summary.calculix ?? null);
  if (!found) return { id: "reference", verdict: "warning", line: "Reference solver: no second solver checked this result" };
  return { id: "reference", verdict: found.verified ? "pass" : "warning", line: found.line };
}

/** The mesh study: the reaction, the gauge strain and the gauge ply stresses settled, and the answer's own R with them. */
function mesh(fields: Fields): QaCheck {
  const study = fields.summary.convergence;
  if (!study) return { id: "mesh", verdict: "warning", line: "Mesh study: not run for this result" };
  if (!study.studied || !study.settled) {
    const reason = customerText(study.reason);
    return { id: "mesh", verdict: "warning", line: `Mesh study: not studied${reason ? `, ${reason}` : ""}` };
  }
  const below = `${printed(100 * study.settled_below)} %`;
  const core: [keyof NonNullable<typeof study.settled>, string][] = [["reaction", "the reaction"], ["gauge_strain", "the gauge strain"], ["plies", "the gauge ply stresses"]];
  const moving = core.filter(([key]) => !study.settled![key]).map(([, name]) => name);
  if (moving.length) return { id: "mesh", verdict: "warning", line: `Mesh study: ${listed(moving)} still moving by ${below} or more` };
  const basis = fields.summary.verdict?.basis;
  const own = basis === "gauge" ? study.settled.fpf_gauge : basis === "whole" ? study.settled.fpf : undefined;
  const settled = `Mesh study: ${listed(core.map(([, name]) => name))} changed by less than ${below}`;
  if (own === false) return { id: "mesh", verdict: "warning", line: `${settled}; the first-ply failure R is still moving` };
  return { id: "mesh", verdict: "pass", line: settled };
}

/** The balance: the reactions and the applied loads sum to the package's residual, printed beside the reaction it is a share of. */
function equilibrium(fields: Fields): QaCheck {
  const s = fields.summary, force = fields.labels.force ?? "";
  const scale = Math.max(Math.abs(s.reaction.value), Math.abs(s.applied.total_force ?? 0));
  const residual = Math.abs(s.equilibrium_residual);
  if (!Number.isFinite(residual) || !(scale > 0)) return { id: "equilibrium", verdict: "warning", line: "Equilibrium: no reaction to balance the loads against" };
  const line = `Equilibrium: reaction ${printed(Math.abs(s.reaction.value))} ${force}, out of balance by ${printed(residual)} ${force}`;
  if (residual <= BALANCED * scale) return { id: "equilibrium", verdict: "pass", line };
  return { id: "equilibrium", verdict: residual <= UNBALANCED * scale ? "warning" : "stop", line };
}

type Place = { touches_grip?: boolean; near_tab?: boolean; near_corner?: boolean; factor: number };
const singular = (p: Place) => !!(p.touches_grip || p.near_tab || p.near_corner);

/** Where the answer is read: past the gauge section's stand-off, away from a plate's held corners, or over the whole model; an earlier
 * failure outside that place is named, and is a warning unless it sits where stress is singular (a grip edge, a tab line, a held corner). */
function place(fields: Fields): QaCheck | null {
  const s = fields.summary as Fields["summary"] & { held_corners?: { stand_off: number } | null };
  const verdict = s.verdict as (Omit<NonNullable<Fields["summary"]["verdict"]>, "basis" | "outside_earlier"> & { basis: string; outside_earlier: Place | null }) | null | undefined;
  if (!verdict) return null;
  const length = fields.labels.length ?? "";
  const words = (BASIS_WORDS as Record<string, string>)[verdict.basis] ?? (verdict.basis === "away" ? "the plate away from its held corners" : "the whole model");
  const stand = verdict.basis === "gauge" ? s.gauge_reading?.stand_off : verdict.basis === "away" ? s.held_corners?.stand_off : undefined;
  const where = `Read in ${words}${stand !== undefined && stand !== null ? `, at least ${printed(stand)} ${length} from ${verdict.basis === "gauge" ? "each tab line" : "each held corner"}` : ""}`;
  const out = verdict.outside_earlier;
  if (out) {
    const at = out.touches_grip ? "a grip edge" : out.near_tab ? "a tab line" : out.near_corner ? "a held corner" : `outside ${words}`;
    const said = `${where}; an earlier failure at ${at}, R = ${printed(out.factor)}, is reported apart`;
    return { id: "place", verdict: singular(out) ? "pass" : "warning", line: singular(out) ? `${said}: stress there grows with a finer mesh` : said };
  }
  if (verdict.basis === "whole") {
    const table = s.fpf[verdict.earliest] as (Place & { place?: string }) | undefined;
    if (table && singular(table)) return { id: "place", verdict: "warning", line: `${where}; the first failure is at a held edge, where stress grows with a finer mesh` };
  }
  return { id: "place", verdict: "pass", line: where };
}

/** The result's own checks, each with its line, and the worst of them as the step's verdict. */
export function readQa(job: Pick<JobStatus, "result">, fields: Fields): QaReading {
  const checks = [reference(job, fields), mesh(fields), equilibrium(fields), place(fields)].filter((c): c is QaCheck => c !== null);
  const verdict = worst(checks);
  const warnings = checks.filter((c) => c.verdict === "warning").length;
  const headline = verdict === "stop" ? "Stop: the result does not hold up"
    : verdict === "warning" ? `Pass with ${warnings === 1 ? "a warning" : `${warnings} warnings`}` : "Pass";
  return { verdict, headline, checks };
}

const NAMES: Record<QaCheck["id"], string> = { reference: "reference solver", mesh: "mesh study", equilibrium: "equilibrium", place: "where it is read" };

/** The step's one line for the plan, as it is reported (ADR-0144): the verdict and the first check that set it, or the checks that passed. */
export function qaNote(reading: QaReading): string {
  const first = reading.checks.find((c) => c.verdict === reading.verdict && reading.verdict !== "pass");
  return first ? `${reading.headline}. ${first.line}.` : `${reading.headline}: ${listed(reading.checks.map((c) => NAMES[c.id]))}.`;
}
