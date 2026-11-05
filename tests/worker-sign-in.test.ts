// Our own sign-in (ADR-0058): the settings, the invite list, the session cookie, the identity token the API checks, the codes,
// and the whole flow through the Worker's front door with stand-ins for the site's files, the API, the code store and the email.
import assert from "node:assert/strict";
import { test } from "node:test";

import { forwardToApi, signInGate, type GateDeps } from "../worker/gate";
import { signInPage } from "../worker/sign-in-page";
import {
  CODE_ATTEMPTS, IDENTITY_HEADER, SESSION_COOKIE, SESSION_SECONDS, checkCode, deriveKey, identityToken, isInvited, issueCode,
  parseInvited, readCookie, readSession, safeNext, signInConfig, signSession, type CodeRecord, type CodeStore,
} from "../worker/sign-in";

const SECRET = "test-session-secret-0123456789abcdefghij";
const ENV = {
  ANISOTROPY_SESSION_SECRET: SECRET,
  ANISOTROPY_INVITED: "engineer@example.com,\n @anisotropy.dev",
  RESEND_API_KEY: "re_test",
  ANISOTROPY_EMAIL_FROM: "Anisotropy <sign-in@anisotropy.dev>",
};
const SITE = "https://anisotropy.dev";

function memoryStore(): CodeStore & { map: Map<string, CodeRecord> } {
  const map = new Map<string, CodeRecord>();
  return {
    map,
    get: async (key) => map.get(key),
    put: async (key, value) => { map.set(key, structuredClone(value)); },
    delete: async (key) => map.delete(key),
  };
}

test("the settings are all four or none, and the secret is long enough", () => {
  assert.equal(signInConfig({}), null);
  assert.equal(signInConfig({ ANISOTROPY_SESSION_SECRET: "  " }), null);
  assert.throws(() => signInConfig({ ANISOTROPY_SESSION_SECRET: SECRET }), /ANISOTROPY_INVITED, RESEND_API_KEY, ANISOTROPY_EMAIL_FROM not set/);
  assert.throws(() => signInConfig({ ...ENV, ANISOTROPY_SESSION_SECRET: "short" }), /at least 32 characters/);
  assert.throws(() => signInConfig({ ...ENV, ANISOTROPY_INVITED: "not-an-email" }), /not an email address/);
  const config = signInConfig(ENV)!;
  assert.equal(config.resendKey, "re_test");
  assert.deepEqual([...config.invited.emails], ["engineer@example.com"]);
  assert.deepEqual([...config.invited.domains], ["anisotropy.dev"]);
});

test("an email is invited by name or by its domain, in any case", () => {
  const invited = parseInvited("Engineer@Example.com @anisotropy.dev");
  assert.ok(isInvited("engineer@example.com", invited));
  assert.ok(isInvited("kai@anisotropy.dev", invited));
  assert.ok(!isInvited("someone@example.com", invited));
  assert.ok(!isInvited("kai@notanisotropy.dev", invited));
  assert.ok(!isInvited("kai@anisotropy.dev.evil.example", invited));
});

test("a session cookie vouches for its email until it expires, and not at all once altered", async () => {
  const key = await deriveKey(SECRET, "session");
  const now = 1_800_000_000_000;
  const value = await signSession(key, "engineer@example.com", now);
  assert.equal(await readSession(key, value, now), "engineer@example.com");
  assert.equal(await readSession(key, value, now + (SESSION_SECONDS - 1) * 1000), "engineer@example.com");
  assert.equal(await readSession(key, value, now + SESSION_SECONDS * 1000), null);
  const [version, payload, signature] = value.split(".");
  const forged = Buffer.from(JSON.stringify({ e: "boss@example.com", x: 9_999_999_999 })).toString("base64url");
  assert.equal(await readSession(key, `${version}.${forged}.${signature}`, now), null);
  assert.equal(await readSession(key, `${version}.${payload}.${signature.slice(0, -2)}AA`, now), null);
  assert.equal(await readSession(await deriveKey(`${SECRET}x`, "session"), value, now), null);
  assert.equal(await readSession(await deriveKey(SECRET, "identity"), value, now), null);  // one key per use
  for (const junk of [null, "", "v1", "v2.a.b", "v1.a.b.c", "v1.!!.??"]) assert.equal(await readSession(key, junk, now), null);
});

