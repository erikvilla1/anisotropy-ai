/**
 * The words the workspace shows a customer (ADR-0091, docs/copy-style-guide.md): the run's five steps mapped from the pipeline's
 * stage names, the run's state in a word, a stopped run in plain language, the verification line, and the download names. The
 * pipeline and the API keep their own names; this file is where they become the product's. `BANNED_TERMS` is the one list the page's
 * guard (`customerText`) and the browser test read.
 */
import type { JobStatus } from "./studio-api";
import { formatNumber, inProse } from "./number-format";

/** What an outage says, on the calculator and in the workspaces: what happened and what to do (style guide, rule 8). */
export const ANALYSIS_UNAVAILABLE = "Analysis is unavailable right now. Your inputs are kept; try again in a minute, and contact us if it continues.";
/** A job the API no longer has: an old viewer link, or a job of a container that has since restarted (ADR-0091 amendment 2). */
export const JOB_GONE = "These results are no longer available. Run the analysis again from your project.";
/** Results whose file the page cannot read; the reason goes to the console, never to the screen. */
export const RESULTS_UNREADABLE = "The results could not be read. Reload the page; if it happens again, contact us.";
/** Any other answer the page cannot read. */
export const ANSWER_UNREADABLE = "The answer could not be read. Reload the page; if it happens again, contact us.";
/** What failed, by the request's name (`what` in `lib/studio-api.ts`), when the service's own words cannot be shown (audit fea-run-48). */
export const FAILED_WORDS: Record<string, string> = {
  "the setup check": "The setup could not be checked",
  "the preview": "The preview could not be loaded",
  "the tow calculation": "The tow calculation could not be run",
  "starting the analysis": "The analysis could not be started",
  "the analysis's progress": "The analysis's progress could not be read",
  "the analyses": "The analyses could not be loaded",
  "the projects": "Your projects could not be loaded",
  "saving the project": "The project could not be saved",
  "the project": "This project could not be opened",
  "renaming the project": "The project could not be renamed",
  "the coupons": "The coupons could not be loaded",
  "the coupon's values": "The coupon could not be opened",
  "the results": "The results could not be loaded",
  "the explanation": "The explanation could not be loaded",
  "the laminate solve": "The laminate could not be solved",
  "the proposals": "The message could not be read",
  "the tests offered": "The tests offered could not be loaded",
  "the assistant": "The assistant could not be reached",
};
/** A failed request in words: what failed, then what to do. */
export const failedText = (what: string): string =>
  `${FAILED_WORDS[what] ?? `${sentence(what)} could not be completed`}. Reload the page; if it happens again, contact us.`;

