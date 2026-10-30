/** The hosted tier's Worker (ADR-0056): the website's static export comes from the assets binding, and every request under /api/
 * goes to the one solver container, a Durable Object that runs the image built from the Dockerfile. Cloudflare Access sits in
 * front of the Worker; the request reaches here with Access's `Cf-Access-Jwt-Assertion` header, which is forwarded untouched so
 * the API can check it (api/src/anisotropy_api/access.py). Nothing here computes a result (ADR-0001). */

import { Container, getContainer } from "@cloudflare/containers";
import type { DurableObject } from "cloudflare:workers";

import { apiPath, containerEnvironment, type ContainerVariable } from "./routing";

type WorkerEnv = Env & Partial<Record<ContainerVariable, string>>;

export class ApiContainer extends Container<WorkerEnv> {
  defaultPort = 8080;  // uvicorn in the image; a request waits until the API listens
  sleepAfter = "20m";  // idle this long, the container stops; the next request starts it again (a cold start, seconds)
  enableInternet = true;  // the database, the object store and, when switched on, the assistant's provider

  constructor(ctx: DurableObject["ctx"], env: WorkerEnv) {
    super(ctx, env);
    this.envVars = containerEnvironment(env);
  }
}

export default {
  async fetch(request: Request, env: WorkerEnv): Promise<Response> {
    const url = new URL(request.url);
    const path = apiPath(url.pathname);
    if (path === null) return env.ASSETS.fetch(request);  // only /api/* runs the Worker first; this keeps the rest honest
    url.pathname = path;
    const forwarded = new Request(url.toString(), request);
    return getContainer(env.API, "api").fetch(forwarded);
  },
} satisfies ExportedHandler<WorkerEnv>;
