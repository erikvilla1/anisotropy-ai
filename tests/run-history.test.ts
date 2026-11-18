import assert from "node:assert/strict";
import test from "node:test";
import { answerWords, askToOpen, OPEN_RUN_KEY, pastRuns, readJobAnswer, runWhen, takeRunToOpen } from "../lib/run-history";
import { readJob, type JobStatus } from "../lib/studio-api";
import { printed } from "../lib/studio-colors";

const ANSWER = { basis: "gauge", criterion: "tsai_hill", fails: false, factor: 1.0334, ply: 4, angle: 90, face: null };
const job = (changes: Partial<JobStatus> & { answer?: unknown }): JobStatus => readJob({
  job_id: "0b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11", state: "done", actor: "studio", started_at: "2026-11-16T22:10:00+00:00", finished_at: "2026-11-16T22:12:00+00:00",
  coupon: "IM7-UNT-L1", attempt: "attempt-02_2026-11-16", message: "57 of 57 recorded values agree with CalculiX", stage: "the outputs", stages_done: [], stages: [],
  outputs: { fields: "a/fields.json", values: "a/values.json" }, run_id: null, log_tail: [], ...changes });

test("the list holds the finished runs that have results, each with the answer the package wrote (ADR-0109)", () => {
  const runs = pastRuns([
    job({ answer: ANSWER }),
    job({ job_id: "1b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11", outputs: { fields: "b/fields.json" } }), // a run from before the rows and the answer were kept
    job({ job_id: "2b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11", state: "stopped", outputs: {} }),
    job({ job_id: "3b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11", state: "running" }),
    job({ job_id: "4b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11", outputs: { package: "c" } }), // done with nothing to show
  ]);
  assert.deepEqual(runs.map((r) => [r.job_id[0], r.keepsRows, r.answer?.factor ?? null]), [["0", true, 1.0334], ["1", false, null]]);
  assert.equal(runs[0].coupon, "IM7-UNT-L1");
  assert.equal(runs[0].finished_at, "2026-11-16T22:12:00+00:00");
});

test("an answer is shown only in the shape the package writes; anything else is no answer", () => {
  assert.deepEqual(readJobAnswer(ANSWER), ANSWER);
  assert.deepEqual(readJobAnswer({ ...ANSWER, face: "top" })?.face, "top");
  for (const bad of [null, undefined, "holds", { ...ANSWER, factor: "1.03" }, { ...ANSWER, factor: Number.POSITIVE_INFINITY }, { ...ANSWER, fails: "no" },
    { ...ANSWER, basis: "grip" }, { ...ANSWER, ply: 4.5 }, { basis: "gauge" }]) {
    assert.equal(readJobAnswer(bad), null, JSON.stringify(bad));
  }
});

test("the answer's words are the package's values, picked and printed: nothing is worked out on the page", () => {
  assert.deepEqual(answerWords(readJobAnswer(ANSWER), printed), { verdict: "Holds", loading: "1.033 × the applied load", facts: ["ply 4 (90°)", "Tsai-Hill", "gauge section"] });
  assert.deepEqual(answerWords(readJobAnswer({ ...ANSWER, fails: true, factor: 0.9274, basis: "whole", criterion: "max_stress", face: "top", ply: 1, angle: -45 }), printed),
    { verdict: "Fails", loading: "0.9274 × the applied load", facts: ["ply 1 (-45°), top face", "Maximum stress", "whole model"] });
  assert.equal(answerWords(null, printed), null);
});

test("a run's time is the reader's own date and time, and nothing for a stamp that is not one", () => {
  assert.match(runWhen("2026-11-16T22:12:00+00:00", "en-US"), /Nov 1[67], 2026/);
  assert.equal(runWhen("soon"), "");
});

test("the run to open passes from the list to the workspace once, as a job's id and nothing else", () => {
  const kept = new Map<string, string>();
  const storage = { setItem: (k: string, v: string) => { kept.set(k, v); }, getItem: (k: string) => kept.get(k) ?? null, removeItem: (k: string) => { kept.delete(k); } };
  assert.equal(askToOpen(storage, "0b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11"), true);
  assert.equal(kept.get(OPEN_RUN_KEY), "0b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11");
  assert.equal(takeRunToOpen(storage), "0b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11");
  assert.equal(takeRunToOpen(storage), null); // taken once
  assert.equal(askToOpen(storage, "../../v1/runs"), false); // not an id: nothing is kept
  kept.set(OPEN_RUN_KEY, "<script>");
  assert.equal(takeRunToOpen(storage), null);
  assert.equal(kept.has(OPEN_RUN_KEY), false);
  assert.equal(askToOpen(null, "0b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11"), false); // storage blocked: the list falls back to the viewer's page
  assert.equal(takeRunToOpen(null), null);
  const refusing = { setItem: () => { throw new Error("blocked"); } };
  assert.equal(askToOpen(refusing, "0b6f6f0e-9d0a-4f43-8a52-3f6a6f2c1d11"), false);
});
