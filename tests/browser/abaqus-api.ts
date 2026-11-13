import { type Page, type Route } from "@playwright/test";
import { readFileSync } from "node:fs";

/** The API's routes for the exchange with the user's own Abaqus (ADR-0094 steps 5 to 7), played for the browser tests: what the card
 * may offer, the uploads beside a run, the upload keys and the connector's zip. The comparisons are the fea package's own, from
 * tests/fixtures/abaqus (pinned by fea/tests/test_abaqus_upload.py). Register it after the run's own stand-in: the later route wins. */
export const JOB = "0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00"; // the finished job of tests/fixtures/studio
export const LIMITS = { max_bundle_bytes: 50 * 1024 * 1024, max_uploads: 100, max_tokens: 10 };
export const comparisonOf = (name: string) => JSON.parse(readFileSync(`tests/fixtures/abaqus/${name}.json`, "utf8"));

let made = 0;
/** An upload as the API answers it: beside the fixture's job, with the named comparison or none. */
export function uploadOf(name: string | null, more: Record<string, unknown> = {}) {
  made += 1;
  const comparison = name ? comparisonOf(name) : null;
  return { id: `0b6f6f0e-9d0a-4f43-8a52-${String(made).padStart(12, "0")}`, actor: "studio", user_email: null, token_id: null, created_at: `2026-11-13T09:${String(10 + made).padStart(2, "0")}:00+00:00`,
    bundle_sha256: "ab".repeat(32), bundle_bytes: 253399, units: "mm-MPa", job: "Job-1", coupon: "IM7-UNT-L1", in_scope: true, may_train: false, job_id: JOB,
    verdict: comparison?.verdict ?? null, compared_at: comparison ? "2026-11-13T09:30:04+00:00" : null, not_compared: null, facts: {}, comparison, ...more };
}

export type Answer = { status: number; body: unknown };
export type ExchangeState = {
  /** what GET /v1/abaqus-exchange answers; null for an API that has no such route */
  exchange: ({ uploads: boolean; connector_route: boolean } & typeof LIMITS) | null;
  uploads: ReturnType<typeof uploadOf>[]; // newest first, as the API lists them
  keys: { id: string; name: string; hint: string; created_at: string; last_used_at: string | null; revoked_at: string | null }[];
  sent: { query: Record<string, string>; contentType: string | null; actor: string | null; bytes: number }[];
  compared: string[]; removed: string[]; cancelled: string[]; named: string[]; connector: number; lists: number;
  /** each request for an upload's document: "POST <id>" to have it written, "GET <id>" for the file */
  documents: string[];
  onSend: () => Answer; onCompare: (id: string) => Answer;
  /** what asking for the document to be written answers; the default says it is written */
  onDocument: (id: string) => Answer;
};

export function exchangeState(more: Partial<ExchangeState> = {}): ExchangeState {
  return { exchange: { uploads: true, connector_route: false, ...LIMITS }, uploads: [], keys: [], sent: [], compared: [], removed: [], cancelled: [], named: [], connector: 0, lists: 0, documents: [],
    onSend: () => ({ status: 201, body: uploadOf("agrees") }), onCompare: () => ({ status: 200, body: uploadOf("agrees") }),
    onDocument: (id) => ({ status: 200, body: { upload_id: id, compared_at: "2026-11-13T09:30:04+00:00", filename: "Job-1-compared-with-anisotropy.pdf" } }), ...more };
}

export const TOKEN = `anisotropy_upload_${"k".repeat(43)}`;

