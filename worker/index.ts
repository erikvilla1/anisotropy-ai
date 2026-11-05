/** The hosted tier's Worker (ADR-0056): the website's static export comes from the assets binding, and every request under /api/
 * goes to the one solver container, a Durable Object that runs the image built from the Dockerfile. Nothing here computes a
 * result (ADR-0001).
 *
 * Who may come in: with the sign-in settings set (ADR-0058, worker/sign-in.ts), our own sign-in guards every request and the API
 * gets the signed-in email as a token it checks. Without them, the Worker is as it was, behind Cloudflare Access, whose
 * `Cf-Access-Jwt-Assertion` header goes to the API untouched (api/src/anisotropy_api/access.py). */

import { Container, getContainer } from "@cloudflare/containers";
import { DurableObject } from "cloudflare:workers";

import { forwardToApi, signInGate } from "./gate";
import { apiPath, containerEnvironment, type ContainerVariable } from "./routing";
import { checkCode, deriveKey, issueCode, signInConfig, type CodeRecord, type CodeStore, type SIGN_IN_VARIABLES } from "./sign-in";

type WorkerEnv = Env & Partial<Record<ContainerVariable | (typeof SIGN_IN_VARIABLES)[number], string>>;

export class ApiContainer extends Container<WorkerEnv> {
  defaultPort = 8080;  // uvicorn in the image; a request waits until the API listens
  sleepAfter = "20m";  // idle this long, the container stops; the next request starts it again (a cold start, seconds)
  enableInternet = true;  // the database, the object store and, when switched on, the assistant's provider

  constructor(ctx: DurableObject["ctx"], env: WorkerEnv) {
    super(ctx, env);
    this.envVars = containerEnvironment(env);
  }
}

/** The sign-in codes (ADR-0058): one instance for the whole site, so a code and its attempt count are read and written in one
 * place, in order. Each email has at most one live code; worker/sign-in.ts holds the rules. */
export class SignInCodes extends DurableObject<WorkerEnv> {
  private store(): CodeStore {
    const storage = this.ctx.storage;
    return {
      get: (key) => storage.get<CodeRecord>(key),
      put: (key, value) => storage.put(key, value),
      delete: (key) => storage.delete(key),
    };
  }

  async issue(email: string) {
    return issueCode(this.store(), email, Date.now());
  }

  async check(email: string, code: string) {
    return checkCode(this.store(), email, code, Date.now());
  }
}

function unavailable(reason: string): Response {
  console.error(`sign-in settings: ${reason}`);
  return new Response("The site's sign-in is not configured correctly; its operator has been told.", {
    status: 503, headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
  });
}

export default {
  async fetch(request: Request, env: WorkerEnv): Promise<Response> {
    const api = (forwarded: Request) => getContainer(env.API, "api").fetch(forwarded);
    let config;
    try {
      config = signInConfig(env);
    } catch (error) {
      return unavailable(error instanceof Error ? error.message : String(error));  // half-set: closed, never open
    }
    if (config === null) {  // behind Cloudflare Access, as before
      const path = apiPath(new URL(request.url).pathname);
      return path === null ? env.ASSETS.fetch(request) : api(forwardToApi(request, path, null));
    }
    const codes = env.SIGN_IN.get(env.SIGN_IN.idFromName("codes"));
    return signInGate(request, {
      config,
      sessionKey: await deriveKey(config.secret, "session"),
      identityKey: await deriveKey(config.secret, "identity"),
      now: () => Date.now(),
      assets: (forwarded) => env.ASSETS.fetch(forwarded),
      api,
      codes: { issue: (email) => codes.issue(email), check: (email, code) => codes.check(email, code) },
      send: (email) => fetch(email),
    });
  },
} satisfies ExportedHandler<WorkerEnv>;
