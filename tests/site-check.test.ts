import { test } from "node:test";
import assert from "node:assert/strict";
import { Budget, headerCost, modelSlots, monthSpent, runCap, FIRST_GUESS } from "../scripts/site-check/budget";
import { fixedChecks, fixedVerdict, repairClaims, type Seen } from "../scripts/site-check/grade";
import { failureText } from "../scripts/site-check/issue";
import { NumberPool, numbersIn, untraced } from "../scripts/site-check/numbers";
import { moves, NOT_OFFERED, plan } from "../scripts/site-check/plan";
import { NO_PROJECTS, refusal } from "../scripts/site-check/routes";
import { combine, html, markdown, stillFailing } from "../scripts/site-check/report";
import { countOf, runFailed, sameCommit, SCHEMA, verdictOf, type QuestionResult } from "../scripts/site-check/record";
import { scrub, scrubbed } from "../scripts/site-check/scrub";
import { banks, type Question } from "./assistant-questions/harness";

// The site check (ADR-0138): the robot that asks the banks' questions on the live site. What runs in the browser is tried on GitHub
// against the site; what decides a grade, what is written out and what is spent is held here.

// ------------------------------------------------------------------------------------------------- nothing private is written out

test("a secret, an address, a signed link, a session token or a header line never leaves the robot", () => {
  const text = [
    "Signed in as someone@example.com; CF-Access-Client-Secret: abc123secretvalue",
    "the file https://bucket.r2.cloudflarestorage.com/runs/x/fields.json?X-Amz-Signature=deadbeef&X-Amz-Credential=key was read",
    "cookie: CF_Authorization=eyJhbGciOiJSUzI1NiJ9.eyJlbWFpbCI6InNvbWVvbmUifQ.c2lnbmF0dXJlLXNpZ25hdHVyZQ",
    "token eyJhbGciOiJSUzI1NiJ9.eyJlbWFpbCI6InNvbWVvbmUifQ.c2lnbmF0dXJlLXNpZ25hdHVyZQ in a sentence",
    "a key sk-ant-api03-AbCdEfGhIjKlMnOpQrStUvWxYz0123456789abcdef in the text",
    "the run's own id my-client-id.access and value s3cr3t-value",
    // the shape a crash printed on the first live run (2026-11-24): the bucket's account host and a signed query
    "GET https://0123456789abcdef0123456789abcdef.r2.cloudflarestorage.com/anisotropy-outputs/jobs/j1/fields.json?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=AKIDEXAMPLE%2F20261124&X-Amz-Signature=cafe0123",
  ].join("\n");
  const out = scrub(text, ["my-client-id.access", "s3cr3t-value"]);
  for (const leaked of ["someone@example.com", "abc123secretvalue", "X-Amz-Signature", "deadbeef", "eyJhbGci", "sk-ant-api03", "my-client-id.access", "s3cr3t-value", "0123456789abcdef0123456789abcdef.r2", "cloudflarestorage", "AKIDEXAMPLE", "cafe0123"]) {
    assert.ok(!out.includes(leaked), `${leaked} is hidden: ${out}`);
  }
  assert.ok(out.includes("https://[storage]/runs/x/fields.json was read"), "the path stays; the bucket's host and the query go");
  // a commit is public, and the chat's words stay as they are
  assert.equal(scrub("the API on 0123456789abcdef0123456789abcdef01234567"), "the API on 0123456789abcdef0123456789abcdef01234567");
  assert.equal(scrub("Ply 4 (90°) fails first at 1.031 × the applied load"), "Ply 4 (90°) fails first at 1.031 × the applied load");
  assert.deepEqual(scrubbed({ "a@b.co": ["x@y.org", 3] }), { "[hidden]": ["[hidden]", 3] });
});

// ---------------------------------------------------------------------------------------- every number in an answer is the engine's

test("numbers are read as printed: separators, signs, decimals and exponents, but not a layup, a date or a time", () => {
  assert.deepEqual(numbersIn("22,740 N and −0.512 MPa, 1.2e-3, 3.5 × 10⁻⁴ and 7 × 10^6").map((n) => n.value), [22740, -0.512, 1.2e-3, 3.5e-4, 7e6]);
  assert.deepEqual(numbersIn("[45/0/-45/90]s on 2026-11-24 at 10:30").map((n) => n.value), []);
  const [n] = numbersIn("1.031");
  assert.ok(Math.abs(n.half - 0.0005) < 1e-12, "half a unit in the last printed digit");
});

