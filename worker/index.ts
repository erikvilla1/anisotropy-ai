/** The hosted tier's Worker (ADR-0056): the website's static export comes from the assets binding, and every request under /api/
 * goes to the API's container, a Durable Object that runs the image built from the Dockerfile. Cloudflare Access sits in front of
 * the Worker; the request reaches here with Access's `Cf-Access-Jwt-Assertion` header, which is forwarded untouched so the API can
 * check it (api/src/anisotropy_api/access.py).
 *
 * The job queue (ADR-0056 stage 3, amendments 3, 4 and 6): with the `JOB_QUEUE` binding, the API's container files each coupon job and
 * answers with its id in a header; the Worker sends the id to the queue. The queue's consumer, this Worker's `queue` handler, asks the
 * warm pool's solvers (`SolverContainer`, `solver-0` to `solver-9`, from the same image) in turn until one takes the job, and returns;
 * that solver's Durable Object watches the job on a timer until it ends (worker/solver-queue.ts). A solver that runs a job answers
 * busy; a finished job's container stays warm for a while with its coupons on disk, so the next job starts without a cold start.
 * Nothing here computes a result (ADR-0001). */

import { Container, getContainer } from "@cloudflare/containers";
import type { DurableObject } from "cloudflare:workers";

import { ENQUEUE_HEADER, apiEnvironment, apiPath, isSolverPath, leftOver, movedLocation, releaseOf, solverEnvironment, type ContainerVariable } from "./routing";
import { POLL_MS, firstWatch, jobIdOf, retryDelay, solverNames, startInPool, startJob, watchJob, type SolverCall, type StartVerdict,
         type Watch, type WatchStep } from "./solver-queue";

type WorkerEnv = Env & Partial<Record<ContainerVariable, string>>;
/** What a job the API filed but the Worker could not queue answers: what happened and what to do, never the cause. */
const NOT_QUEUED = "The analysis could not be queued. Start it again; if it keeps failing, contact us.";

/** Where the API's container keeps the word for what it was started with (`releaseOf`). */
const STARTED_WITH = "anisotropy:started-with";
/** How long a container told to stop is waited for before it is ended outright. */
const STOP_WAIT_MS = 10_000;

/** The API's container. A deploy replaces this object, with the new code and the new variables, and leaves the container it manages
 * running on the image and the variables it started with until it has been idle for `sleepAfter`; on 2026-11-17 the API answered
 * with the code and the secrets of before a deploy for half an hour after it. So the first request this object sees asks whether the
 * running container was started with what it would be started with now, and if not stops it; the request then starts it again, on
 * the deployed image with the deployed variables (ADR-0056 amendment 10). */
export class ApiContainer extends Container<WorkerEnv> {
  defaultPort = 8080;  // uvicorn in the image; a request waits until the API listens
  sleepAfter = "20m";  // idle this long, the container stops; the next request starts it again (a cold start, seconds)
  enableInternet = true;  // the database, the object store and, when switched on, the assistant's provider
  private current: Promise<void> | null = null;  // the one look this object takes at what its container was started with

  constructor(ctx: DurableObject["ctx"], env: WorkerEnv) {
    super(ctx, env);
    this.envVars = apiEnvironment(env);
  }

  /** A container that has started leaves the word for what it was started with. */
  override async onStart(): Promise<void> {
    await this.ctx.storage.put(STARTED_WITH, await releaseOf(this.envVars ?? {}));
  }

  override async fetch(request: Request): Promise<Response> {
    this.current ??= this.stopIfLeftOver();
    await this.current;
    return super.fetch(request);
  }

  /** Stops a container left over from before a deploy: it is told to stop, waited for, and ended outright if it has not stopped.
   * Whatever goes wrong here is logged and the request goes on to the container as it is, as it did before this was written. */
  private async stopIfLeftOver(): Promise<void> {
    try {
      const container = this.ctx.container;
      if (container === undefined) return;
      const release = await releaseOf(this.envVars ?? {});
      const startedWith = (await this.ctx.storage.get<string>(STARTED_WITH)) ?? null;
      if (!leftOver(container.running, startedWith, release)) return;
      console.log("the API's container was started before this deploy: stopping it, to start it on what is deployed");
      await this.stop();
      for (const until = Date.now() + STOP_WAIT_MS; container.running && Date.now() < until;) await new Promise((done) => setTimeout(done, 200));
      if (container.running) await this.destroy();
    } catch (error) {
      console.log(`the API's container could not be checked against this deploy: ${String(error)}`);
    }
  }
}

/** The solver's timer runs this method (the Container class's `schedule`, kept in the Durable Object's storage). */
const WATCH = "watch";

/** One of the pool's solver containers: the same image as the API's, in the role `solver`, running one coupon job at a time. The
 * consumer starts a job here (`begin`) and returns; this object's timer then asks the container for the job's state every POLL_MS
 * until it ends (`watch`), which keeps the container awake, applies the per-job limit and sends a job whose coupon is busy back to
 * the queue. After a job the container stays warm for sleepAfter, its coupons on disk, for the next job (ADR-0056 amendment 6). */
