import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  checkSetup, DOWNLOADS, explainJob, fetchFields, fileUrl, getJob, getProject, listProjects, noProjectStore, putProject, readChecklist, readExplainAnswer, readExplanation,
  readFields, readJob, readPreview, readProjectRecord, RECORDS_HEADER, startSolve, StudioError,
} from "../lib/studio-api";
import { bannedIn, customerText, FAILED_WORDS, failedText, JOB_GONE, RESULTS_UNREADABLE } from "../lib/studio-copy";

const fixture = (name: string) => JSON.parse(readFileSync(`tests/fixtures/studio/${name}.json`, "utf8"));

test("the readers accept the package's files and refuse other shapes", () => {
  assert.equal(readChecklist(fixture("checklist")).items.length, 13); // the twelve of ADR-0051 and the Test standard (ADR-0072)
  assert.equal(readPreview(fixture("preview")).mesh.element_count, 250);
  const fields = readFields(fixture("fields"));
  const bending = readFields(JSON.parse(readFileSync("tests/fixtures/studio-bending/fields.json", "utf8")));
  assert.equal(bending.nodal.displacement[0].length, 3);
  assert.equal(fields.summary.earliest, "tsai_hill");
  assert.equal(readExplanation(fixture("explanation")).writer, "template");
  assert.equal(readJob(fixture("job-running")).stage, "our engine");
  assert.throws(() => readChecklist({ items: "none" }), StudioError);
  assert.throws(() => readPreview({ mesh: {} }), StudioError);
  assert.throws(() => readFields({ ...fixture("fields"), nodal: { displacement: [] } }), (error: StudioError) => error.message === RESULTS_UNREADABLE);
  assert.throws(() => readExplanation({ writer: 1 }), StudioError);
  assert.throws(() => readJob({ job_id: 5 }), StudioError);
});

