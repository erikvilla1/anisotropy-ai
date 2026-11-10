// The job queue's two steps (ADR-0056 amendments 3 and 4): the consumer starts a job in its own solver container and returns, then
// the solver's timer watches it to its end. A fake solver and a fake clock stand in for the container and the time.
import assert from "node:assert/strict";
import { test } from "node:test";

import {
  BUSY_RETRY_S, ERROR_RETRY_S, JOB_TIMEOUT_MS, LOST_AFTER_ERRORS, POLL_MS, RETRY_CAP_S, SOLVER_POOL, STOP_GRACE_MS, firstWatch, jobIdOf,
  retryDelay, solverNames, startInPool, startJob, watchJob, type SolverAnswer, type SolverCall, type StartVerdict, type WatchStep,
} from "../worker/solver-queue";

const ID = "0f8fad5b-d9cb-469f-a165-70867728950e";
const PATH = `/v1/solver/jobs/${ID}`;

/** A solver that answers the start with `start` and then each look with the next of `looks`, `running` once they run out; a stop is
 * answered `running`. It records every call. */
function solver(start: SolverAnswer | Error, looks: (SolverAnswer | Error)[] = []) {
  const calls: string[] = [];
  const call: SolverCall = async (method, path) => {
    calls.push(`${method} ${path}`);
    const next = path.includes("/stop") ? running : method === "POST" ? start : looks.shift() ?? running;
    if (next instanceof Error) throw next;
    return next;
  };
  return { call, calls };
}

const running = { status: 200, body: { state: "running" } };
const taken = { status: 202, body: { state: "running" } };
const ended = (state: string) => ({ status: 200, body: { state } });

/** The solver's timer, as the Durable Object runs it: a look every POLL_MS from the start until a step is not `again`. Returns the
 * last step and how many looks it took. */
async function timer(call: SolverCall, timeoutMs = JOB_TIMEOUT_MS): Promise<{ step: WatchStep; looks: number }> {
  let now = 0;
  let watch = firstWatch(ID, now);
  for (let looks = 1; ; looks += 1) {
    now += POLL_MS;
    const step = await watchJob(watch, call, now, timeoutMs);
    if (step.kind !== "again") return { step, looks };
    watch = step.watch;
  }
}

test("a message that is not a job id is let go without a call", async () => {
  const { call, calls } = solver(taken);
  for (const body of [null, "x", { job_id: "not-a-uuid" }, { job_id: ID.toUpperCase() }]) {
    assert.deepEqual(await startJob(body, call), { kind: "ack", watch: false, reason: "the message names no coupon job" });
  }
  assert.deepEqual(calls, []);
  assert.equal(jobIdOf({ job_id: ID }), ID);
});

test("the consumer starts the job with one call and returns; the timer watches it until it ends", async () => {
  const { call, calls } = solver(taken, [running, running, ended("done")]);
  assert.deepEqual(await startJob({ job_id: ID }, call), { kind: "ack", watch: true, reason: "the job started" });
  assert.deepEqual(calls, [`POST ${PATH}`]);
  const { step, looks } = await timer(call);
  assert.deepEqual(step, { kind: "end", reason: "the job ended done" });
  assert.equal(looks, 3);
  assert.deepEqual(calls.slice(1), Array(3).fill(`GET ${PATH}`));
});

test("a message delivered twice finds the job here already: acked, watched, not run twice", async () => {
  assert.deepEqual(await startJob({ job_id: ID }, solver(running).call), { kind: "ack", watch: true, reason: "the solver has the job already" });
  assert.deepEqual(await startJob({ job_id: ID }, solver(ended("done")).call), { kind: "ack", watch: false, reason: "the job had ended done" });
});

test("a job another solver took, or that ended, is let go; one that could not start comes back", async () => {
  assert.deepEqual(await startJob({ job_id: ID }, solver({ status: 409, body: {} }).call),
                   { kind: "ack", watch: false, reason: "the job is not queued: another solver took it, or it ended" });
  assert.deepEqual(await startJob({ job_id: ID }, solver({ status: 503, body: {} }).call),
                   { kind: "retry", delaySeconds: ERROR_RETRY_S, reason: "the solver answered 503 to the start" });
  const unreachable = await startJob({ job_id: ID }, solver(new Error("no container")).call);
  assert.equal(unreachable.kind, "retry");
  assert.equal(unreachable.kind === "retry" && unreachable.delaySeconds, ERROR_RETRY_S);
});

test("a job waiting for a free solver comes back a little later each time, and outlasts the API's one-hour sweep", async () => {
  assert.deepEqual([1, 2, 3, 4, 100].map(retryDelay), [ERROR_RETRY_S, 2 * ERROR_RETRY_S, RETRY_CAP_S, RETRY_CAP_S, RETRY_CAP_S]);
  assert.equal(retryDelay(0), ERROR_RETRY_S);
  // the consumer's max_retries in wrangler.jsonc is 100: the waits before the dead-letter queue add up to more than an hour
  const waited = Array.from({ length: 100 }, (_, n) => retryDelay(n + 1)).reduce((a, b) => a + b, 0);
  assert.ok(waited > 3600, `${waited} s`);
  const full = await startJob({ job_id: ID }, solver({ status: 503, body: "no container instance is available" }).call, 7);
  assert.deepEqual(full, { kind: "retry", delaySeconds: RETRY_CAP_S, reason: "the solver answered 503 to the start" });
});