test("the identity token is the one the API verifies (the vector in api/tests/test_identity.py)", async () => {
  const key = await deriveKey("vector-secret-0123456789abcdefghijklmnop", "identity");
  assert.equal(await identityToken(key, "engineer@example.com", 1_800_000_000_000),
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJhbmlzb3Ryb3B5LWFwaSIsImVtYWlsIjoiZW5naW5lZXJAZXhhbXBsZS5jb20iLCJleHAiOjE4MDAwMDAxMjAs"
    + "ImlhdCI6MTgwMDAwMDAwMCwiaXNzIjoiYW5pc290cm9weS1zaWduLWluIn0.Bn_cPjz92xeREhCaBmB3uAU2lKqvKot12nxWZ3RlFO4");
});

test("after signing in, only a path on this site", () => {
  for (const good of ["/", "/studio", "/studio?coupon=a&b=1", "/chat#x"]) assert.equal(safeNext(good), good);
  for (const bad of [null, "", "studio", "https://evil.example", "//evil.example", "/\\evil.example", "/sign-in", "/sign-out", "/a\nb"]) {
    assert.equal(safeNext(bad), "/", String(bad));
  }
});

test("a code works once, for ten minutes, and five wrong guesses use it up", async () => {
  const store = memoryStore();
  const now = 1_800_000_000_000;
  assert.deepEqual(await issueCode(store, "e@x.com", now, () => "123456"), { code: "123456" });
  assert.ok(!(await checkCode(store, "e@x.com", "654321", now)));
  assert.ok(await checkCode(store, "e@x.com", " 123 456 ", now + 1000));
  assert.ok(!(await checkCode(store, "e@x.com", "123456", now + 2000)), "used up");

  await issueCode(store, "f@x.com", now, () => "111111");
  assert.ok(!(await checkCode(store, "f@x.com", "111111", now + 10 * 60_000)), "expired");

  await issueCode(store, "g@x.com", now, () => "222222");
  for (let attempt = 0; attempt < CODE_ATTEMPTS; attempt += 1) assert.ok(!(await checkCode(store, "g@x.com", "000000", now)));
  assert.ok(!(await checkCode(store, "g@x.com", "222222", now)), "spent by the wrong guesses");
  assert.ok(!(await checkCode(store, "nobody@x.com", "222222", now)));
});

test("codes are sent at most every thirty seconds and five times an hour", async () => {
  const store = memoryStore();
  let now = 1_800_000_000_000;
  assert.ok("code" in await issueCode(store, "e@x.com", now));
  assert.deepEqual(await issueCode(store, "e@x.com", now + 10_000), { waitSeconds: 20 });
  for (let sent = 1; sent < 5; sent += 1) {
    now += 31_000;
    assert.ok("code" in await issueCode(store, "e@x.com", now), `send ${sent + 1}`);
  }
  now += 31_000;
  const waited = await issueCode(store, "e@x.com", now);
  assert.ok("waitSeconds" in waited && waited.waitSeconds > 3000);
  assert.ok("code" in await issueCode(store, "e@x.com", 1_800_000_000_000 + 3600_000 + 1));
});

// ----------------------------------------------------------------------------------------------------------- the front door