test("the check and the solve send the values with the studio's actor and read the answer", async () => {
  const calls: { url: string; init: RequestInit }[] = [];
  const answers = [{ run_id: "r1", state: "ready", designation: "IM7-UNT-L1", checklist: fixture("checklist"), preview: fixture("preview") }, fixture("job-running")];
  const original = globalThis.fetch;
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(JSON.stringify(answers.shift()), { status: calls.length === 1 ? 200 : 202, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  try {
    const checked = await checkSetup("http://api.test/", { form_version: "0.3", length: 250 });
    assert.equal(checked.state, "ready");
    assert.equal(checked.preview?.mesh.element_count, 250);
    assert.equal(calls[0].url, "http://api.test/v1/coupon-jobs/check");
    assert.equal((calls[0].init.headers as Record<string, string>)["X-Anisotropy-Actor"], "studio");
    assert.deepEqual(JSON.parse(calls[0].init.body as string), { values: { form_version: "0.3", length: 250 } });
    const job = await startSolve("http://api.test", { form_version: "0.3" }, "A. Engineer", true);
    assert.equal(job.state, "running");
    assert.deepEqual(JSON.parse(calls[1].init.body as string), { values: { form_version: "0.3" }, run_by: "A. Engineer", replace: true });
    assert.equal(calls[1].init.credentials, "same-origin");  // the Access cookie reaches the hosted /api, never another origin
  } finally {
    globalThis.fetch = original;
  }
});

test("a refusal carries the API's words and its status", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = (async () => new Response(JSON.stringify({ detail: "Another analysis is running. Wait for it to finish, then run this one." }), { status: 409 })) as typeof fetch;
  try {
    await assert.rejects(startSolve("http://api.test", { form_version: "0.3" }, "A. Engineer", false), // a sentence of its own: no label before it
      (error: StudioError) => error.status === 409 && error.message === "Another analysis is running. Wait for it to finish, then run this one.");
  } finally {
    globalThis.fetch = original;
  }
  globalThis.fetch = (async () => new Response(JSON.stringify({ detail: [{ loc: ["body", "values"], msg: "Field required", type: "missing" }] }), { status: 422 })) as typeof fetch;
  try {
    await assert.rejects(checkSetup("http://api.test", {}), /values: Field required/);
  } finally {
    globalThis.fetch = original;
  }
  globalThis.fetch = (async () => { throw new TypeError("fetch failed"); }) as typeof fetch;
  try {
    await assert.rejects(checkSetup("http://api.test", {}), /Analysis is unavailable right now\. Your inputs are kept/); // an outage: what happened, what to do
  } finally {
    globalThis.fetch = original;
  }
  globalThis.fetch = (async () => new Response(JSON.stringify({ detail: "the container did not answer" }), { status: 503 })) as typeof fetch;
  try {
    await assert.rejects(checkSetup("http://api.test", {}), (error: StudioError) => error.status === 503 && /^Analysis is unavailable right now/.test(error.message));
  } finally {
    globalThis.fetch = original;
  }
});

test("file addresses and the download list", () => {
  assert.equal(fileUrl("http://api.test/", "abc", "fields"), "http://api.test/v1/coupon-jobs/abc/files/fields");
  assert.equal(fileUrl("http://api.test/", "abc", "document", "D3039_[0,90]2s_report.pdf"),
    "http://api.test/v1/coupon-jobs/abc/files/document?name=D3039_%5B0%2C90%5D2s_report.pdf"); // saved under the page's name (ADR-0091)
  // a solver file is asked for by what it is, never by a program's name (decision D4, ADR-0091 amendment 2)
  assert.equal(fileUrl("http://api.test", "abc", "abaqus_deck"), "http://api.test/v1/coupon-jobs/abc/files/solver_input");
  assert.equal(fileUrl("http://api.test", "abc", "prepomax_deck"), "http://api.test/v1/coupon-jobs/abc/files/reference_input");
  assert.equal(fileUrl("http://api.test", "abc", "prepomax_results"), "http://api.test/v1/coupon-jobs/abc/files/reference_results");
  for (const [key] of DOWNLOADS) assert.deepEqual(bannedIn(fileUrl("", "abc", key).replace("/v1/", "/")), [], key);
  // the page offers the report, the package and the solver files; the JSON files, the record, the summary and the .vtu stay outputs, not downloads
  assert.deepEqual(DOWNLOADS.map(([key]) => key), ["document", "package", "abaqus_deck", "prepomax_deck", "prepomax_results"]);
  assert.deepEqual(DOWNLOADS.map(([, label]) => label), ["Report (PDF)", "Full package (ZIP)", "Abaqus input file (.inp)", "Reference solver input (.inp)", "Reference solver results (.frd)"]);
});

test("the explain answer carries its writer and reads only a known shape", async () => {
  const answer = { run_id: null, job_id: "j", kind: "result", writer: "anthropic", model: "claude-opus-5-5", prose: ["The top grip carries 16211 N."], withheld: false, reason: null, facts: {} };
  assert.equal(readExplainAnswer(answer).model, "claude-opus-5-5");
  assert.throws(() => readExplainAnswer({ writer: "template", prose: "text" }), StudioError);
  const original = globalThis.fetch;
  const calls: { url: string; init: RequestInit }[] = [];
  globalThis.fetch = (async (url: string, init: RequestInit) => { calls.push({ url, init }); return new Response(JSON.stringify(answer), { status: 200 }); }) as typeof fetch;
  try {
    const got = await explainJob("http://api.test", "j", "result");
    assert.equal(got.writer, "anthropic");
    assert.equal(calls[0].url, "http://api.test/v1/coupon-jobs/j/explain");
    assert.deepEqual(JSON.parse(calls[0].init.body as string), { kind: "result" });
  } finally {
    globalThis.fetch = original;
  }
});

test("the projects are PUT by id with the studio's actor, listed, and a 503 means the API keeps none (ADR-0062, part 6)", async () => {
  const calls: { url: string; init: RequestInit }[] = [];
  const row = { id: "4f1c2e3d-5a6b-4c7d-8e9f-0a1b2c3d4e5f", kind: "fea", name: "OHT study", actor: "studio", user_email: null, content: { form: { length: "250" }, plate: {} },
    form_version: "0.6", units: "mm-MPa", designation: "IM7-OHT-L1", last_check_run_id: null, created_at: "2026-11-06T10:00:00+00:00", updated_at: "2026-11-06T10:05:00+00:00",
    jobs: [{ job_id: "j1", state: "done", coupon: "IM7-OHT-L1", attempt: "attempt-01", message: "ok", started_at: "2026-11-06T10:01:00+00:00", finished_at: "2026-11-06T10:02:00+00:00", run_id: "r1" }] };
  const answers: [unknown, number, Record<string, string>?][] = [[row, 201], [[row], 200], [{ detail: "Records are switched off on this server" }, 503, { [RECORDS_HEADER]: "off" }],
    [{ detail: "the container did not answer" }, 503]];
  const original = globalThis.fetch;
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    const [body, status, more] = answers.shift()!;
    return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...more } });
  }) as typeof fetch;
  try {
    const saved = await putProject("http://api.test", row.id, { kind: "fea", name: "OHT study", content: row.content, form_version: "0.6", units: "mm-MPa" });
    assert.equal(calls[0].url, `http://api.test/v1/projects/${row.id}`);
    assert.equal(calls[0].init.method, "PUT");
    assert.equal((calls[0].init.headers as Record<string, string>)["X-Anisotropy-Actor"], "studio");
    assert.deepEqual(JSON.parse(calls[0].init.body as string), { kind: "fea", name: "OHT study", content: row.content, form_version: "0.6", units: "mm-MPa" });
    assert.equal(saved.designation, "IM7-OHT-L1");
    assert.equal(saved.jobs[0].run_id, "r1");
    const listed = await listProjects("http://api.test");
    assert.equal(calls[1].init.method, "GET");
    assert.equal(listed.length, 1);
    await assert.rejects(listProjects("http://api.test"), (error: unknown) => noProjectStore(error)); // the API said it keeps none
    await assert.rejects(listProjects("http://api.test"), (error: unknown) => !noProjectStore(error)); // an outage is not that (audit fea-screens-3)
    assert.throws(() => readProjectRecord({ ...row, kind: "stl" }), /could not be read/);
    assert.throws(() => readProjectRecord({ ...row, content: [] }), /could not be read/);
  } finally {
    globalThis.fetch = original;
  }
});