export async function mockExchange(page: Page, state: ExchangeState) {
  const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  await page.route(/https?:\/\/[^/]+\/v1\/(abaqus-exchange|abaqus-uploads|abaqus-connector|upload-tokens)/, async (route) => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname, method = request.method();
    if (path === "/v1/abaqus-exchange") return state.exchange ? json(route, state.exchange) : json(route, { detail: "Not Found" }, 404);
    if (path === "/v1/abaqus-connector") { state.connector += 1; return route.fulfill({ status: 200, contentType: "application/zip", body: "PK" }); }
    if (path === "/v1/abaqus-uploads" && method === "GET") {
      state.lists += 1;
      const jobId = url.searchParams.get("job_id");
      return json(route, state.uploads.filter((u) => !jobId || u.job_id === jobId).map((u) => ({ ...u, facts: null, comparison: null })));
    }
    if (path === "/v1/abaqus-uploads" && method === "POST") {
      state.sent.push({ query: Object.fromEntries(url.searchParams), contentType: await request.headerValue("content-type"), actor: await request.headerValue("x-anisotropy-actor"),
        bytes: request.postDataBuffer()?.length ?? 0 });
      const answer = state.onSend();
      if (answer.status === 201) state.uploads.unshift(answer.body as ReturnType<typeof uploadOf>);
      return json(route, answer.body, answer.status);
    }
    const one = path.match(/^\/v1\/abaqus-uploads\/([^/]+)(\/bundle|\/compare|\/document)?$/);
    if (one) {
      const index = state.uploads.findIndex((u) => u.id === one[1]);
      if (index < 0) return json(route, { detail: `No upload ${one[1]} of yours` }, 404);
      if (one[2] === "/bundle") { // a link carries no header, so the API takes the actor from the address here, and refuses a link without it
        if (!(await request.headerValue("x-anisotropy-actor")) && !url.searchParams.get("actor")) return json(route, { detail: "Header X-Anisotropy-Actor is required" }, 422);
        return route.fulfill({ status: 200, contentType: "application/zip", body: "PK" });
      }
      if (one[2] === "/document") { // the comparison as a PDF: asked to be written with the header, then fetched as a link, the actor in the address
        state.documents.push(`${method} ${one[1]}`);
        if (method === "POST") { const answer = state.onDocument(one[1]); return json(route, answer.body, answer.status); }
        if (!(await request.headerValue("x-anisotropy-actor")) && !url.searchParams.get("actor")) return json(route, { detail: "Header X-Anisotropy-Actor is required" }, 422);
        if (!state.uploads[index].comparison) return json(route, { detail: "Not compared: this upload has not stood beside a run of ours yet" }, 409);
        return route.fulfill({ status: 200, contentType: "application/pdf", headers: { "content-disposition": 'attachment; filename="Job-1-compared-with-anisotropy.pdf"' }, body: "%PDF-1.4 a stand-in" });
      }
      if (one[2] === "/compare" && method === "POST") {
        state.compared.push(`${one[1]}?${url.searchParams.toString()}`);
        const answer = state.onCompare(one[1]);
        if (answer.status === 200) state.uploads[index] = { ...(answer.body as ReturnType<typeof uploadOf>), id: one[1], created_at: state.uploads[index].created_at };
        return json(route, answer.status === 200 ? state.uploads[index] : answer.body, answer.status);
      }
      if (method === "DELETE") { state.removed.push(one[1]); state.uploads.splice(index, 1); return route.fulfill({ status: 204, body: "" }); }
      return json(route, state.uploads[index]);
    }
    if (path === "/v1/upload-tokens" && method === "GET") return json(route, state.keys);
    if (path === "/v1/upload-tokens" && method === "POST") {
      const name = String((request.postDataJSON() as { name?: string }).name ?? "");
      state.named.push(name);
      if (state.keys.filter((k) => !k.revoked_at).length >= LIMITS.max_tokens) return json(route, { detail: "You have 10 tokens that are not cancelled; cancel one to create another" }, 429);
      const key = { id: `7d0c7b0a-55aa-4f0e-9a3c-${String(state.keys.length + 1).padStart(12, "0")}`, name, hint: TOKEN.slice(-4), created_at: "2026-11-13T09:05:00+00:00", last_used_at: null, revoked_at: null };
      state.keys.unshift(key);
      return json(route, { ...key, token: TOKEN }, 201);
    }
    const key = path.match(/^\/v1\/upload-tokens\/([^/]+)$/);
    if (key && method === "DELETE") {
      const found = state.keys.find((k) => k.id === key[1]);
      if (!found) return json(route, { detail: `No token ${key[1]} of yours` }, 404);
      state.cancelled.push(key[1]); found.revoked_at = "2026-11-13T09:40:00+00:00";
      return json(route, found);
    }
    return json(route, { detail: `no stand-in for ${method} ${path}` }, 404);
  });
}

/** One finished run of the public tension coupon, for the viewer window: its status, its fields and its explanation. */
export async function mockRun(page: Page, more: { outputs?: Record<string, string>; state?: string; fields?: (fields: Record<string, unknown>) => unknown } = {}) {
  const fixture = (name: string) => JSON.parse(readFileSync(`tests/fixtures/studio/${name}.json`, "utf8"));
  const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  await page.route(/https?:\/\/[^/]+\/v1\//, async (route) => {
    const request = route.request(), path = new URL(request.url()).pathname;
    const job = fixture("job-done");
    if (path === `/v1/coupon-jobs/${JOB}`) return json(route, { ...job, state: more.state ?? job.state, outputs: { ...job.outputs, ...(more.outputs ?? {}) } });
    if (path.endsWith("/files/fields")) return json(route, more.fields ? more.fields(fixture("fields")) : fixture("fields"));
    if (path.endsWith("/files/explanation")) return json(route, fixture("explanation"));
    if (path.endsWith("/explain")) {
      const explanation = fixture("explanation");
      return json(route, { run_id: "run-2", job_id: JOB, kind: "result", writer: "template", model: null, prose: explanation.sentences, withheld: false, reason: null, facts: explanation.facts });
    }
    if (path.endsWith("/files/abaqus_build")) return route.fulfill({ status: 200, contentType: "application/octet-stream", body: "# the build script" });
    return json(route, { detail: `no stand-in for ${request.method()} ${path}` }, 404);
  });
}