async function door(overrides: Partial<GateDeps> = {}) {
  const store = memoryStore();
  const sent: Request[] = [];
  const toApi: Request[] = [];
  let clock = 1_800_000_000_000;
  const deps: GateDeps = {
    config: signInConfig(ENV)!,
    sessionKey: await deriveKey(SECRET, "session"),
    identityKey: await deriveKey(SECRET, "identity"),
    now: () => clock,
    assets: async (request) => new Response(`file ${new URL(request.url).pathname}`),
    api: async (request) => { toApi.push(request); return Response.json({ ok: true }); },
    codes: { issue: (email) => issueCode(store, email, clock, () => "123456"), check: (email, code) => checkCode(store, email, code, clock) },
    send: async (request) => { sent.push(request); return new Response("{}", { status: 200 }); },
    ...overrides,
  };
  const go = (path: string, init: RequestInit = {}) => signInGate(new Request(`${SITE}${path}`, init), deps);
  const post = (path: string, form: Record<string, string>, headers: Record<string, string> = {}) =>
    go(path, { method: "POST", body: new URLSearchParams(form), headers: { origin: SITE, ...headers } });
  return { deps, store, sent, toApi, go, post, tick: (ms: number) => { clock += ms; } };
}

function cookieFrom(response: Response): string {
  const set = response.headers.get("set-cookie") ?? "";
  assert.match(set, new RegExp(`^${SESSION_COOKIE}=v1\\.`));
  assert.match(set, /HttpOnly/);
  assert.match(set, /Secure/);
  assert.match(set, /SameSite=Lax/);
  return set.split(";")[0];
}

test("without a session, pages go to the sign-in and the API answers 401", async () => {
  const { go, toApi } = await door();
  const page = await go("/studio?coupon=x");
  assert.equal(page.status, 303);
  assert.equal(page.headers.get("location"), "/sign-in?next=%2Fstudio%3Fcoupon%3Dx");
  const apiCall = await go("/api/v1/materials");
  assert.equal(apiCall.status, 401);
  assert.match((await apiCall.json()).detail, /Not signed in/);
  assert.equal((await go("/", { method: "POST" })).status, 401);
  assert.equal(toApi.length, 0);
});

test("an invited engineer signs in with the emailed code and reaches the site and the API as themselves", async () => {
  const { go, post, sent, toApi } = await door();
  const first = await go("/sign-in?next=%2Fstudio");
  assert.equal(first.status, 200);
  const html = await first.text();
  assert.match(html, /Send sign-in code/);
  assert.match(html, /name="next" value="\/studio"/);
  assert.doesNotMatch(html, /cloudflare/i);
  assert.match(first.headers.get("content-security-policy") ?? "", /frame-ancestors 'none'/);

  const asked = await post("/sign-in/code", { email: " Engineer@Example.com ", next: "/studio" });
  assert.equal(asked.status, 200);
  assert.match(await asked.text(), /Check your email/);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].url, "https://api.resend.com/emails");
  assert.equal(sent[0].headers.get("authorization"), "Bearer re_test");
  const email = await sent[0].json();
  assert.deepEqual(email.to, ["engineer@example.com"]);
  assert.equal(email.from, "Anisotropy <sign-in@anisotropy.dev>");
  assert.match(email.subject, /^123456 /);
  assert.match(email.text, /123456/);

  const wrong = await post("/sign-in/verify", { email: "engineer@example.com", code: "000000", next: "/studio" });
  assert.equal(wrong.status, 401);
  assert.match(await wrong.text(), /not right/);

  const right = await post("/sign-in/verify", { email: "engineer@example.com", code: "123456", next: "/studio" });
  assert.equal(right.status, 303);
  assert.equal(right.headers.get("location"), "/studio");
  const cookie = cookieFrom(right);

  const file = await go("/studio", { headers: { cookie } });
  assert.equal(await file.text(), "file /studio");
  assert.equal((await go("/sign-in?next=%2Fchat", { headers: { cookie } })).headers.get("location"), "/chat");

  const apiCall = await go("/api/v1/coupon-jobs?x=1", {
    headers: { cookie: `theme=dark; ${cookie}`, [IDENTITY_HEADER]: "forged-by-the-browser" },
  });
  assert.equal(apiCall.status, 200);
  assert.equal(toApi.length, 1);
  const forwarded = toApi[0];
  assert.equal(new URL(forwarded.url).pathname + new URL(forwarded.url).search, "/v1/coupon-jobs?x=1");
  assert.equal(forwarded.headers.get("cookie"), "theme=dark");
  const identity = forwarded.headers.get(IDENTITY_HEADER) ?? "";
  assert.notEqual(identity, "forged-by-the-browser");
  assert.equal(identity, await identityToken(await deriveKey(SECRET, "identity"), "engineer@example.com", 1_800_000_000_000));
});