test("a job whose coupon another job holds is sent back to the queue after a while", async () => {
  const { step } = await timer(solver(taken, [running, ended("queued")]).call);
  assert.deepEqual(step, { kind: "requeue", delaySeconds: BUSY_RETRY_S, reason: "another job holds the coupon; the job is queued again" });
});

test("the per-job limit stops the job once and waits for it to say so", async () => {
  const before = Math.floor(JOB_TIMEOUT_MS / POLL_MS);  // the looks before the limit passes
  const { call, calls } = solver(taken, [...Array(before + 2).fill(running), ended("stopped")]);
  const { step } = await timer(call);
  assert.deepEqual(step, { kind: "end", reason: "the job ended stopped" });
  const stops = calls.filter((c) => c.includes("/stop"));
  assert.equal(stops.length, 1);
  assert.match(decodeURIComponent(stops[0]), /longer than 12 minutes, the per-job limit/);
});

test("a stopped job that never says it ended is let go after the grace period", async () => {
  const { call, calls } = solver(taken);  // `running` for ever
  const { step, looks } = await timer(call);
  assert.deepEqual(step, { kind: "end", reason: "stopped at the per-job limit; it did not say it ended" });
  assert.equal(calls.filter((c) => c.includes("/stop")).length, 1);
  assert.ok(looks * POLL_MS > JOB_TIMEOUT_MS + STOP_GRACE_MS);
  assert.ok(looks * POLL_MS <= JOB_TIMEOUT_MS + STOP_GRACE_MS + 3 * POLL_MS);
});

test("a solver that stops answering, or forgot the job, is let go for the API's sweep", async () => {
  const silent = await timer(solver(taken, Array(LOST_AFTER_ERRORS).fill(new Error("reset"))).call);
  assert.equal(silent.step.kind, "end");
  assert.match(silent.step.reason, /stopped answering/);
  assert.equal(silent.looks, LOST_AFTER_ERRORS);
  // a failed look is not the end, and an answer between two failed looks starts the count again
  const flaky = await timer(solver(taken, [new Error("reset"), new Error("reset"), running, new Error("reset"), new Error("reset"), ended("done")]).call);
  assert.deepEqual(flaky.step, { kind: "end", reason: "the job ended done" });
  const forgot = await timer(solver(taken, [{ status: 404, body: {} }]).call);
  assert.match(forgot.step.reason, /no longer has the job/);
});

test("an error in place of the job (the container's proxy answering 5xx) is a failed look, not an answer", async () => {
  const proxy = { status: 500, body: "Container suddenly disconnected, try again" };
  const once = solver(taken, [proxy, ended("done")]);
  const first = await watchJob(firstWatch(ID, 0), once.call, POLL_MS);
  assert.deepEqual(first, { kind: "again", watch: { ...firstWatch(ID, 0), errors: 1 },
                            reason: "the solver did not answer (500: Container suddenly disconnected, try again)" });
  assert.deepEqual((await timer(solver(taken, [proxy, ended("done")]).call)).step, { kind: "end", reason: "the job ended done" });
  const gone = await timer(solver(taken, Array(LOST_AFTER_ERRORS).fill(proxy)).call);
  assert.equal(gone.step.kind, "end");
  assert.equal(gone.looks, LOST_AFTER_ERRORS);
  // a 4xx or 2xx without a state is an answer: the job is looked at again and the count starts afresh
  const odd = await watchJob({ ...firstWatch(ID, 0), errors: 2 }, solver(taken, [{ status: 200, body: "?" }]).call, POLL_MS);
  assert.deepEqual(odd, { kind: "again", watch: firstWatch(ID, 0), reason: "the solver answered 200 without a state" });
});

test("a busy solver answers 423 and the consumer asks the pool's next one; every solver busy brings the message back", async () => {
  const busy = { status: 423, body: { detail: "this solver runs coupon job x" } };
  assert.deepEqual(await startJob({ job_id: ID }, solver(busy).call), { kind: "busy", reason: "this solver runs another job" });
  assert.deepEqual(solverNames(3), ["solver-0", "solver-1", "solver-2"]);
  assert.equal(solverNames().length, SOLVER_POOL);
  const asked: string[] = [];
  const begin = async (name: string): Promise<StartVerdict> => {
    asked.push(name);
    return name === "solver-2" ? { kind: "ack", watch: true, reason: "the job started" } : { kind: "busy", reason: "this solver runs another job" };
  };
  const picked = await startInPool(begin, solverNames(4));
  assert.deepEqual(picked, { verdict: { kind: "ack", watch: true, reason: "the job started" }, solver: "solver-2" });
  assert.deepEqual(asked, ["solver-0", "solver-1", "solver-2"]);  // the fourth was not asked
  const allBusy = await startInPool(async () => ({ kind: "busy", reason: "this solver runs another job" }), solverNames(2), 3);
  assert.equal(allBusy.solver, null);
  assert.deepEqual(allBusy.verdict, { kind: "retry", delaySeconds: retryDelay(3), reason: "every solver of the pool (2) runs a job; the job waits in the queue" });
});
