/** The Worker's front door with our own sign-in on (ADR-0058): the sign-in pages, and a session check in front of every other
 * request, the site's files and the API alike. Pure apart from what `GateDeps` hands it, so `tests/worker-gate.test.ts` runs the
 * whole flow in Node with stand-ins for the files, the API, the code store and the email service. */

import { apiPath } from "./routing";
import {
  IDENTITY_HEADER, SESSION_COOKIE, clearedCookie, codeEmailRequest, identityToken, isInvited, normalizeEmail, readCookie,
  readSession, safeNext, sessionCookie, signSession, type Issued, type SignInConfig,
} from "./sign-in";
import { signInPage, type SignInView } from "./sign-in-page";

export interface GateDeps {
  config: SignInConfig;
  sessionKey: CryptoKey;
  identityKey: CryptoKey;
  now(): number;
  assets(request: Request): Promise<Response>;
  api(request: Request): Promise<Response>;
  codes: { issue(email: string): Promise<Issued>; check(email: string, code: string): Promise<boolean> };
  send(request: Request): Promise<Response>;
}

const PAGE_HEADERS = {
  "content-type": "text/html; charset=utf-8",
  "cache-control": "no-store",
  "x-frame-options": "DENY",
  "referrer-policy": "same-origin",
  "x-content-type-options": "nosniff",
  "content-security-policy": "default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; "
    + "img-src data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
};

function page(view: SignInView, status = 200, extra: Record<string, string> = {}): Response {
  return new Response(signInPage(view), { status, headers: { ...PAGE_HEADERS, ...extra } });
}

function redirect(location: string, extra: Record<string, string> = {}): Response {
  return new Response(null, { status: 303, headers: { location, "cache-control": "no-store", ...extra } });
}

/** The request as the API's container gets it: the path without /api, the identity token added, and nothing a browser could use
 * to pose as someone (its own identity header) or that the API has no use for (the session cookie). */
export function forwardToApi(request: Request, path: string, identity: string | null): Request {
  const url = new URL(request.url);
  url.pathname = path;
  const headers = new Headers(request.headers);
  headers.delete(IDENTITY_HEADER);
  const cookies = (headers.get("cookie") ?? "").split(";").filter((part) => part.trim() && !part.trim().startsWith(`${SESSION_COOKIE}=`));
  if (cookies.length > 0) headers.set("cookie", cookies.join(";").trim());
  else headers.delete("cookie");
  if (identity !== null) headers.set(IDENTITY_HEADER, identity);
  const init: RequestInit & { duplex?: "half" } = { method: request.method, headers, redirect: request.redirect };
  if (request.body !== null) {
    init.body = request.body;
    init.duplex = "half";
  }
  return new Request(url.toString(), init);
}

async function formOf(request: Request): Promise<URLSearchParams> {
  const type = request.headers.get("content-type") ?? "";
  if (!type.startsWith("application/x-www-form-urlencoded")) return new URLSearchParams();
  return new URLSearchParams(await request.text());
}

function sameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  return origin === null || origin === new URL(request.url).origin;
}

async function sendCode(email: string, next: string, deps: GateDeps): Promise<Response> {
  if (!isInvited(email, deps.config.invited)) return page({ step: "code", email, next });  // the same answer, so the list stays private
  const issued = await deps.codes.issue(email);
  if ("waitSeconds" in issued) {
    return page({ step: "code", email, next, error: `A code was sent a moment ago. You can ask for a new one in ${issued.waitSeconds} seconds.` }, 429);
  }
  let failure: string | null = null;
  try {
    const sent = await deps.send(codeEmailRequest(deps.config, email, issued.code));
    if (!sent.ok) failure = `the email service answered ${sent.status}: ${(await sent.text()).slice(0, 300)}`;
  } catch (error) {
    failure = `the email service could not be reached: ${error instanceof Error ? error.message : String(error)}`;
  }
  if (failure !== null) {
    console.error(`sign-in: ${failure}`);
    return page({ step: "email", email, next, error: "The sign-in email could not be sent. Try again in a minute." }, 502);
  }
  return page({ step: "code", email, next });
}

export async function signInGate(request: Request, deps: GateDeps): Promise<Response> {
  const url = new URL(request.url);
  const method = request.method.toUpperCase();
  const signedIn = await readSession(deps.sessionKey, readCookie(request.headers.get("cookie"), SESSION_COOKIE), deps.now());
  const user = signedIn !== null && isInvited(signedIn, deps.config.invited) ? signedIn : null;  // off the list, out at once

  if (url.pathname === "/sign-in" || url.pathname === "/sign-in/") {
    const next = safeNext(url.searchParams.get("next"));
    if (user !== null) return redirect(next);
    if (method !== "GET" && method !== "HEAD") return new Response("Method not allowed", { status: 405, headers: { allow: "GET, HEAD" } });
    return page({ step: "email", next });
  }

  if (url.pathname === "/sign-in/code" || url.pathname === "/sign-in/verify") {
    if (method !== "POST") return redirect("/sign-in");
    if (!sameOrigin(request)) return new Response("Forbidden", { status: 403 });
    const form = await formOf(request);
    const next = safeNext(form.get("next"));
    const email = normalizeEmail(form.get("email"));
    if (email === null) return page({ step: "email", next, email: form.get("email") ?? "", error: "That is not an email address." }, 400);
    if (url.pathname === "/sign-in/code") return sendCode(email, next, deps);
    const code = form.get("code") ?? "";
    if (isInvited(email, deps.config.invited) && await deps.codes.check(email, code)) {
      return redirect(next, { "set-cookie": sessionCookie(await signSession(deps.sessionKey, email, deps.now())) });
    }
    return page({ step: "code", email, next, error: "That code is not right, or it has expired. Check it, or send a new code." }, 401);
  }

  if (url.pathname === "/sign-out") return redirect("/sign-in", { "set-cookie": clearedCookie() });

  const path = apiPath(url.pathname);
  if (user === null) {
    if (path !== null) {
      return Response.json({ detail: "Not signed in. Sign in at /sign-in and try again." }, { status: 401, headers: { "cache-control": "no-store" } });
    }
    if (method === "GET" || method === "HEAD") return redirect(`/sign-in?next=${encodeURIComponent(url.pathname + url.search)}`);
    return new Response("Not signed in", { status: 401 });
  }
  if (path !== null) return deps.api(forwardToApi(request, path, await identityToken(deps.identityKey, user, deps.now())));
  return deps.assets(request);
}
