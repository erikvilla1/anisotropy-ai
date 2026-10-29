import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { checkSetup, DOWNLOADS, explainJob, fileUrl, readChecklist, readExplainAnswer, readExplanation, readFields, readJob, readPreview, startSolve, StudioError } from "../lib/studio-api";

const fixture = (name: string) => JSON.parse(readFileSync(`tests/fixtures/studio/${name}.json`, "utf8"));

test("the readers accept the package's files and refuse other shapes", () => {
  assert.equal(readChecklist(fixture("checklist")).items.length, 12);
  assert.equal(readPreview(fixture("preview")).mesh.element_count, 250);
  const fields = readFields(fixture("fields"));
  const bending = readFields(JSON.parse(readFileSync("tests/fixtures/studio-bending/fields.json", "utf8")));
  assert.equal(bending.nodal.displacement[0].length, 3);
  assert.equal(fields.summary.earliest, "tsai_hill");
  assert.equal(readExplanation(fixture("explanation")).writer, "template");
  assert.equal(readJob(fixture("job-running")).stage, "our engine");
  assert.throws(() => readChecklist({ items: "none" }), StudioError);
  assert.throws(() => readPreview({ mesh: {} }), StudioError);
  assert.throws(() => readFields({ ...fixture("fields"), nodal: { displacement: [] } }), /does not match its mesh/);
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
    assert.equal(calls[1].init.credentials, "omit");
  } finally {
    globalThis.fetch = original;
  }
});

test("a refusal carries the API's words and its status", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = (async () => new Response(JSON.stringify({ detail: "coupon job 1 is running; one runs at a time" }), { status: 409 })) as typeof fetch;
  try {
    await assert.rejects(startSolve("http://api.test", { form_version: "0.3" }, "A. Engineer", false), (error: StudioError) => error.status === 409 && /one runs at a time/.test(error.message));
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
    await assert.rejects(checkSetup("http://api.test", {}), /did not answer/);
  } finally {
    globalThis.fetch = original;
  }
});

test("file addresses and the download list", () => {
  assert.equal(fileUrl("http://api.test/", "abc", "fields"), "http://api.test/v1/coupon-jobs/abc/files/fields");
  assert.equal(DOWNLOADS[0][0], "package");
  assert.ok(DOWNLOADS.some(([key]) => key === "prepomax_results"));
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
