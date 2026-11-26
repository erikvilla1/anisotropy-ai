/** A person's past analyses (ADR-0109): the list is their own coupon jobs as the API keeps them (ADR-0104), each finished run with the
 * answer the fea package wrote for it; one is opened again from the files that run stored, its own rows among them. The page computes
 * nothing (ADR-0051): every value here is picked and worded. */
import { BASIS_WORDS, CRITERION_NAMES } from "./studio-answer";
import type { Basis, JobStatus } from "./studio-api";

/** A done run's answer in a few values, as the package wrote it: on the gauge section, a plate away from its held corners (ADR-0108 amendment 2)
 * or the whole model, by the criterion that governs. */
export type JobAnswer = { basis: Basis; criterion: string; fails: boolean; factor: number; ply: number; angle: number; face: string | null };

/** The answer as a job's status carries it, checked before it is shown; null for anything else. */
export function readJobAnswer(value: unknown): JobAnswer | null {
  if (typeof value !== "object" || value === null) return null;
  const a = value as Record<string, unknown>;
  const ok = (a.basis === "gauge" || a.basis === "away" || a.basis === "whole") && typeof a.criterion === "string" && typeof a.fails === "boolean"
    && typeof a.factor === "number" && Number.isFinite(a.factor) && typeof a.ply === "number" && Number.isInteger(a.ply)
    && typeof a.angle === "number" && Number.isFinite(a.angle) && (a.face === null || a.face === undefined || typeof a.face === "string");
  return ok ? { basis: a.basis as Basis, criterion: a.criterion as string, fails: a.fails as boolean, factor: a.factor as number,
    ply: a.ply as number, angle: a.angle as number, face: (a.face as string | null | undefined) ?? null } : null;
}

export type PastRun = {
  job_id: string; coupon: string; finished_at: string; answer: JobAnswer | null;
  /** Whether the run kept its own rows, so its setup can be taken up again as it was; a run from before they were kept did not. */
  keepsRows: boolean;
};

/** The runs a person can open again: those that ended done with results to show, in the order given (the API's, newest first). */
export function pastRuns(jobs: JobStatus[]): PastRun[] {
  return jobs.filter((job) => job.state === "done" && "fields" in job.outputs && Boolean(job.coupon))
    .map((job) => ({ job_id: job.job_id, coupon: job.coupon ?? "", finished_at: job.finished_at ?? job.started_at, answer: readJobAnswer(job.answer),
      keepsRows: "values" in job.outputs }));
}

export type AnswerWords = { verdict: "Holds" | "Fails"; /** "1.033 × the applied load" */ loading: string; /** ["ply 4 (90°)", "Tsai-Hill"] */ facts: string[] };

/** The answer in the list's words: the verdict, the factor on the applied loading at first-ply failure, then the ply and the criterion.
 * Every number is the package's, printed by `print`. Null when the run kept no answer. */
export function answerWords(answer: JobAnswer | null, print: (value: number) => string): AnswerWords | null {
  if (!answer) return null;
  const ply = `ply ${answer.ply} (${answer.angle}°)${answer.face ? `, ${answer.face} face` : ""}`;
  return { verdict: answer.fails ? "Fails" : "Holds", loading: `${print(answer.factor)} × the applied load`,
    facts: [ply, CRITERION_NAMES[answer.criterion] ?? answer.criterion, BASIS_WORDS[answer.basis].replace(/^the /, "")] };
}

/** When a run ended, in the reader's own date and time; empty for a stamp that is not one. */
export function runWhen(stamp: string, locale?: string): string {
  const date = new Date(stamp);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
}

/** The run the workspace is asked to open, passed from the list to the workspace through this tab's session storage: an id of the
 * person's own job, nothing else, taken once. Blocked storage opens nothing. */
export const OPEN_RUN_KEY = "anisotropy.open-run.v1";
const RUN_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function askToOpen(storage: Pick<Storage, "setItem"> | null, jobId: string): boolean {
  if (!storage || !RUN_ID.test(jobId)) return false;
  try { storage.setItem(OPEN_RUN_KEY, jobId); return true; } catch { return false; }
}

export function takeRunToOpen(storage: Pick<Storage, "getItem" | "removeItem"> | null): string | null {
  if (!storage) return null;
  try {
    const kept = storage.getItem(OPEN_RUN_KEY);
    storage.removeItem(OPEN_RUN_KEY);
    return kept && RUN_ID.test(kept) ? kept : null;
  } catch { return null; }
}
