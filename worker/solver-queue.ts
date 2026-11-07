/** The job queue's two steps, without the Cloudflare runtime (ADR-0056 amendment 3, amendment 4), so
 * `tests/worker-solver-queue.test.ts` runs them in Node. One message is one coupon job's id.
 *
 * The queue's consumer only starts the job (`startJob`): it asks the job's own solver container to take the job up and returns
 * within seconds, so Queues, which decides whether to add consumers only after a batch ends, can hand the next message to a
 * consumer at once. The solver container's Durable Object then watches the job on a timer of its own (`watchJob`, every
 * POLL_MS): each look keeps the container awake, the per-job limit stops a job that runs too long, and a job whose coupon another
 * job holds is sent back to the queue. Nothing here computes a result (ADR-0001). */

export const JOB_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export const POLL_MS = 5_000;  // how often the solver's timer asks its container for the job's state
export const JOB_TIMEOUT_MS = 12 * 60_000;  // the per-job limit
export const STOP_GRACE_MS = 60_000;  // after a stop, how long the timer waits for the job to say it ended
export const BUSY_RETRY_S = 30;  // a job whose coupon another job holds is delivered again this much later
export const ERROR_RETRY_S = 15;  // a solver that could not be started is tried again this much later, and this much more each time
export const RETRY_CAP_S = 45;  // ... up to this: with the consumer's 100 retries a waiting job outlasts the API's one-hour sweep
export const LOST_AFTER_ERRORS = 3;  // this many failed looks in a row and the timer lets the job go; the API sweeps its row

const ENDED = new Set(["done", "stopped", "refused"]);

export type SolverAnswer = { status: number; body: unknown };
/** One request to the job's solver container: a method and a path of its API. Throws when the container cannot be reached. */
export type SolverCall = (method: "GET" | "POST", path: string) => Promise<SolverAnswer>;

/** What the consumer does with the message: `ack` (with `watch` when the solver's timer is to watch the job) or `retry`. */
export type StartVerdict = { kind: "ack"; watch: boolean; reason: string } | { kind: "retry"; delaySeconds: number; reason: string };

/** The timer's state between two looks, kept by the solver's Durable Object (JSON). */
export type Watch = { jobId: string; startedAt: number; stoppedAt: number | null; errors: number };

/** What the timer does next: look `again` after POLL_MS, `requeue` the job (send its id to the queue again), or `end`. */
export type WatchStep =
  | { kind: "again"; watch: Watch; reason: string }
  | { kind: "requeue"; delaySeconds: number; reason: string }
  | { kind: "end"; reason: string };

function stateOf(answer: SolverAnswer): string | null {
  const state: unknown = typeof answer.body === "object" && answer.body !== null ? Reflect.get(answer.body, "state") : null;
  return typeof state === "string" ? state : null;
}

const jobPath = (id: string) => `/v1/solver/jobs/${id}`;

/** The message's job id, or null when the message is not one (it is then let go). */
export function jobIdOf(body: unknown): string | null {
  const id: unknown = typeof body === "object" && body !== null ? Reflect.get(body, "job_id") : null;
  return typeof id === "string" && JOB_ID.test(id) ? id : null;
}

/** How long a message waits before its next delivery after its `attempts`-th failed start: ERROR_RETRY_S, then ERROR_RETRY_S more
 * each time, at most RETRY_CAP_S. A job waiting for a free solver (the container's proxy answers 503 past `max_instances`) uses a
 * retry each time, so the waits add up to more than the hour after which the API sweeps a queued job: the API, not the
 * dead-letter queue, decides that a job waited too long. */
export function retryDelay(attempts: number): number {
  return Math.min(ERROR_RETRY_S * Math.max(1, Math.floor(attempts)), RETRY_CAP_S);
}

/** The consumer's step, at the message's `attempts`-th delivery: ask the job's solver to take it up. 202 (taken here) or 200 (this
 * solver has it already) is acked with a watch unless the job has ended; 409 (not queued: another solver took it, it ended, or
 * there is none) is acked without one; any other answer, or no answer, brings the message back after `retryDelay(attempts)`. */
