// The queue's consumer (ADR-0056 amendment 3): one message is one job, driven to its end in its own solver container, with a fake
// solver and a fake clock standing in for the container and the time.
import assert from "node:assert/strict";
import { test } from "node:test";

import { BUSY_RETRY_S, ERROR_RETRY_S, JOB_TIMEOUT_MS, POLL_MS, driveJob, jobIdOf, type SolverAnswer, type SolverCall } from "../worker/solver-queue";

const ID = "0f8fad5b-d9cb-469f-a165-70867728950e";

/** A solver that answers the start with `start` and then each poll with the next of `polls`; it records every call. */
function solver(start: SolverAnswer | Error, polls: (SolverAnswer | Error)[]) {
  const calls: string[] = [];
  const call: SolverCall = async (method, path) => {
    calls.push(`${method} ${path}`);
    const next = method === "POST" && !path.includes("/stop") ? start : path.includes("/stop") ? { status: 200, body: { state: "running" } } : polls.shift();
    if (next === undefined) return { status: 200, body: { state: "running" } };
    if (next instanceof Error) throw next;
    return next;
  };
  return { call, calls };
}

function fakeClock() {
  let now = 0;
  return { now: () => now, sleep: async (ms: number) => { now += ms; } };
}

const running = { status: 200, body: { state: "running" } };

test("a message that is not a job id is let go without a call", async () => {
  const { call, calls } = solver(running, []);
  for (const body of [null, "x", { job_id: "not-a-uuid" }, { job_id: ID.toUpperCase() }]) {
    assert.equal((await driveJob(body, call, fakeClock())).kind, "ack");
  }
  assert.deepEqual(calls, []);
  assert.equal(jobIdOf({ job_id: ID }), ID);
});

test("the consumer starts the job and stays with it until it ends", async () => {
  const { call, calls } = solver({ status: 202, body: { state: "running" } }, [running, running, { status: 200, body: { state: "done" } }]);
  const verdict = await driveJob({ job_id: ID }, call, fakeClock());
  assert.deepEqual(verdict, { kind: "ack", reason: "the job ended done" });
  assert.deepEqual(calls, [`POST /v1/solver/jobs/${ID}`, ...Array(3).fill(`GET /v1/solver/jobs/${ID}`)]);
});

test("a job another solver took, or that ended, is let go; one that could not start comes back", async () => {
  assert.equal((await driveJob({ job_id: ID }, solver({ status: 409, body: {} }, []).call, fakeClock())).kind, "ack");
  assert.deepEqual(await driveJob({ job_id: ID }, solver({ status: 503, body: {} }, []).call, fakeClock()),
                   { kind: "retry", delaySeconds: ERROR_RETRY_S, reason: "the solver answered 503 to the start" });
  const unreachable = await driveJob({ job_id: ID }, solver(new Error("no container"), []).call, fakeClock());
  assert.equal(unreachable.kind, "retry");
});

test("a job whose coupon another job holds comes back after a while", async () => {
  const { call } = solver({ status: 202, body: { state: "running" } }, [running, { status: 200, body: { state: "queued" } }]);
  const verdict = await driveJob({ job_id: ID }, call, fakeClock());
  assert.equal(verdict.kind, "retry");
  assert.equal(verdict.kind === "retry" && verdict.delaySeconds, BUSY_RETRY_S);
});

test("the per-job limit stops the job and waits for it to say so", async () => {
  const polls = Array(Math.ceil(JOB_TIMEOUT_MS / POLL_MS) + 2).fill(running);
  polls.push({ status: 200, body: { state: "stopped" } });
  const { call, calls } = solver({ status: 202, body: { state: "running" } }, polls);
  const verdict = await driveJob({ job_id: ID }, call, fakeClock());
  assert.deepEqual(verdict, { kind: "ack", reason: "the job ended stopped" });
  const stops = calls.filter((c) => c.includes("/stop"));
  assert.equal(stops.length, 1);
  assert.match(decodeURIComponent(stops[0]), /longer than 12 minutes, the per-job limit/);
});

test("a solver that stops answering, or forgot the job, is let go for the API's sweep", async () => {
  const silent = solver({ status: 202, body: { state: "running" } }, [new Error("reset"), new Error("reset"), new Error("reset")]);
  assert.match((await driveJob({ job_id: ID }, silent.call, fakeClock())).reason, /stopped answering/);
  const flaky = solver({ status: 202, body: { state: "running" } }, [new Error("reset"), running, { status: 200, body: { state: "done" } }]);
  assert.equal((await driveJob({ job_id: ID }, flaky.call, fakeClock())).reason, "the job ended done");  // one failed poll is not the end
  const forgot = solver({ status: 202, body: { state: "running" } }, [{ status: 404, body: {} }]);
  assert.match((await driveJob({ job_id: ID }, forgot.call, fakeClock())).reason, /no longer has the job/);
});
