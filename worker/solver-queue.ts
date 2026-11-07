/** The queue's consumer, without the Cloudflare runtime (ADR-0056 amendment 3), so `tests/worker-solver-queue.test.ts` runs it in
 * Node. One message is one coupon job's id. The consumer starts the job in a solver container of the job's own and stays with it,
 * asking for its state every few seconds, until it ends: that keeps the container awake, bounds the jobs running at once by the
 * consumer's `max_concurrency`, and gives the per-job timeout a place to act. Nothing here computes a result (ADR-0001). */

export const JOB_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export const POLL_MS = 5_000;  // how often the consumer asks a solver for its job's state
export const JOB_TIMEOUT_MS = 12 * 60_000;  // the per-job limit, inside the 15 minutes a consumer invocation may last
export const STOP_GRACE_MS = 60_000;  // after a stop, how long the consumer waits for the job to say it ended
export const BUSY_RETRY_S = 30;  // a job whose coupon another job holds is delivered again this much later
export const ERROR_RETRY_S = 15;  // a solver that could not be started is tried again this much later
export const LOST_AFTER_ERRORS = 3;  // this many failed polls in a row and the consumer lets the job go; the API sweeps its row

const ENDED = new Set(["done", "stopped", "refused"]);

export type SolverAnswer = { status: number; body: unknown };
/** One request to the job's solver container: a method and a path of its API. Throws when the container cannot be reached. */
export type SolverCall = (method: "GET" | "POST", path: string) => Promise<SolverAnswer>;
export type Verdict = { kind: "ack"; reason: string } | { kind: "retry"; delaySeconds: number; reason: string };

export type Clock = { now: () => number; sleep: (ms: number) => Promise<void> };

function stateOf(answer: SolverAnswer): string | null {
  const state: unknown = typeof answer.body === "object" && answer.body !== null ? Reflect.get(answer.body, "state") : null;
  return typeof state === "string" ? state : null;
}

/** The message's job id, or null when the message is not one (it is then let go). */
export function jobIdOf(body: unknown): string | null {
  const id: unknown = typeof body === "object" && body !== null ? Reflect.get(body, "job_id") : null;
  return typeof id === "string" && JOB_ID.test(id) ? id : null;
}

/** Drive one job to its end in its solver container; say whether the message is done with (`ack`) or comes back later (`retry`). */
export async function driveJob(body: unknown, call: SolverCall, clock: Clock, timeoutMs = JOB_TIMEOUT_MS): Promise<Verdict> {
  const id = jobIdOf(body);
  if (id === null) return { kind: "ack", reason: "the message names no coupon job" };
  const path = `/v1/solver/jobs/${id}`;
  let answer: SolverAnswer;
  try {
    answer = await call("POST", path);
  } catch (error) {
    return { kind: "retry", delaySeconds: ERROR_RETRY_S, reason: `the solver could not be started: ${String(error)}` };
  }
  if (answer.status === 409) return { kind: "ack", reason: "the job is not queued: another solver took it, or it ended" };
  if (answer.status !== 200 && answer.status !== 202) {
    return { kind: "retry", delaySeconds: ERROR_RETRY_S, reason: `the solver answered ${answer.status} to the start` };
  }
  const started = clock.now();
  let stopped: number | null = null;
  let errors = 0;
  for (;;) {
    const state = stateOf(answer);
    if (state !== null && ENDED.has(state)) return { kind: "ack", reason: `the job ended ${state}` };
    if (state === "queued") return { kind: "retry", delaySeconds: BUSY_RETRY_S, reason: "another job holds the coupon; the job is queued again" };
    if (stopped !== null && clock.now() - stopped > STOP_GRACE_MS) return { kind: "ack", reason: "stopped at the per-job limit; it did not say it ended" };
    if (stopped === null && clock.now() - started > timeoutMs) {
      stopped = clock.now();
      const reason = `the job ran longer than ${Math.round(timeoutMs / 60_000)} minutes, the per-job limit, so it was stopped`;
      try {
        await call("POST", `${path}/stop?reason=${encodeURIComponent(reason)}`);
      } catch {
        return { kind: "ack", reason: "the per-job limit was reached and the solver did not answer; the API stops the job's row" };
      }
    }
    await clock.sleep(POLL_MS);
    try {
      answer = await call("GET", path);
      errors = 0;
    } catch (error) {
      errors += 1;
      if (errors >= LOST_AFTER_ERRORS) return { kind: "ack", reason: `the solver stopped answering (${String(error)}); the API stops the job's row` };
      continue;
    }
    if (answer.status === 404) return { kind: "ack", reason: "the solver no longer has the job (its container restarted); the API stops the job's row" };
  }
}