export class SolverContainer extends Container<WorkerEnv> {
  defaultPort = 8080;
  sleepAfter = "15m";
  enableInternet = true;  // the database and the object store

  constructor(ctx: DurableObject["ctx"], env: WorkerEnv) {
    super(ctx, env);
    this.envVars = solverEnvironment(env);
  }

  private call(): SolverCall {
    return async (method, path) => {
      const answer = await this.containerFetch(`http://solver${path}`, { method });
      const text = await answer.text();
      let body: unknown = null;
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
      return { status: answer.status, body };
    };
  }

  /** The consumer's call, at the message's `attempts`-th delivery: take the job up in this container and, when it runs, set the
   * timer that watches it, unless one is set already (a message delivered twice). Returns what the consumer does with the message. */
  async begin(jobId: string, attempts = 1): Promise<StartVerdict> {
    const verdict = await startJob({ job_id: jobId }, this.call(), attempts);
    if (verdict.kind === "ack" && verdict.watch && (await this.listSchedules(WATCH)).length === 0) {
      await this.schedule<Watch>(POLL_MS / 1000, WATCH, firstWatch(jobId, Date.now()));
    }
    return verdict;
  }

  /** The timer: one look at the job, then the next look, the job sent back to the queue, or the end. A look that throws is
   * counted as a failed one, so the timer never stops by accident while the job runs. */
  async watch(watch: Watch): Promise<void> {
    let step: WatchStep;
    try {
      step = await watchJob(watch, this.call(), Date.now());
    } catch (error) {
      step = { kind: "again", watch: { ...watch, errors: watch.errors + 1 }, reason: `the look failed: ${String(error)}` };
    }
    if (step.kind === "requeue") {
      try {
        await this.env.JOB_QUEUE.send({ job_id: watch.jobId }, { delaySeconds: step.delaySeconds });
      } catch (error) {  // the job stays queued in its row; look again, and send it then
        step = { kind: "again", watch, reason: `the job could not be queued again (${String(error)})` };
      }
    }
    console.log(`coupon job ${watch.jobId}: ${step.reason}`);
    if (step.kind === "again") await this.schedule<Watch>(POLL_MS / 1000, WATCH, step.watch);
  }
}

export default {
  async fetch(request: Request, env: WorkerEnv): Promise<Response> {
    const moved = movedLocation(request.url);
    if (moved !== null) return Response.redirect(moved, 301);  // /chat, /studio and their viewers moved (ADR-0058 amendment 2)
    const url = new URL(request.url);
    const path = apiPath(url.pathname);
    if (path === null) return env.ASSETS.fetch(request);  // only /api/* and the moved pages run the Worker first; this keeps the rest honest
    if (isSolverPath(path)) return Response.json({ detail: "Not Found" }, { status: 404 });  // the solvers' routes are the consumer's alone
    url.pathname = path;
    const forwarded = new Request(url.toString(), request);
    const answer = await getContainer(env.API, "api").fetch(forwarded);
    const queued = answer.headers.get(ENQUEUE_HEADER);
    if (queued === null) return answer;
    const headers = new Headers(answer.headers);
    headers.delete(ENQUEUE_HEADER);
    const jobId = jobIdOf({ job_id: queued });
    if (jobId === null || env.JOB_QUEUE == null) {
      // the cause stays in the log; the answer says what happened and what to do (ADR-0091 amendment 2)
      console.log(`coupon job ${queued}: filed but not queued: ${jobId === null ? "the API named no job" : "the Worker has no queue"}`);
      return Response.json({ detail: NOT_QUEUED }, { status: 503 });
    }
    try {
      await env.JOB_QUEUE.send({ job_id: jobId });
    } catch (error) {
      console.log(`coupon job ${jobId}: filed but not queued: ${String(error)}`);
      return Response.json({ detail: NOT_QUEUED }, { status: 503 });
    }
    return new Response(answer.body, { status: answer.status, statusText: answer.statusText, headers });
  },

  async queue(batch: MessageBatch<unknown>, env: WorkerEnv): Promise<void> {
    for (const message of batch.messages) {  // one message a batch (max_batch_size 1 in wrangler.jsonc); a loop all the same
      const id = jobIdOf(message.body);
      let verdict: StartVerdict;
      let solver: string | null = null;
      if (id === null) {
        verdict = { kind: "ack", watch: false, reason: "the message names no coupon job" };
      } else {
        const begin = async (name: string): Promise<StartVerdict> => {
          try {
            return await getContainer(env.SOLVER, name).begin(id, message.attempts);
          } catch (error) {
            return { kind: "retry", delaySeconds: retryDelay(message.attempts), reason: `the solver's object ${name} could not be reached: ${String(error)}` };
          }
        };
        ({ verdict, solver } = await startInPool(begin, solverNames(), message.attempts));
      }
      console.log(`coupon job ${id ?? "(none)"}${solver ? ` on ${solver}` : ""}: ${verdict.reason}`);
      if (verdict.kind === "retry") message.retry({ delaySeconds: verdict.delaySeconds });
      else message.ack();
    }
  },
} satisfies ExportedHandler<WorkerEnv>;