test("a number traces when the engine sent it, to its printed digits, in SI, with a prefix, as a percent or in US units", () => {
  const pool = new NumberPool();
  pool.addJson({ summary: { reaction: 22743.18, stress: 1.18234e9, factor: 1.0312, share: 0.0046 }, labels: ["376"], width: 0.025 });
  assert.deepEqual(untraced("Reaction 22,743 N; σ₁ = 1182 MPa at element 376; 1.031 × the applied load; 0.46 %; 25 mm; 0.984 in", pool), []);
  assert.deepEqual(untraced("5113 lbf", pool), [], "22,743 N in pound-force");
  assert.deepEqual(untraced("σ₁ = 1250 MPa and 23,450 N", pool), ["1250", "23,450"]);
  assert.deepEqual(untraced("ply 4, 90°, 2 steps, 0 MPa", pool), [], "small whole numbers and zero are not results");
});

// --------------------------------------------------------------------------------------------------------------- the fixed checks

const question = (over: Partial<Question> = {}): Question => ({ ask: "which ply fails first", kind: "which", style: "plain", page: "results", route: "failure", ...over });
const seen = (over: Partial<Seen> = {}): Seen => ({ heading: "Ply 4 (90°) fails first", shown: "Ply 4 (90°) fails first\n1.031 × the applied load · Tsai-Hill", folded: "",
  parts: ["chat-failure"], applies: false, seconds: 1.2, timedOut: false, modelCalls: 0, errors: [], ...over });
const pool = () => { const p = new NumberPool(); p.add(1.0312); return p; };

test("an answer that is on time, in the product's words and the engine's numbers passes every fixed check", () => {
  assert.deepEqual(fixedChecks(question(), seen(), pool(), false), []);
  assert.equal(fixedVerdict([]), null);
});

test("no answer, an outage, a slow answer, a tool's name, a long heading or a question that offers a change each fail", () => {
  const names = (s: Partial<Seen>, q: Partial<Question> = {}, modelRead = false) => fixedChecks(question(q), seen(s), pool(), modelRead).map((c) => `${c.name}:${c.level}`);
  assert.deepEqual(names({ timedOut: true, shown: "", heading: "" }), ["answered:fails"]);
  // an answer shown with the page still at work under it (the second run, 2026-11-25: "switch to inches", then "Checking the setup…" for
  // over 45 s) is that answer, timed from when it was shown, and weak: not "no answer appeared"
  const busy = fixedChecks(question(), seen({ timedOut: true, busy: "Checking the setup…", seconds: 0.4 }), pool(), false);
  assert.deepEqual(busy.map((c) => `${c.name}:${c.level}`), ["answered:weak"]);
  assert.match(busy[0].note, /still at work under its answer .*“Checking the setup…”/);
  assert.deepEqual(names({ shown: "That question could not be answered right now. Try again in a moment." }), ["answered:fails"]);
  assert.deepEqual(names({ seconds: 8 }), ["time:weak"]);
  assert.deepEqual(names({ seconds: 25 }), ["time:fails"]);
  assert.deepEqual(names({ seconds: 25, modelCalls: 1 }), ["time:weak"], "a model's reading has longer");
  assert.deepEqual(names({ folded: "Checked by CalculiX" }), ["names:fails"]);
  assert.deepEqual(names({ heading: "Ply 4 (90°) fails first under the applied tension at the gauge centre of the coupon" }), ["heading:fails"]);
  assert.deepEqual(names({ applies: true }), ["changes:fails"]);
  assert.deepEqual(names({ applies: true }, { kind: "change" }), [], "a change offers one");
  assert.deepEqual(names({ errors: ["TypeError: x is undefined"] }), ["page:fails"]);
});

test("a number the engine did not send is weak in the page's answer and fails in words a model wrote", () => {
  const page = fixedChecks(question(), seen({ shown: "Ply 4 fails first at 1.25 × the applied load" }), pool(), false);
  assert.deepEqual(page.map((c) => `${c.name}:${c.level}`), ["numbers:weak"]);
  assert.match(page[0].note, /1\.25/);
  const prose = fixedChecks(question({ kind: "why" }), seen({ shown: "Because ply 4 carries 1.25 times more.", parts: ["chat-why"] }), pool(), true);
  assert.deepEqual(prose.map((c) => `${c.name}:${c.level}`), ["numbers:fails"]);
});

