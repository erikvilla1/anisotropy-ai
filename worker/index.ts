/** The hosted tier's Worker (ADR-0056): the website's static export comes from the assets binding, and every request under /api/
 * goes to the API's container, a Durable Object that runs the image built from the Dockerfile. Cloudflare Access sits in front of
 * the Worker; the request reaches here with Access's `Cf-Access-Jwt-Assertion` header, which is forwarded untouched so the API can
 * check it (api/src/anisotropy_api/access.py).
 *
 * The job queue (ADR-0056 stage 3, amendment 3): with the `JOB_QUEUE` binding, the API's container files each coupon job and
 * answers with its id in a header; the Worker sends the id to the queue. The queue's consumer, this Worker's `queue` handler, runs
 * each job in a solver container of its own (`SolverContainer`, named by the job's id, from the same image) and stays with it until
 * it ends (worker/solver-queue.ts). Nothing here computes a result (ADR-0001). */

import { Container, getContainer } from "@cloudflare/containers";
import type { DurableObject } from "cloudflare:workers";

import { ENQUEUE_HEADER, apiEnvironment, apiPath, isSolverPath, solverEnvironment, type ContainerVariable } from "./routing";
import { driveJob, jobIdOf, type SolverCall } from "./solver-queue";

type WorkerEnv = Env & Partial<Record<ContainerVariable, string>>;

export class ApiContainer extends Container<WorkerEnv> {
  defaultPort = 8080;  // uvicorn in the image; a request waits until the API listens
  sleepAfter = "20m";  // idle this long, the container stops; the next request starts it again (a cold start, seconds)
  enableInternet = true;  // the database, the object store and, when switched on, the assistant's provider

  constructor(ctx: DurableObject["ctx"], env: WorkerEnv) {
    super(ctx, env);
    this.envVars = apiEnvironment(env);
  }
}

/** One coupon job's container: the same image as the API's, in the role `solver`. The consumer asks it for the job's state every
 * few seconds while the job runs, which keeps it awake; once the job has ended it sleeps after a few idle minutes. */
export class SolverContainer extends Container<WorkerEnv> {
  defaultPort = 8080;
  sleepAfter = "3m";
  enableInternet = true;  // the database and the object store

  constructor(ctx: DurableObject["ctx"], env: WorkerEnv) {
    super(ctx, env);
    this.envVars = solverEnvironment(env);
  }
}

function solverCall(env: WorkerEnv, jobId: string): SolverCall {
  const solver = getContainer(env.SOLVER, jobId);
  return async (method, path) => {
    const answer = await solver.fetch(new Request(`http://solver${path}`, { method }));
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

const clock = { now: () => Date.now(), sleep: (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)) };

export default {
  async fetch(request: Request, env: WorkerEnv): Promise<Response> {
    const url = new URL(request.url);
    const path = apiPath(url.pathname);
    if (path === null) return env.ASSETS.fetch(request);  // only /api/* runs the Worker first; this keeps the rest honest
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
      return Response.json({ detail: "the job was filed but could not be queued: the API named no job, or the Worker has no queue" }, { status: 503 });
    }
    try {
      await env.JOB_QUEUE.send({ job_id: jobId });
    } catch (error) {
      return Response.json({ detail: `the job ${jobId} was filed but could not be queued (${String(error)}); start it again` }, { status: 503 });
    }
    return new Response(answer.body, { status: answer.status, statusText: answer.statusText, headers });
  },

  async queue(batch: MessageBatch<unknown>, env: WorkerEnv): Promise<void> {
    for (const message of batch.messages) {  // one message a batch (max_batch_size 1 in wrangler.jsonc); a loop all the same
      const id = jobIdOf(message.body);
      const verdict = await driveJob(message.body, id === null ? async () => ({ status: 409, body: null }) : solverCall(env, id), clock);
      console.log(`coupon job ${id ?? "(none)"}: ${verdict.reason}`);
      if (verdict.kind === "retry") message.retry({ delaySeconds: verdict.delaySeconds });
      else message.ack();
    }
  },
} satisfies ExportedHandler<WorkerEnv>;