test("only a refusal the user can act on shows the service's words; a job that is gone says so; the rest says what failed (audit fea-screens-2)", async () => {
  const original = globalThis.fetch;
  const answer = (body: unknown, status: number) => { globalThis.fetch = (async () => new Response(JSON.stringify(body), { status })) as typeof fetch; };
  try {
    answer({ detail: "These results are no longer available. Run the analysis again from your project." }, 404);
    await assert.rejects(getJob("http://api.test", "gone"), (error: StudioError) => error.status === 404 && error.message === JOB_GONE);
    answer({ detail: "No coupon job 1: not in this API process, and not in the jobs table" }, 404); // an older API's words never reach the page
    await assert.rejects(fetchFields("http://api.test", "gone"), (error: StudioError) => error.message === JOB_GONE);
    answer({ detail: "No project 7c1a of yours" }, 404);
    await assert.rejects(getProject("http://api.test", "7c1a"),
      (error: StudioError) => error.message === "This project could not be opened. Reload the page; if it happens again, contact us.");
    answer({ detail: "Access denied for this sign-in" }, 403);
    await assert.rejects(startSolve("http://api.test", {}, "A. Engineer", false),
      (error: StudioError) => error.message === "The analysis could not be started. Reload the page; if it happens again, contact us.");
    answer({ detail: "3 runs today; the limit is 3" }, 429);
    await assert.rejects(startSolve("http://api.test", {}, "A. Engineer", false), /^Error: Starting the analysis: 3 runs today; the limit is 3$/);
    // an older API's refusal names the running job's id: the page says what failed instead (audit fea-screens-2)
    answer({ detail: "coupon job 0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00 is running; one runs at a time, so wait for it to end" }, 409);
    await assert.rejects(startSolve("http://api.test", {}, "A. Engineer", false), (error: StudioError) => error.message === failedText("starting the analysis"));
    answer({ detail: "Not Found" }, 401);
    await assert.rejects(getJob("http://api.test", "j1"), (error: StudioError) => error.message.startsWith("The analysis's progress could not be read."));
    answer({ detail: "The run records database did not answer: connection refused" }, 503);
    await assert.rejects(getProject("http://api.test", "7c1a"), (error: StudioError) => /^Analysis is unavailable right now/.test(error.message) && !noProjectStore(error));
  } finally {
    globalThis.fetch = original;
  }
});

test("every request the page makes has its failure in product words (audit fea-run-48)", () => {
  const source = readFileSync("lib/studio-api.ts", "utf8");
  const labels = [...source.matchAll(/\bcall\([^;]*?\}, "([^"]+)"/g)].map((m) => m[1]); // [^;] crosses lines without the s flag
  assert.ok(labels.length >= 15, `the call sites read: ${labels.length}`);
  for (const what of labels) assert.ok(what in FAILED_WORDS, `no failure words for ${what}`);
  for (const [what, words] of Object.entries(FAILED_WORDS)) {
    assert.equal(customerText(failedText(what)), failedText(what), what); // no banned term, path or id
    assert.match(words, /^[A-Z]/, what);
  }
  assert.equal(customerText("coupon job 0f3a2c9e-6b1d-4d2a-9c1e-7a5b3d2f1e00 is running"), null); // a job's id is never shown
});