test("the bank's expected answer is held in words: how it opens and what it never says always, its heading and words when the page answers", () => {
  const q = question({ kind: "yes-no", answer: { opens: "Yes", never: ["Which element?"], heading: "Answered in words", says: ["the gauge centre", "1182 MPa"] } });
  const notes = (s: Partial<Seen>, modelRead: boolean) => fixedChecks(q, seen(s), pool(), modelRead).map((c) => c.note);
  assert.deepEqual(notes({ heading: "Answered in words", shown: "Yes. At the gauge centre." }, false), ["does not open with “Yes”"]);
  assert.deepEqual(notes({ heading: "Yes, it does", shown: "Yes, it does. Which element?" }, true), ["says “Which element?”"]);
  assert.deepEqual(notes({ heading: "Yes, it does", shown: "Yes, it does" }, false),
    ["heading “Yes, it does”, expected “Answered in words”", "does not say “the gauge centre”"], "a number in the bank's words is the fixture's and is not held");
});

test("the bank's words are of the answer first shown, of its example's numbers, and of its example's page", () => {
  const solve = question({ kind: "command", page: "repair", answer: { heading: "Solving the slice" } });
  const solved = { heading: "Shear first, at 260.8 N/mm", shown: "Shear first, at 260.8 N/mm", parts: ["repair-chat-answer"] };
  assert.deepEqual(fixedChecks(solve, seen({ ...solved, interim: { heading: "Solving the slice", shown: "", folded: "" } }), pool(), false)
    .filter((c) => c.name === "expected"), [], "the page said what it would do, then did it");
  assert.equal(fixedChecks(solve, seen(solved), pool(), false).filter((c) => c.name === "expected").length, 1, "never said");
  const confirm = question({ kind: "yes-no", answer: { heading: "Yes", opens: "Yes" } });
  const no = { heading: "No", shown: "No. At the applied 1 mm, 16210 N no ply has failed." };
  assert.deepEqual(fixedChecks(confirm, seen({ ...no, foreign: ["16220"] }), pool(), false).filter((c) => c.name === "expected"), [],
    "the question quotes the example's 16220 N: on this coupon No may be right, and the judge grades it");
  assert.equal(fixedChecks(confirm, seen(no), pool(), false).filter((c) => c.name === "expected").length, 2);
  const preview = fixedChecks(question({ page: "setup", answer: { heading: "No answer to read yet" } }), seen(), pool(), false);
  assert.deepEqual(preview.map((c) => `${c.name}:${c.level}`), ["expected:weak"], "a customer's setup previews; the bank's example does not");
});

test("a table read as bare text runs its numbers together, which is why a fold is read cell by cell", () => {
  const pool = new NumberPool();
  for (const v of [74, 12.85, 233.5]) pool.add(v);
  assert.deepEqual(untraced("4 (pick) 74 12.85 233.5 Yes", pool), []);
  assert.deepEqual(untraced("4 (pick)7412.85233.5Yes", pool), ["7412.85233"], "read as one number, it traces to nothing");
});

test("a repair's answer never calls the repair strong enough, safe or a margin unless it says it is not", () => {
  assert.deepEqual(repairClaims("The repair is strong enough for 230 N/mm."), ["strong enough"]);
  assert.deepEqual(repairClaims("Not the repair's strength: the adhesive yields before it fails. Neither is a margin."), []);
  assert.deepEqual(repairClaims("It stays elastic at 230 N/mm. It is safe."), ["safe"]);
  const checks = fixedChecks(question({ page: "repair", kind: "yes-no" }), seen({ heading: "Yes", shown: "Yes. The repair carries the load." }), pool(), false);
  assert.deepEqual(checks.map((c) => c.name), ["repair"]);
});

test("the same question back twice in a row fails", () => {
  const checks = fixedChecks(question({ after: ["stress at ply 7"] }), seen({ heading: "Which element?", shown: "Which element?", before: "Which element?" }), pool(), false);
  assert.deepEqual(checks.map((c) => `${c.name}:${c.criterion}`), ["asked-twice:11"]);
});

// ---------------------------------------------------------------------------------------------------------------------- the plan