test("someone not invited gets the same answer and no email", async () => {
  const { post, sent } = await door();
  const asked = await post("/sign-in/code", { email: "stranger@example.com", next: "/" });
  assert.equal(asked.status, 200);
  assert.match(await asked.text(), /Check your email/);
  assert.equal(sent.length, 0);
  assert.equal((await post("/sign-in/verify", { email: "stranger@example.com", code: "123456", next: "/" })).status, 401);
});

test("a session ends when its email leaves the invite list, when it is altered, and at sign-out", async () => {
  const { deps, go, post } = await door();
  await post("/sign-in/code", { email: "kai@anisotropy.dev", next: "/" });
  const cookie = cookieFrom(await post("/sign-in/verify", { email: "kai@anisotropy.dev", code: "123456", next: "/" }));
  assert.equal((await go("/", { headers: { cookie } })).status, 200);
  assert.equal((await go("/", { headers: { cookie: `${cookie}x` } })).status, 303);
  const out = await go("/sign-out", { headers: { cookie } });
  assert.equal(out.headers.get("location"), "/sign-in");
  assert.match(out.headers.get("set-cookie") ?? "", /Max-Age=0/);
  deps.config = signInConfig({ ...ENV, ANISOTROPY_INVITED: "engineer@example.com" })!;
  assert.equal((await go("/", { headers: { cookie } })).status, 303);
});

test("a form posted from another site is refused, and a fast second code waits", async () => {
  const { post, sent } = await door();
  assert.equal((await post("/sign-in/code", { email: "engineer@example.com" }, { origin: "https://evil.example" })).status, 403);
  assert.equal(sent.length, 0);
  assert.equal((await post("/sign-in/code", { email: "engineer@example.com" })).status, 200);
  const again = await post("/sign-in/code", { email: "engineer@example.com" });
  assert.equal(again.status, 429);
  assert.match(await again.text(), /in 30 seconds/);
  assert.equal(sent.length, 1);
});

test("when the email service fails, the page says so and asks to try again", async () => {
  const { post } = await door({ send: async () => new Response("bad key", { status: 401 }) });
  const failed = await post("/sign-in/code", { email: "engineer@example.com", next: "/" });
  assert.equal(failed.status, 502);
  assert.match(await failed.text(), /could not be sent/);
  const { post: postUnreachable } = await door({ send: async () => { throw new TypeError("fetch failed"); } });
  assert.equal((await postUnreachable("/sign-in/code", { email: "engineer@example.com", next: "/" })).status, 502);
});

test("the page escapes what a request puts in it", () => {
  const html = signInPage({ step: "code", next: '/x"><script>alert(1)</script>', email: 'a"<b>@x.com' });
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /&quot;&gt;&lt;script&gt;/);
});

test("the API's request keeps its method and body and loses the browser's identity header", async () => {
  const original = new Request(`${SITE}/api/v1/cases/solve`, {
    method: "POST", body: JSON.stringify({ case: {} }), headers: { "content-type": "application/json", [IDENTITY_HEADER]: "x" },
  });
  const forwarded = forwardToApi(original, "/v1/cases/solve", null);
  assert.equal(forwarded.method, "POST");
  assert.equal(new URL(forwarded.url).pathname, "/v1/cases/solve");
  assert.equal(forwarded.headers.get(IDENTITY_HEADER), null);
  assert.deepEqual(await forwarded.json(), { case: {} });
  assert.equal(readCookie("a=1; b=2", "b"), "2");
});