export async function startJob(body: unknown, call: SolverCall, attempts = 1): Promise<StartVerdict> {
  const id = jobIdOf(body);
  if (id === null) return { kind: "ack", watch: false, reason: "the message names no coupon job" };
  let answer: SolverAnswer;
  try {
    answer = await call("POST", jobPath(id));
  } catch (error) {
    return { kind: "retry", delaySeconds: retryDelay(attempts), reason: `the solver could not be started: ${String(error)}` };
  }
  if (answer.status === 409) return { kind: "ack", watch: false, reason: "the job is not queued: another solver took it, or it ended" };
  if (answer.status !== 200 && answer.status !== 202) {
    return { kind: "retry", delaySeconds: retryDelay(attempts), reason: `the solver answered ${answer.status} to the start` };
  }
  const state = stateOf(answer);
  if (state !== null && ENDED.has(state)) return { kind: "ack", watch: false, reason: `the job had ended ${state}` };
  return { kind: "ack", watch: true, reason: answer.status === 202 ? "the job started" : "the solver has the job already" };
}

/** The first watch of a job the consumer started at `now`. */
export function firstWatch(jobId: string, now: number): Watch {
  return { jobId, startedAt: now, stoppedAt: null, errors: 0 };
}

/** A look that got no answer, or an error in place of the job (the container's proxy answers 5xx when the container is not
 * reachable): counted, and after LOST_AFTER_ERRORS in a row the timer lets the job go. */
function failedLook(watch: Watch, why: string): WatchStep {
  const errors = watch.errors + 1;
  if (errors >= LOST_AFTER_ERRORS) return { kind: "end", reason: `the solver stopped answering (${why}); the API stops the job's row` };
  return { kind: "again", watch: { ...watch, errors }, reason: `the solver did not answer (${why})` };
}

/** The first line of an answer's body, short enough for a log line. */
function gist(body: unknown): string {
  const text = typeof body === "string" ? body : JSON.stringify(body);
  return (text ?? "").split("\n")[0].slice(0, 160);
}

/** The timer's step: one look at the job. Ended, or gone from the solver (404): `end`. Queued again, because another job holds its
 * coupon: `requeue`. Past the per-job limit: stop it once and look `again` until it says it ended or STOP_GRACE_MS has passed. A
 * failed look (no answer, or a 5xx without the job) counts toward LOST_AFTER_ERRORS; a look that gets the job resets the count. */
export async function watchJob(watch: Watch, call: SolverCall, now: number, timeoutMs = JOB_TIMEOUT_MS): Promise<WatchStep> {
  const path = jobPath(watch.jobId);
  let answer: SolverAnswer;
  try {
    answer = await call("GET", path);
  } catch (error) {
    return failedLook(watch, String(error));
  }
  if (answer.status === 404) return { kind: "end", reason: "the solver no longer has the job (its container restarted); the API stops the job's row" };
  const state = stateOf(answer);
  if (state === null && answer.status >= 500) return failedLook(watch, `${answer.status}: ${gist(answer.body)}`);
  if (state !== null && ENDED.has(state)) return { kind: "end", reason: `the job ended ${state}` };
  if (state === "queued") return { kind: "requeue", delaySeconds: BUSY_RETRY_S, reason: "another job holds the coupon; the job is queued again" };
  const looked = { ...watch, errors: 0 };
  if (watch.stoppedAt !== null) {
    if (now - watch.stoppedAt > STOP_GRACE_MS) return { kind: "end", reason: "stopped at the per-job limit; it did not say it ended" };
    return { kind: "again", watch: looked, reason: "stopped at the per-job limit; waiting for it to end" };
  }
  if (now - watch.startedAt > timeoutMs) {
    const reason = `the job ran longer than ${Math.round(timeoutMs / 60_000)} minutes, the per-job limit, so it was stopped`;
    try {
      await call("POST", `${path}/stop?reason=${encodeURIComponent(reason)}`);
    } catch {
      return { kind: "end", reason: "the per-job limit was reached and the solver did not answer; the API stops the job's row" };
    }
    return { kind: "again", watch: { ...looked, stoppedAt: now }, reason };
  }
  return { kind: "again", watch: looked, reason: state === null ? `the solver answered ${answer.status} without a state` : `the job is ${state}` };
}