test("a quick run asks only what the page answers itself, a full run the model's too, and the founder's pages are left out with the reason", () => {
  const all = banks();
  const quick = plan("quick", [], all), full = plan("full", [], all);
  const total = all.reduce((n, b) => n + b.questions.length, 0);
  assert.equal(quick.asked.length + quick.skipped.length, total);
  assert.equal(full.asked.length + full.skipped.length, total);
  assert.ok(quick.asked.every((p) => !p.modelRead) && full.asked.some((p) => p.modelRead));
  assert.ok(full.skipped.every((s) => s.question.page !== "results" || s.question.picked !== undefined || s.reason.includes("Ansys file")),
    "every results question is asked unless it needs a click or is of a page without the Ansys file");
  for (const page of Object.keys(NOT_OFFERED)) assert.ok(full.asked.every((p) => p.question.page !== page), `${page} is a founder's page`);
  // each page's questions together, those that move the page on last
  const pages = full.asked.map((p) => p.question.page);
  assert.deepEqual(pages, [...pages].sort((a, b) => pages.indexOf(a) - pages.indexOf(b)), "grouped by page");
  assert.throws(() => plan("full", ["no-such-bank"], all), /no bank named no-such-bank/);
  // the site offers the Ansys file to everyone (ADR-0129 amendment 3): a bank's question of a page without it, whose twin with the file
  // offered is in the same bank, is left out (the second run, 2026-11-25: "download ansys model" failed for offering the file)
  const ansys = full.skipped.filter((s) => s.reason.includes("Ansys file")).map((s) => `${s.id} ${s.ask}`);
  assert.deepEqual(ansys, ["model-downloads#3 download ansys model", "model-downloads#6 export the model"]);
  assert.ok(["model-downloads#1", "model-downloads#2", "model-downloads#5"].every((id) => full.asked.some((p) => p.id === id)), "the twins and the rest are asked");
  // an analysis is run in the full run only (ADR-0138 amendment 3): a quick run asks no "run" and sets up no page of results
  assert.ok(quick.asked.every((p) => p.question.route !== "run" && p.question.page !== "results"));
  assert.ok(quick.skipped.some((s) => s.question.route === "run" && s.reason.includes("deploy check")));
  assert.ok(full.asked.some((p) => p.question.route === "run") && full.asked.some((p) => p.question.page === "results"));
});

test("the robot answers the projects as an API that keeps none, and in a quick run the model's routes and a new analysis unavailable", () => {
  // 2026-11-25: the wing page opened a wing with spar caps an earlier run had added; the robot's quick runs used up the day's analyses of
  // the check's sign-in, so the deploy of 2dbcf8f ran no job
  for (const quick of [true, false]) {
    assert.equal(refusal("GET", "/api/v1/projects", quick), "projects");
    assert.equal(refusal("PUT", "/api/v1/projects/0b3c6a1e-1111-4222-8333-944455556666", quick), "projects");
    assert.equal(refusal("GET", "/api/v1/projects/0b3c6a1e-1111-4222-8333-944455556666", quick), "projects");
  }
  assert.equal(refusal("POST", "/api/v1/workspace/result-questions", true), "model");
  assert.equal(refusal("POST", "/api/v1/coupon-jobs", true), "analysis");
  assert.equal(refusal("POST", "/api/v1/wings/checks", true), "analysis");
  for (const path of ["/api/v1/coupon-jobs/check", "/api/v1/coupon-jobs/live", "/api/v1/coupon-jobs/model", "/api/v1/wings/analyze", "/api/v1/repairs/bond"]) {
    assert.equal(refusal("POST", path, true), null, `${path} is the page's own work, asked in a quick run`);
  }
  assert.equal(refusal("GET", "/api/v1/coupon-jobs", true), null, "the list of past analyses is read");
  for (const path of ["/api/v1/workspace/result-questions", "/api/v1/coupon-jobs", "/api/v1/wings/checks"]) assert.equal(refusal("POST", path, false), null);
  // what the page reads as "this server keeps no projects" (lib/studio-api.ts, noProjectStore)
  assert.equal(NO_PROJECTS.status, 503);
  assert.equal(NO_PROJECTS.headers["X-Anisotropy-Records"], "off");
});

test("in a full run the model's questions take turns under the cap: those asked longest ago first", () => {
  const all = banks();
  const models = plan("full", [], all).asked.filter((p) => p.modelRead);
  const first = plan("full", [], all, { slots: 10, lastAsked: {} });
  const asked = first.asked.filter((p) => p.modelRead).map((p) => p.id);
  assert.equal(asked.length, 10);
  const lastAsked = Object.fromEntries(asked.map((id) => [id, "2026-11-24T00:00:00Z"]));
  const second = plan("full", [], all, { slots: 10, lastAsked }).asked.filter((p) => p.modelRead).map((p) => p.id);
  assert.equal(second.filter((id) => asked.includes(id)).length, 0, "the next run asks the next ten");
  assert.ok(models.length > 20);
  assert.ok(first.skipped.some((s) => /its turn comes in a later full run/.test(s.reason)));
});