/** Words that never reach a customer's screen: our tools and vendors, our records and scripts, the team's own language and machinery. */
export const BANNED_TERMS: { label: string; pattern: RegExp }[] = [
  { label: "Anthropic", pattern: /anthropic/i },
  { label: "Claude", pattern: /\bclaude\b/i },
  { label: "Abaqus", pattern: /abaqus/i },
  { label: "PrePoMax", pattern: /prepomax/i },
  { label: "CalculiX", pattern: /calculix|\bccx\b/i },
  { label: "SPOOLES", pattern: /spooles/i },
  { label: ".py", pattern: /\.py\b/i },
  { label: ".toml", pattern: /\.toml\b/i },
  { label: "the founder", pattern: /\bthe founder\b/i },
  { label: "for the team", pattern: /\bfor the team\b/i },
  { label: "free solver", pattern: /\bfree solver\b|\bsolver is free\b/i },
  { label: "our engine", pattern: /\bour (engine|kernel)\b/i },
  { label: "engine", pattern: /\bengines?\b/i },
  { label: "decks", pattern: /\bdecks\b/i },
  { label: "case runner", pattern: /\bcase runner\b/i },
  { label: "ADR number", pattern: /\bADR-\d{4}\b/ },
  { label: "environment variable", pattern: /\bNEXT_PUBLIC_|\bANISOTROPY_[A-Z_]+\b/ },
  // the service's machinery (audit fea-screens-2, fea-screens-19): its endpoints, its parts and its records
  { label: "endpoint", pattern: /\/v1\// },
  { label: "API", pattern: /\bAPI\b/ },
  { label: "Worker", pattern: /\bWorker\b/ },
  { label: "jobs table", pattern: /\bjobs? table\b/i },
  { label: "run records", pattern: /\brun records?\b/i },
  { label: "database", pattern: /\bdatabases?\b/i },
  { label: "set name", pattern: /\bGrip-(?:Top|Bottom)\b/ },
];

/** The one phrase that names a banned tool and may still be shown: the customer's solver file, which opens in Abaqus (the audit's D18:
 * "Abaqus input file (.inp)" on the site and in the workspace, the founder's "accept" of 2026-11-12). */
export const ALLOWED_PHRASE = /Abaqus input file \(\.inp\)/g;

/** The banned terms a text holds, by label; empty when it is fit to show. */
export function bannedIn(text: string): string[] {
  const shown = text.replace(ALLOWED_PHRASE, "");
  return BANNED_TERMS.filter((t) => t.pattern.test(shown)).map((t) => t.label);
}

/** What the card of the user's own Abaqus may name (ADR-0094 part 7, a change to ADR-0091): Abaqus, because there it is the user's own
 * program and not a tool of ours, and the connector's file, which the user runs by its name. Everything else stays banned there too. */
export const ABAQUS_CARD_ALLOWS = ["Abaqus", ".py"];
/** The banned terms a text of that card holds, by label. */
export function bannedInAbaqusCard(text: string): string[] {
  return bannedIn(text).filter((label) => !ABAQUS_CARD_ALLOWS.includes(label));
}

/** A file path with a file name ("tools/run.py"), or a folder path of two or more folders ("fea/checks/unnotched-im7-8552/"); a layup
 * ("[45/0/-45/90]s") or a material ("IM7/8552") is neither. */
const PATH = /(^|\s)\.?\/?[\w.-]+\/[\w./-]+\.\w+|(^|[\s("'])[A-Za-z_.][\w.-]*\/[\w.-]+\//;

/** A job's or a project's id ("0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00"): never in a message, though an address may carry one. */
const ID = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i;

/** A message from the API or the pipeline, shown as it is only when it holds no banned term, no file or folder path, no id and no exit
 * code; null otherwise, so the page says the plain thing instead. */
export function customerText(text: string | null | undefined): string | null {
  if (!text) return null;
  const trimmed = text.trim();
  if (!trimmed || bannedIn(trimmed).length) return null;
  if (/[A-Za-z]:\\|exited with code|Traceback|\bat line \d+/i.test(trimmed) || PATH.test(trimmed) || ID.test(trimmed)) return null;
  return trimmed;
}

/** A coupon's record name at the head of a sentence ("IM7-UNT-L1, unnotched tension, ..."), which jobs solved before ADR-0091 amendment 2
 * still carry: the material code, the test code and the layup code. */
const DESIGNATION_HEAD = /^[A-Z][A-Z0-9]*-[A-Z0-9]{2,4}-L[1-9]\d*,\s*/;

/** A sentence of the explanation as the page shows it: an aside about another program's viewer, which jobs solved before ADR-0091 still
 * carry, is cut, and so is a record's name at its head; a sentence that still holds a banned term is left out; its numbers read as the
 * page prints them ("1.622e+04" from an older job is "16220", "1.5e+06" is "1.5 × 10⁶", the minus sign; ADR-0091 amendment 1). */
export function shownSentence(text: string): string | null {
  const symbols = withSymbols(text);
  const named = DESIGNATION_HEAD.test(symbols) ? sentence(symbols.replace(DESIGNATION_HEAD, "")) : symbols; // the test opens the sentence then
  const shown = customerText(named.replace(/;\s*these are element centroids[^.;]*?,?\s*not the [^.;]*?a viewer such as PrePoMax shows\./, "."));
  return shown === null ? null : inProse(shown);
}

/** The ASCII names the explanation templates and the chat's echoes write (eps_x, gamma_xy, sigma_2, tau12, nu_xy, E1, G12) as the
 * symbols the rest of the page uses. */
const SYMBOLS: [RegExp, string][] = [
  [/\beps_x\b/g, "εx"], [/\beps_y\b/g, "εy"], [/\bgamma_xy\b/g, "γxy"], [/\bnu_xy\b/g, "νxy"], [/\bnu_?12\b/g, "ν₁₂"],
  [/\bsigma_?1\b/g, "σ₁"], [/\bsigma_?2\b/g, "σ₂"], [/\btau_?12\b/g, "τ₁₂"], [/\bkappa_x\b/g, "κx"], [/\bkappa_y\b/g, "κy"], [/\bkappa_xy\b/g, "κxy"],
  [/\bE1\b/g, "E₁"], [/\bE2\b/g, "E₂"], [/\bG12\b/g, "G₁₂"],
];
export const withSymbols = (text: string): string => SYMBOLS.reduce((out, [pattern, symbol]) => out.replace(pattern, symbol), text);

/** Sentence case: the first letter up, the rest as written. */
export const sentence = (text: string): string => (text ? text.charAt(0).toUpperCase() + text.slice(1) : text);

/** A setup-check item's message as the page shows it: the package's words when they are fit to show, else the plain state. The
 * environment items (the reference solver, the document builder) name paths and programs, which stay in the check's record. An item
 * the engineer can act on names its inputs when its own words cannot be shown, so it is never a dead end (audit repository-2). */
export function checkText(item: { state: string; message: string; rows?: string[] }): string {
  const said = customerText(item.message);
  if (said) return said;
  if (item.state === "pass") return "Ready.";
  if (item.state === "warn") return "Review this setting.";
  if (item.state === "pending") return "Not checked yet.";
  const rows = [...new Set(item.rows ?? [])].filter((row) => customerText(row) !== null);
  if (rows.length) return `${item.state === "missing" ? "Inputs to fill in" : "Inputs to change"}: ${rows.join(", ")}.`;
  if (item.rows?.length) return item.state === "missing" ? "Fill in the inputs listed." : "Change the inputs listed.";
  return "Not available right now. Try again later, or contact us.";
}

/** The problem a check item names for each of its rows (audit fea-run-49), by label: the item's message split where the package joined
 * its problems ("; " outside parentheses), each problem given to the rows its head names ("Length (mm): required", "A, B and C: ...")
 * as words fit to show. A row no problem names gets "Check this value.", unless the item's one problem names a group of rows rather than
 * a field ("Own material strengths: enter all five, or none"), which is every row's; `isField` tells a field's label from a group's. */
export function rowProblems(item: { message: string; rows: string[] }, isField: (label: string) => boolean = () => true): Record<string, string> {
  const parts: { named: string[]; words: string }[] = [];
  let depth = 0, start = 0;
  const pieces: string[] = [];
  for (let i = 0; i < item.message.length; i++) {
    const char = item.message[i];
    depth += char === "(" ? 1 : char === ")" ? -1 : 0;
    if (depth <= 0 && item.message.startsWith("; ", i)) { pieces.push(item.message.slice(start, i)); start = i + 2; }
  }
  pieces.push(item.message.slice(start));
  const stems = (label: string) => [label, label.split(" (")[0]];
  for (const piece of pieces) {
    let rest = piece;
    const named: string[] = [];
    for (;;) {
      const label = item.rows.filter((l) => stems(l).some((s) => rest.startsWith(s) && /^($|[:, ])/.test(rest.slice(s.length))))
        .sort((a, b) => b.length - a.length)[0];
      if (!label) break;
      named.push(label);
      rest = rest.slice(stems(label).find((s) => rest.startsWith(s))!.length);
      const separator = /^(, | and | or )/.exec(rest);
      if (!separator) break;
      rest = rest.slice(separator[0].length);
    }
    const words = rest.replace(/^:\s*/, "").trim();
    if (!named.length && parts.length && !piece.includes(": ")) parts[parts.length - 1].words += `; ${piece}`; // the rest of the previous problem
    else parts.push({ named, words: named.length ? words : piece.trim() });
  }
  const shown = (words: string) => {
    const said = customerText(words);
    return said ? `${sentence(said).replace(/[.;,:]$/, "")}.` : "Check this value.";
  };
  const out: Record<string, string> = {};
  for (const part of parts) for (const label of part.named) out[label] ??= shown(part.words);
  const group = parts.length === 1 && parts[0].named.length > 0 && !parts[0].named.some(isField) ? shown(parts[0].words) : null;
  for (const label of item.rows) out[label] ??= group ?? "Check this value.";
  return out;
}

// ------------------------------------------------------------------------------------------------------------- the run's steps

export type RunStepId = "queued" | "meshing" | "solving" | "post" | "report";
export const RUN_STEPS: { id: RunStepId; label: string; doing: string }[] = [
  { id: "queued", label: "Queued", doing: "Queued" },
  { id: "meshing", label: "Meshing", doing: "Meshing" },
  { id: "solving", label: "Solving", doing: "Solving" },
  { id: "post", label: "Post-processing", doing: "Post-processing" },
  { id: "report", label: "Report ready", doing: "Writing the report" },
];

/** The pipeline's stage names (fea/tools/run_coupon.py STAGES) and the step each belongs to. A stage this list does not know counts as
 * solving, the step a new stage is most likely to join. */
const STAGE_STEP: Record<string, RunStepId> = {
  "the setup check": "meshing", "the input": "meshing", "the decks": "meshing", "the attempt": "meshing",
  "our engine": "solving", "the convergence study": "solving", "CalculiX": "solving",
  "the CalculiX record": "post", "the result": "post", "the drawings": "post",
  "the package": "report", "the outputs": "report",
};
export const stepOfStage = (stage: string | null | undefined): RunStepId => (stage ? STAGE_STEP[stage] ?? "solving" : "meshing");
/** The step a job is at: a job that ended before any stage (refused at the gate, or never taken up) ended in the queue. */
const stepOfJob = (job: Pick<JobStatus, "state" | "stage">): RunStepId =>
  !job.stage && (job.state === "stopped" || job.state === "refused") ? "queued" : stepOfStage(job.stage);
/** A finished job whose report was not written: the outcome says so, or (a job read back from its row) no package was stored. */
const reportMissing = (job: Pick<JobStatus, "documents"> & { outputs?: JobStatus["outputs"] }): boolean =>
  job.documents ? job.documents !== "written" : job.outputs !== undefined && !("package" in job.outputs);
const order = (id: RunStepId) => RUN_STEPS.findIndex((s) => s.id === id);

export type StepState = "done" | "current" | "waiting" | "stopped";
/** Each step's state for a job: everything before the job's step done, its step current (or stopped), the rest waiting. */
export function runSteps(job: Pick<JobStatus, "state" | "stage" | "documents"> & { outputs?: JobStatus["outputs"] }): { id: RunStepId; label: string; state: StepState }[] {
  const at = job.state === "queued" ? "queued" : job.state === "done" ? null : stepOfJob(job);
  return RUN_STEPS.map((s) => {
    if (at === null) return { ...s, state: s.id === "report" && reportMissing(job) ? "stopped" : "done" };
    const k = order(s.id), here = order(at);
    const state: StepState = k < here ? "done" : k > here ? "waiting" : job.state === "stopped" || job.state === "refused" ? "stopped" : "current";
    return { ...s, state };
  });
}

/** How many jobs are ahead of a queued one, read from the API's message ("queued; 2 ahead", or the older "…; 2 job(s) ahead…"). */
export function queueAhead(message: string | null | undefined): number | null {
  const m = message?.match(/(\d+)\s+(?:job\(s\)\s+)?ahead/);
  return m ? Number(m[1]) : null;
}

/** The run in a few words: "Queued (1 ahead)", "Solving", "Done", "Stopped". */
export function runHeadline(job: Pick<JobStatus, "state" | "stage" | "message" | "result" | "documents"> & { outputs?: JobStatus["outputs"] }): string {
  if (job.state === "queued") {
    const ahead = queueAhead(job.message);
    return ahead ? `Queued (${ahead} ahead)` : "Queued";
  }
  if (job.state === "running") return RUN_STEPS[order(stepOfStage(job.stage))].doing;
  if (job.state === "done") return reportMissing(job) ? "Done, report not written" : "Done";
  if (job.state === "refused") return "Not started";
  return "Stopped";
}

const STEP_WORDS: Record<RunStepId, string> = { queued: "before it started", meshing: "while meshing", solving: "while solving", post: "during post-processing", report: "while writing the report" };

/** What went wrong and what to do next, in plain words; the pipeline's own message only when it is fit to show. */
export function runProblem(job: Pick<JobStatus, "state" | "stage" | "message" | "documents"> & { outputs?: JobStatus["outputs"] }): string | null {
  if (job.state === "refused") {
    const said = customerText(job.message);
    return `The analysis did not start${said ? `: ${said.replace(/\.$/, "")}` : ""}. Check the setup and run it again.`;
  }
  if (job.state === "stopped") {
    return `The analysis stopped ${STEP_WORDS[stepOfJob(job)]}. Run it again; if it stops again, contact us.`;
  }
  if (job.state === "done" && reportMissing(job)) return "The results are ready, but the report could not be written. Run the analysis again to retry.";
  return null;
}

/** One line on what the run has done so far, under the headline. */
export function runDetail(job: Pick<JobStatus, "state" | "stage" | "result"> & { message?: string | null }): string {
  if (job.state === "queued") {
    const ahead = queueAhead(job.message);
    return ahead ? `Waiting for the ${ahead === 1 ? "run" : `${ahead} runs`} ahead.` : "The analysis starts in a moment.";
  }
  if (job.state !== "running") return "";
  const step = stepOfStage(job.stage);
  if (job.result || step === "report") return "Results are ready. The report follows.";
  if (step === "post") return "Checking the result against the reference solver.";
  return "Results appear as soon as the solve finishes.";
}

// --------------------------------------------------------------------------------------------------------------- verification

export type Verification = { line: string; verified: boolean };
/** The reference solver's check in one line, from the summary the package wrote when it is there, else from the result line the
 * pipeline reported ("57 of 57 recorded values agree with …"); null before the reference solver has run. "Verified" only when every
 * value agrees; otherwise the line says how many did, and `verified` is false so the page does not show it as a pass. */
export function verificationOf(result: string | null | undefined, beside?: { agree: string; tolerance: number } | null): Verification | null {
  const counted = beside && /\d+\s+of\s+\d+/.test(beside.agree) ? beside.agree.match(/(\d+)\s+of\s+(\d+)/)
    : result?.match(/(\d+)\s+of\s+(\d+)\s+recorded values agree/);
  if (!counted) return null;
  const [agree, of] = [Number(counted[1]), Number(counted[2])];
  const how = beside && /\d+\s+of\s+\d+/.test(beside.agree) ? `within ${Number((100 * beside.tolerance).toPrecision(3))} %` : "agree";
  return agree === of && of > 0
    ? { line: `Verified against reference solver: ${agree} of ${of} values ${how}`, verified: true }
    : { line: `Reference solver check: ${agree} of ${of} values ${how}`, verified: false };
}

/** The run's state in the side panel: the plain problem when it ended badly, else done with where the files are, else the headline. No
 * position words: below 1100 px the results sit under the setup, not in a centre column (audit fea-run-50). */
export function runStatus(job: Parameters<typeof runProblem>[0] & Pick<JobStatus, "result">, filesUnder: string): string {
  return runProblem(job) ?? (job.state === "done" ? `Done. Download the report and files under ${filesUnder}.`
    : `${runHeadline(job)}${job.state === "running" ? "…" : "."}`);
}

// --------------------------------------------------------------------------------------------------------------- the downloads

/** The files a job offers, in the order the page lists them, with their plain names (ADR-0091). The keys are the pipeline's. */
export const DOWNLOAD_LABELS: [string, string][] = [
  ["document", "Report (PDF)"],
  ["package", "Full package (ZIP)"],
  ["abaqus_deck", "Abaqus input file (.inp)"],
  ["prepomax_deck", "Reference solver input (.inp)"],
  ["prepomax_results", "Reference solver results (.frd)"],
];
/** What a customer downloads (decision D4, ADR-0091 amendment 2): the report and the solver input. The full package, the reference solver's
 * input and its results are the team's verification material, offered only where every test is (the development switch). */
export const CUSTOMER_DOWNLOADS: readonly string[] = ["document", "abaqus_deck"];
/** The files offered, in order: the customer's, or every one with the development switch on. */
export const downloadsFor = (all: boolean): [string, string][] => DOWNLOAD_LABELS.filter(([key]) => all || CUSTOMER_DOWNLOADS.includes(key));
/** The neutral name a file is asked for by (ADR-0091 amendment 2): what it is, not the program it is for; the API maps it back. */
export const FILE_URL_KEY: Record<string, string> = { abaqus_deck: "solver_input", prepomax_deck: "reference_input", prepomax_results: "reference_results" };
const DOWNLOAD_SUFFIX: Record<string, string> = {
  document: "_report.pdf", package: "_package.zip", abaqus_deck: "_solver.inp", prepomax_deck: "_reference.inp", prepomax_results: "_reference.frd",
  abaqus_build: "_build.py", // the script that builds the coupon in Abaqus/CAE: offered on the Abaqus card alone, never in the list of files
};

/** What a downloaded file is called: the standard and the layup, then what it is, e.g. `D3039_[45,0,-45,90]s_report.pdf`; the plies are
 * parted by commas, so a −45 ply reads as one (audit fea-run-39). Only letters, digits and `_ . , ( ) [ ] + -` survive, which the API
 * accepts as a file name. */
export function downloadName(key: string, coupon: { standard?: string | null; test?: string | null; layup?: string | null }): string {
  const standard = coupon.standard?.match(/\bD\d{3,4}\b/)?.[0];
  const test = (coupon.test ?? "").split(/\s+/).filter(Boolean).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join("");
  const layup = (coupon.layup ?? "").replace(/±/g, "+-").replace(/\//g, ",").replace(/\s+/g, "");
  const base = [standard ?? (test || "Coupon"), layup].filter(Boolean).join("_").replace(/[^A-Za-z0-9_.,()[\]+-]/g, "-");
  return `${base.slice(0, 100)}${DOWNLOAD_SUFFIX[key] ?? ""}`;
}

// ------------------------------------------------------------------------------------------- what is held and what is loaded

/** The mesh's set names in words (audit fea-run-16): the grips, the supports and the loading noses; a plate's own region names as written. */
const SET_WORDS: Record<string, string> = { "Grip-Bottom": "bottom grip", "Grip-Top": "top grip", "Support-Left": "left support", "Support-Right": "right support",
  "Pin-Left": "left pin", "Pin-Right": "right pin" };
export const setWords = (set: string): string => SET_WORDS[set] ?? (/^Nose/.test(set) ? "loading nose" : set);

/** A held set in one line, every direction it holds merged: "Bottom grip: fixed", "Top grip: free to move along the coupon only", or the
 * directions ("Left support: held along z"). `dofs` 1-3 are x, y, z and 4-6 the rotations about them; y runs along a coupon. */
export function heldWords(set: string, dofs: number[], directions: string[]): string {
  const held = new Set(dofs);
  const name = sentence(setWords(set));
  if ([1, 2, 3, 4, 5, 6].every((d) => held.has(d))) return `${name}: fixed`;
  if (!held.has(2) && [1, 3, 4, 5, 6].every((d) => held.has(d))) return `${name}: free to move along the coupon only`;
  return `${name}: held along ${[...new Set(directions)].join(", ")}`;
}

/** What a loaded set does, in the words the results use: "Top grip: pulled 1 mm along the coupon", "Top grip: pulled by 10000 N along the
 * coupon"; a load across or out of the plane names its direction. */
export function loadWords(load: { set: string; control: string; dof: number; direction: string; value: number; unit: string }): string {
  const name = sentence(setWords(load.set));
  const printed = (value: number) => formatNumber(value, { zeros: false }); // a readout: no trailing zeros
  const amount = `${printed(Math.abs(load.value))} ${load.unit}`;
  if (load.dof === 2 && (load.control === "displacement" || load.control === "force")) {
    const verb = load.value < 0 ? "pushed" : "pulled";
    return `${name}: ${verb} ${load.control === "force" ? "by " : ""}${amount} along the coupon`;
  }
  return `${name}: ${load.control} ${printed(load.value)} ${load.unit} along ${load.direction}`;
}
