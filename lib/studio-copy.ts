/**
 * The words the workspace shows a customer (ADR-0091, docs/copy-style-guide.md): the run's five steps mapped from the pipeline's
 * stage names, the run's state in a word, a stopped run in plain language, the verification line, and the download names. The
 * pipeline and the API keep their own names; this file is where they become the product's. `BANNED_TERMS` is the one list the page's
 * guard (`customerText`) and the browser test read.
 */
import type { JobStatus } from "./studio-api";

/** Words that never reach a customer's screen: our tools and vendors, our records and scripts, the team's own language. */
export const BANNED_TERMS: { label: string; pattern: RegExp }[] = [
  { label: "Anthropic", pattern: /anthropic/i },
  { label: "Claude", pattern: /\bclaude\b/i },
  { label: "Abaqus", pattern: /abaqus/i },
  { label: "PrePoMax", pattern: /prepomax/i },
  { label: "CalculiX", pattern: /calculix|\bccx\b/i },
  { label: ".py", pattern: /\.py\b/i },
  { label: ".toml", pattern: /\.toml\b/i },
  { label: "the founder", pattern: /\bthe founder\b/i },
  { label: "for the team", pattern: /\bfor the team\b/i },
  { label: "free solver", pattern: /\bfree solver\b/i },
  { label: "our engine", pattern: /\bour (engine|kernel)\b/i },
  { label: "ADR number", pattern: /\bADR-\d{4}\b/ },
  { label: "environment variable", pattern: /\bNEXT_PUBLIC_|\bANISOTROPY_[A-Z_]+\b/ },
];

/** The banned terms a text holds, by label; empty when it is fit to show. */
export function bannedIn(text: string): string[] {
  return BANNED_TERMS.filter((t) => t.pattern.test(text)).map((t) => t.label);
}

/** A message from the API or the pipeline, shown as it is only when it holds no banned term, no file path and no exit code; null
 * otherwise, so the page says the plain thing instead. */
export function customerText(text: string | null | undefined): string | null {
  if (!text) return null;
  const trimmed = text.trim();
  if (!trimmed || bannedIn(trimmed).length) return null;
  if (/[A-Za-z]:\\|(^|\s)\.?\/?[\w.-]+\/[\w./-]+\.\w+|exited with code|Traceback|\bat line \d+/i.test(trimmed)) return null;
  return trimmed;
}

/** A sentence of the explanation as the page shows it: an aside about another program's viewer, which jobs solved before ADR-0091 still
 * carry, is cut; a sentence that still holds a banned term is left out. */
export function shownSentence(text: string): string | null {
  return customerText(withSymbols(text).replace(/;\s*these are element centroids[^.;]*?,?\s*not the [^.;]*?a viewer such as PrePoMax shows\./, "."));
}

/** The ASCII names the explanation templates write (eps_x, gamma_xy, sigma_2, tau12, nu_xy) as the symbols the rest of the page uses. */
const SYMBOLS: [RegExp, string][] = [
  [/\beps_x\b/g, "εx"], [/\beps_y\b/g, "εy"], [/\bgamma_xy\b/g, "γxy"], [/\bnu_xy\b/g, "νxy"], [/\bnu_?12\b/g, "ν₁₂"],
  [/\bsigma_?1\b/g, "σ₁"], [/\bsigma_?2\b/g, "σ₂"], [/\btau_?12\b/g, "τ₁₂"], [/\bkappa_x\b/g, "κx"], [/\bkappa_y\b/g, "κy"], [/\bkappa_xy\b/g, "κxy"],
];
export const withSymbols = (text: string): string => SYMBOLS.reduce((out, [pattern, symbol]) => out.replace(pattern, symbol), text);

/** Sentence case: the first letter up, the rest as written. */
export const sentence = (text: string): string => (text ? text.charAt(0).toUpperCase() + text.slice(1) : text);

/** A setup-check item's message as the page shows it: the package's words when they are fit to show, else the plain state. The
 * environment items (the reference solver, the document builder) name paths and programs, which stay in the check's record. */