// ------------------------------------------------------------------------------------------------------------------------ the spend

test("the cap: the site's cost from each answer's header, a run within its cap and the month's, the slots from what was measured", () => {
  assert.deepEqual(headerCost("0.018250; calls=1; unpriced=0", 1), { dollars: 0.01825, calls: 1 });
  assert.deepEqual(headerCost("0.010000; calls=2; unpriced=1", 1), { dollars: 0.01 + FIRST_GUESS, calls: 2 });
  assert.deepEqual(headerCost(undefined, 1), { dollars: FIRST_GUESS, calls: 1 }, "a site from before the header is counted at the first guess");
  const ledger = [{ at: "2026-11-02T10:00:00Z", mode: "full", site: 0.9, judge: 0.05, models: 40 }, { at: "2026-10-30T10:00:00Z", mode: "full", site: 5, judge: 0 }];
  assert.ok(Math.abs(monthSpent(ledger, new Date("2026-11-24T00:00:00Z")) - 0.95) < 1e-9);
  assert.equal(runCap(1, ledger, new Date("2026-11-24T00:00:00Z"), 20), 1);
  assert.ok(Math.abs(runCap(1, ledger, new Date("2026-11-24T00:00:00Z"), 1.5) - 0.55) < 1e-9, "no more than the month has left");
  assert.equal(modelSlots(1, []), Math.floor(0.9 / FIRST_GUESS));
  assert.equal(modelSlots(1, ledger), Math.floor(0.9 / (0.9 / 40)));
  const budget = new Budget(0.1, 10);
  assert.ok(budget.fits());
  budget.add(0.05);
  assert.ok(!budget.fits(), "0.05 spent, 0.05 more likely, 0.01 kept for the judge: over 0.10");
});

// ------------------------------------------------------------------------------------------------------------------- the report

const result = (over: Partial<QuestionResult>): QuestionResult => ({ id: "which-ply-fails#1", feature: "which-ply-fails", ask: "which ply fails first", after: [], kind: "which",
  style: "plain", page: "results", route: "failure", modelRead: false, gap: null, foreign: [], asked: true, reason: null,
  answer: { heading: "Ply 4 (90°) fails first", shown: "Ply 4 (90°) fails first", folded: "", parts: [], applies: false }, seconds: 1, modelCalls: 0, cost: 0, checks: [],
  judge: null, verdict: "holds", picture: null, ...over });

test("one verdict per question: a fixed check that fails, then the judge; a known gap's failure does not fail the run", () => {
  assert.equal(verdictOf(false, [], null), "not-asked");
  assert.equal(verdictOf(true, [{ name: "time", level: "weak", note: "" }], { verdict: "holds", criteria: [], why: "" }), "weak");
  assert.equal(verdictOf(true, [], { verdict: "fails", criteria: [1], why: "x" }), "fails");
  assert.equal(verdictOf(true, [], null), "holds");
  assert.equal(runFailed([result({ verdict: "fails", gap: "criterion 7: no caution" })], []), false);
  assert.equal(runFailed([result({ verdict: "fails" })], []), true);
  assert.equal(runFailed([], [{ page: "results", state: "failed", seconds: 1, reason: "the run did not finish", picture: null }]), true);
  assert.deepEqual(countOf([result({}), result({ verdict: "weak" })]), { holds: 1, weak: 1, fails: 0, "not-asked": 0 });
});

test("a run asks the banks of the commit the site runs: a short commit is the same as its full one", () => {
  assert.ok(sameCommit("29d483b59c897fc0f94bf8df08719aec3854c787", "29d483b"));
  assert.ok(sameCommit("29D483B", "29d483b59c897fc0f94bf8df08719aec3854c787"));
  assert.ok(!sameCommit("29d483b59c897fc0f94bf8df08719aec3854c787", "1d6451427d3fa4b427b69bb24c96ab16d482d980"));
  assert.ok(!sameCommit(null, "29d483b") && !sameCommit("29d483b", "") && !sameCommit(undefined, undefined));
});

test("a run that tells nothing opens, adds to and closes no issue, and keeps what failed; a failure that stays is told once", () => {
  const run = { site: "https://anisotropy.dev", mode: "quick" as const, started: "2026-11-25T02:38:00Z", finished: "2026-11-25T03:10:00Z", commit: "29d483b", cap: 1, siteSpent: 0, stopped: null };
  const judged = { grades: {}, spent: 0, stopped: null };
  const failingPage = { page: "past", state: "failed" as const, seconds: 3, reason: "the history did not load", picture: null };
  const asked = { run: { ...run, void: "the site changed while the run asked (29d483b to 1d64514): a deploy landed, and its own run asks again" }, pages: [failingPage],
    questions: [result({ verdict: "fails", checks: [{ name: "answered", level: "fails", note: "no answer appeared" }] })] };
  const voided = combine(asked, judged, [], new Date("2026-11-25T03:11:00Z"), []);
  assert.equal(voided.void, asked.run.void);
  assert.match(markdown(voided, null), /\*\*This run tells nothing:\*\* the site changed while the run asked \(29d483b to 1d64514\)[\s\S]*No issue was opened, added to or closed/);
  // the same failures as the run before: nothing new to tell; one more, and it is new
  const same = combine({ ...asked, run }, judged, [], new Date("2026-11-25T03:11:00Z"), ["which-ply-fails#1", "page:past"]);
  assert.equal(same.void, null);
  assert.ok(same.failed);
  assert.deepEqual(same.newlyFailing, []);
  assert.deepEqual(stillFailing(same), ["page:past", "which-ply-fails#1"]);
  const more = combine({ ...asked, run }, judged, [], new Date("2026-11-25T03:11:00Z"), ["which-ply-fails#1"]);
  assert.deepEqual(more.newlyFailing, ["page:past"]);
  // a page that failed before and was set up this time is resolved; one not tried this time stays unresolved
  const later = combine({ run, pages: [{ ...failingPage, state: "set-up" as const }], questions: [result({})] }, judged, [], new Date("2026-11-25T03:11:00Z"), ["page:past", "page:wing"]);
  assert.deepEqual(later.unresolved, ["page:wing"]);
  assert.ok(!later.failed);
});

test("the report joins the judge's grades, keeps what failed before and was not asked again, and is written in plain words", () => {
  const asked = { run: { site: "https://anisotropy.dev", mode: "quick" as const, started: "2026-11-24T19:00:00Z", finished: "2026-11-24T19:20:00Z", commit: "ed4968a90f8233f1918e42cf33897e81fd2a3b4d",
    cap: 1, siteSpent: 0, stopped: null }, pages: [], questions: [result({}), result({ id: "why-answers#2", feature: "why-answers", ask: "why does ply 4 fail", asked: false, reason: "a model reads it on the site: asked in the full run", answer: null })] };
  const judged = { grades: { "which-ply-fails#1": { verdict: "fails" as const, criteria: [6], why: "does not show the failure load" } }, spent: 0.002, stopped: null };
  const r = combine(asked, judged, [], new Date("2026-11-24T19:21:00Z"), ["why-answers#2", "result-values#3"]);
  assert.equal(r.schema, SCHEMA);
  assert.equal(r.questions.find((q) => q.id === "which-ply-fails#1")?.verdict, "fails");
  assert.deepEqual(r.unresolved, ["why-answers#2", "result-values#3"], "failed before and not asked in this run");
  assert.ok(r.failed);
  assert.deepEqual(stillFailing(r), ["result-values#3", "which-ply-fails#1", "why-answers#2"]);
  const md = markdown(r, "https://github.com/o/r/actions/runs/1");
  assert.match(md, /^# Site check, quick run, 2026-11-24 19:00 UTC/);
  assert.match(md, /the API on ed4968a/);
  assert.match(md, /which-ply-fails#1 “which ply fails first” \(results\): judge: does not show the failure load \(criteria 6\)/);
  assert.match(md, /1: a model reads it on the site: asked in the full run/);
  const page = html(r, () => "data:image/jpeg;base64,AAAA");
  assert.match(page, /<title>Site check report<\/title>/);
  assert.match(page, /prefers-color-scheme:dark/);
  assert.ok(!page.includes("<script"), "the page runs no script");
  assert.match(failureText(r, "https://github.com/o/r/actions/runs/1"), /found 1 answer that fails[\s\S]*which-ply-fails#1 “which ply fails first” \(results\): judge: does not show the failure load/);
});

test("a question that changes the page's rows has the page set up again after it, so the next is asked of the bank's coupon", () => {
  // the second run asked "what units are you using?" after "work in metres" and graded "m, Pa and N" as wrong
  const bank = banks().find((b) => b.feature === "commands-and-units")!;
  const asked = (words: string) => bank.questions.find((q) => q.ask === words)!;
  assert.equal(moves(asked("switch to inches")), true);
  assert.equal(moves(asked("A. Engineer")), true);
  assert.equal(moves(asked("what units are you using?")), false);
});