export function checkText(item: { state: string; message: string }): string {
  const said = customerText(item.message);
  if (said) return said;
  if (item.state === "pass") return "Ready.";
  if (item.state === "warn") return "Review this setting.";
  return "Not available right now. Try again later, or contact us.";
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
const order = (id: RunStepId) => RUN_STEPS.findIndex((s) => s.id === id);

export type StepState = "done" | "current" | "waiting" | "stopped";
/** Each step's state for a job: everything before the job's step done, its step current (or stopped), the rest waiting. */
export function runSteps(job: Pick<JobStatus, "state" | "stage" | "documents">): { id: RunStepId; label: string; state: StepState }[] {
  const at = job.state === "queued" ? "queued" : job.state === "done" ? null : stepOfStage(job.stage);
  return RUN_STEPS.map((s) => {
    if (at === null) return { ...s, state: s.id === "report" && job.documents && job.documents !== "written" ? "stopped" : "done" };
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
export function runHeadline(job: Pick<JobStatus, "state" | "stage" | "message" | "result" | "documents">): string {
  if (job.state === "queued") {
    const ahead = queueAhead(job.message);
    return ahead ? `Queued (${ahead} ahead)` : "Queued";
  }
  if (job.state === "running") return RUN_STEPS[order(stepOfStage(job.stage))].doing;
  if (job.state === "done") return job.documents && job.documents !== "written" ? "Done, report not written" : "Done";
  if (job.state === "refused") return "Not started";
  return "Stopped";
}

const STEP_WORDS: Record<RunStepId, string> = { queued: "in the queue", meshing: "while meshing", solving: "while solving", post: "during post-processing", report: "while writing the report" };

/** What went wrong and what to do next, in plain words; the pipeline's own message only when it is fit to show. */
export function runProblem(job: Pick<JobStatus, "state" | "stage" | "message" | "documents">): string | null {
  if (job.state === "refused") {
    const said = customerText(job.message);
    return `The analysis did not start${said ? `: ${said.replace(/\.$/, "")}` : ""}. Check the setup and run it again.`;
  }
  if (job.state === "stopped") {
    return `The analysis stopped ${STEP_WORDS[stepOfStage(job.stage)]}. Run it again; if it stops again, contact us.`;
  }
  if (job.state === "done" && job.documents && job.documents !== "written") return "The results are ready, but the report could not be written. Run the analysis again to retry.";
  return null;
}

/** One line on what the run has done so far, under the headline. */
export function runDetail(job: Pick<JobStatus, "state" | "stage" | "result">): string {
  if (job.state === "queued") return "The analysis starts when a solver is free.";
  if (job.state !== "running") return "";
  const step = stepOfStage(job.stage);
  if (job.result || step === "report") return "Results are ready. The report follows.";
  if (step === "post") return "Checking the result against the reference solver.";
  return "Results appear as soon as the solve finishes.";
}

// --------------------------------------------------------------------------------------------------------------- verification

/** "Verified against reference solver: 57 of 57 values within 3 %", from the summary the package wrote when it is there, else from
 * the result line the pipeline reported ("57 of 57 recorded values agree with …"); null before the reference solver has run. */
export function verificationLine(result: string | null | undefined, beside?: { agree: string; tolerance: number } | null): string | null {
  if (beside && /\d+\s+of\s+\d+/.test(beside.agree)) {
    const within = Number((100 * beside.tolerance).toPrecision(3));
    return `Verified against reference solver: ${beside.agree.match(/\d+\s+of\s+\d+/)![0]} values within ${within} %`;
  }
  const m = result?.match(/(\d+)\s+of\s+(\d+)\s+recorded values agree/);
  return m ? `Verified against reference solver: ${m[1]} of ${m[2]} values agree` : null;
}

// --------------------------------------------------------------------------------------------------------------- the downloads

/** The files a job offers, in the order the page lists them, with their plain names (ADR-0091). The keys are the pipeline's. */
export const DOWNLOAD_LABELS: [string, string][] = [
  ["document", "Report (PDF)"],
  ["package", "Full package (ZIP)"],
  ["abaqus_deck", "Solver input (.inp)"],
  ["prepomax_deck", "Reference solver input (.inp)"],
  ["prepomax_results", "Reference solver results (.frd)"],
];
const DOWNLOAD_SUFFIX: Record<string, string> = {
  document: "_report.pdf", package: "_package.zip", abaqus_deck: "_solver.inp", prepomax_deck: "_reference.inp", prepomax_results: "_reference.frd",
};

/** What a downloaded file is called: the standard and the layup, then what it is, e.g. `D3039_[45-0--45-90]s_report.pdf`. Only
 * letters, digits and `_ . , ( ) [ ] + -` survive, which the API accepts as a file name. */
export function downloadName(key: string, coupon: { standard?: string | null; test?: string | null; layup?: string | null }): string {
  const standard = coupon.standard?.match(/\bD\d{3,4}\b/)?.[0];
  const test = (coupon.test ?? "").split(/\s+/).filter(Boolean).map((w) => w.charAt(0).toUpperCase() + w.slice(1)).join("");
  const layup = (coupon.layup ?? "").replace(/±/g, "+-").replace(/\//g, "-").replace(/\s+/g, "");
  const base = [standard ?? (test || "Coupon"), layup].filter(Boolean).join("_").replace(/[^A-Za-z0-9_.,()[\]+-]/g, "-");
  return `${base.slice(0, 100)}${DOWNLOAD_SUFFIX[key] ?? ""}`;
}
