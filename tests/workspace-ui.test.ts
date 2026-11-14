// The coupon workspace after the audit of 2026-11-12 (group PR-WS-UI): every suggestion of the assistant opens a panel the view on screen
// renders, every wide table sits in the one keyboard-reachable scroll box, a ply is labelled one way, and the reference solver's line
// says what the page can show. Behaviour is tested through the helpers the components call; the sources are read only for guards over
// the whole file (no table outside the scroll box, no ply label or panel title written by hand) and for the stylesheet's rules. What a
// component does on the page (the panels it renders, a focused Show scrolling its table back, the rail's edit) is in the browser specs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { PANEL_OF_STEP, PANELS, panelToFix, shownPanel, TENSION_PANEL_OF, TENSION_PANELS, tensionPanelTitle, type PanelId } from "../lib/workspace-panels";
import { SIMPLE_STEPS, STEP_ORDER } from "../lib/studio-chat";
import { runVerification } from "../lib/studio-copy";
import { answerOf, firstPlyOf } from "../lib/studio-answer";
import { fieldsStamp, type Fields, type JobStatus } from "../lib/studio-api";
import { layupNotation, layupRows, parseLayup, sameLayup } from "../lib/studio-chat";

const source = (path: string) => readFileSync(path, "utf8").replace(/\r\n/g, "\n");
const fields = JSON.parse(readFileSync("tests/fixtures/studio/fields.json", "utf8")) as Fields;
const job = (over: Partial<JobStatus>): JobStatus => ({ ...JSON.parse(readFileSync("tests/fixtures/studio/job-done.json", "utf8")), ...over });

test("the product view's panels have one title each, the one the assistant names (audit fea-run-3)", () => {
  // that the tension screen renders each of them under that title, and no other, is in tests/browser/studio.spec.ts
  assert.equal(new Set(TENSION_PANELS.map((p) => p.id)).size, TENSION_PANELS.length);
  assert.equal(tensionPanelTitle("tension-input"), "Material and layup");
  assert.equal(tensionPanelTitle("tension-change"), "Change settings");
  for (const target of Object.values(TENSION_PANEL_OF)) assert.ok(target === null || TENSION_PANELS.some((p) => p.id === target), String(target));
});

test("every suggestion of the assistant opens a panel of the view on screen, and names it as that view does (audit fea-run-3)", () => {
  // the full panels with every test offered: the step panels, by their own titles
  for (const p of PANELS) assert.deepEqual(shownPanel(p.id, true), { id: p.id, title: p.title });
  // the product view: the tension screen's panels; the material and the layup on "Material and layup", the size, load and mesh under "Change settings"
  assert.deepEqual(shownPanel("layup", false), { id: "tension-input", title: "Material and layup" });
  assert.deepEqual(shownPanel("geometry", false), { id: "tension-change", title: "Change settings" });
  assert.deepEqual(shownPanel("loads", false), { id: "tension-change", title: "Change settings" });
  assert.deepEqual(shownPanel("test", false), { id: "tension-coupon", title: "Unnotched tension coupon" });
  assert.equal(shownPanel("project", false), null); // no counterpart: the suggestion is not offered
  // each step the conversation can stand at names a panel the product view renders
  for (const step of [...STEP_ORDER, "review" as const]) assert.ok(shownPanel(PANEL_OF_STEP[step], false), step);
  for (const step of SIMPLE_STEPS) assert.ok(shownPanel(PANEL_OF_STEP[step], false), step);
  // a failing check item's "Fix under …" link: the panel holding its rows, on the tension screen too
  assert.equal(shownPanel(panelToFix({ id: "geometry", rows: ["Length (mm)"] })!, false)?.id, "tension-change");
  assert.equal(shownPanel(panelToFix({ id: "material", rows: ["Library material"] })!, false)?.id, "tension-input");
  // every panel link in the assistant goes through the mapping: no panel id or title written by hand
  const chat = source("components/studio/coupon-chat.tsx");
  for (const [, id] of chat.matchAll(/<PanelLink id="(\w+)"/g)) assert.ok(PANELS.some((p) => p.id === id), id);
  assert.doesNotMatch(chat, /under Layup and material|under Loads and supports|under Geometry|under Run\b|Open Loads and supports/);
  // a panel opened by its own id only where its view is the one on screen: the fibre tow's, and every input behind "All inputs" with every test offered
  assert.doesNotMatch(chat, /showPanel\("(?!tow-fibre|advanced)/);
  const ids: PanelId[] = ["test", "project", "geometry", "layup", "loads", "mesh", "validate", "run", "outputs", "advanced"];
  assert.deepEqual(Object.keys(TENSION_PANEL_OF).sort(), [...ids].sort());
});

test("the results' small actions are buttons with a 24 px target; a text button in a sentence or on a rail keeps its link look (audit fea-run-35)", () => {
  const css = source("app/studio/studio.css");
  assert.match(css, /\n\.studio-text-button \{ display: inline-flex; gap: 6px; align-items: center; background: transparent; padding: 2px 0;/);
  assert.match(css, /\n\.studio-results \.studio-text-button \{ min-height: 24px; padding: 3px 8px; border: 1px solid var\(--line\);/);
  assert.doesNotMatch(css, /\n\.studio-text-button \{[^}]*border: 1px/, "every text button of the site's tools bordered");
});

test("every wide table of the coupon workspace sits in the one scroll box the keyboard reaches, named and with a ring (audit fea-run-9)", () => {
  // the box is a named region with tabindex 0 (checked on the page in tests/browser/studio.spec.ts); its focus ring is the stylesheet's
  assert.match(source("app/studio/studio.css"), /\.studio-table-scroll:focus-visible \{ outline: 2px solid var\(--accent\)/);
  for (const path of ["components/studio/results-view.tsx", "components/workspace/tension-screen.tsx", "components/workspace/chooser.tsx"]) {
    const text = source(path);
    assert.doesNotMatch(text, /className="studio-table-scroll"/, `${path}: a table scroll box by hand`);
    assert.equal((text.match(/<table /g) ?? []).length, (text.match(/<TableScroll /g) ?? []).length, `${path}: a table outside a TableScroll`);
  }
  // the card of the user's own Abaqus on the same results page: its three wide tables, each named; its narrow ones fit their panel
  const card = source("components/studio/abaqus-card.tsx");
  assert.doesNotMatch(card, /className="studio-table-scroll"/, "the Abaqus card: a table scroll box by hand");
  for (const name of ["What differs", "The model, item by item", "The results, zone by zone"]) assert.ok(card.includes(`<TableScroll label="${name}">`), name);
  // a Show the keyboard reaches scrolls its table back to the start (audit uiux-fea-run-21): tests/browser/studio.spec.ts, the answer table
});

test("a ply is labelled one way, \"Ply 4 · 90°\", in the results, the readout and the assistant (audit fea-run-22)", () => {
  for (const path of ["components/studio/results-view.tsx", "lib/studio-fields.ts", "components/studio/coupon-chat.tsx"]) {
    const text = source(path);
    assert.doesNotMatch(text, /\} · \{[^}]*angle[^}]*\}°/, `${path}: a ply label built by hand`);
    assert.doesNotMatch(text, /`Ply \$\{[^`]*\(\$\{[^`]*angle/, `${path}: "Ply 4 (90°)"`);
    assert.doesNotMatch(text, /ply \{?\w*\.?ply\}? · /, `${path}: "ply 4 · 90°"`);
  }
});

test("the assistant's first-ply failure is the answer the centre gives, the gauge section's, with the grip edge as a note (audit fea-run-2)", () => {
  const answer = answerOf(fields)!;
  assert.ok(answer.basis === "gauge" && answer.outside?.touches_grip, "the fixture has an earlier failure at a clamped edge");
  assert.ok(answer.earliest.factor > answer.outside!.factor); // the two numbers the page used to give as one answer
  const first = firstPlyOf(fields)!;
  assert.deepEqual([first.factor, first.name, first.ply, first.angle, first.basis], [answer.earliest.factor, answer.earliest.name, answer.earliest.ply,
    answer.earliest.angle, "the gauge section"]);
  assert.deepEqual(first.outside, answer.outside); // the grip edge's earlier R, as a note
  assert.equal(first.atGrip, false);
  // a job solved before the package wrote the answer: the whole model's earliest criterion, at a grip edge when it is there
  const older = { ...fields, summary: { ...fields.summary, verdict: undefined } } as Fields;
  const whole = fields.summary.fpf[fields.summary.earliest!];
  assert.deepEqual(firstPlyOf(older), { factor: whole.factor, name: "Tsai-Hill", ply: whole.ply, angle: whole.angle, basis: "the whole model", outside: null,
    atGrip: whole.touches_grip });
  assert.equal(firstPlyOf({ ...older, summary: { ...older.summary, earliest: null } } as Fields), null); // no criterion
});

test("the reference solver's line says what the page can show (audit fea-run-10)", () => {
  const calculix = { record: "r", units: "mm-MPa", tolerance: 0.03, agree: "57 of 57", reaction: null, gauge_element: null, gauge: [], frd: null };
  const withBlock = { ...fields, summary: { ...fields.summary, calculix } } as Fields;
  // the fields' own block: the guide's wording, "within 3 %", in the centre and the assistant alike
  assert.deepEqual(runVerification(job({}), withBlock, "done"), { line: "Verified against reference solver: 57 of 57 values within 3 %", verified: true });
  assert.deepEqual(runVerification(job({ state: "running" }), withBlock, "running"), { line: "Verified against reference solver: 57 of 57 values within 3 %", verified: true });
  // the pipeline's own count only for a job that wrote no fields to show a table from
  assert.deepEqual(runVerification(job({ state: "running", outputs: {} }), null, null), { line: "Verified against reference solver: 57 of 57 values agree", verified: true });
  // while the report is written: fields not read yet, or read before the reference solver's values were in them, say nothing yet (review P2)
  assert.equal(runVerification(job({ state: "running" }), null, null), null);
  assert.equal(runVerification(job({ state: "running" }), fields, "running"), null);
  // fields read before the run finished are not yet the finished run's
  assert.equal(runVerification(job({}), fields, "running"), null);
  // a finished run whose fields, read after it finished, carry no reference values: no pass the page cannot show
  assert.deepEqual(runVerification(job({}), fields, "done"), { line: "Reference solver check: values could not be shown for this run.", verified: false });
  assert.equal(runVerification(job({ state: "stopped" }), fields, "done"), null);
});

test("the fields are read again when the result line arrives, the reference solver's values being in them from then (audit fea-run-10)", () => {
  // the stamp the workspace and the viewer read the fields once per
  const solving = job({ state: "running", result: null, outputs: { fields: "fields.json" } });
  const resultIn = { ...solving, result: "57 of 57 recorded values agree" };
  const explained = { ...resultIn, outputs: { ...resultIn.outputs, explanation: "explanation.json" } };
  const done = { ...explained, state: "done" as const };
  const stamps = [solving, resultIn, explained, done].map(fieldsStamp);
  assert.equal(new Set(stamps).size, 4, "each is a new read");
  assert.equal(fieldsStamp({ ...solving, log_tail: ["another line"], stages_done: ["mesh"] }), stamps[0], "a poll with nothing new reads nothing");
  assert.notEqual(fieldsStamp({ ...solving, job_id: "another" }), stamps[0]);
});

test("the same layup submitted again is no edit, so a finished run stays; another layup is one (audit fea-run-J2-2, review P1)", () => {
  // that an edit on the rail leaves the earlier run behind, and the same layup does not, is in tests/browser/studio.spec.ts
  const form = { test: "unnotched tension", library: "im7-8552", ...layupRows(parseLayup("[45/0/-45/90]s")!) };
  assert.equal(layupNotation(form), "[45/0/-45/90]s");
  assert.ok(sameLayup(form, parseLayup("[45/0/-45/90]s")!));
  assert.ok(sameLayup(form, parseLayup("[45/0/-45/90]S")!)); // written another way, the same plies
  assert.ok(!sameLayup(form, parseLayup("[0/90]2s")!));
  assert.ok(!sameLayup(form, parseLayup("[45/0/-45/90]")!)); // the same plies, not mirrored
  assert.ok(!sameLayup({ test: "unnotched tension" }, parseLayup("[45/0/-45/90]s")!)); // a first layup is an edit
});

test("the rail and the assistant stick 12 px under the workspace's header (audit uiux-fea-run-6)", () => {
  // the viewer's section heading over its panels (fea-run-46) is checked on the page, in tests/browser/studio.spec.ts
  const header = /\.site-header\.chat-site-header \{[^}]*\sheight: (\d+)px;/.exec(source("app/research.css"));
  const top = /\.ws-shell \{[^}]*--ws-top: (\d+)px;/.exec(source("app/workspace/workspace.css"));
  assert.ok(header && top, "the header's height and the columns' sticky offset");
  assert.equal(Number(top![1]), Number(header![1]) + 12);
});

test("a field's border is one token at 3:1 or more, on the calculator too (audit uiux-fea-run-23)", () => {
  assert.match(source("app/globals.css"), /:root \{[^}]*--field-line: #6b6b6b;/);
  for (const path of ["app/studio/studio.css", "app/workspace/workspace.css", "app/calculator/calculator.css"]) {
    const css = source(path);
    assert.doesNotMatch(css, /--field-line:/, `${path}: the token defined twice`);
    assert.doesNotMatch(css, /\.(studio-field|studio-ply|chat-inline|chat-rows|calc-field|studio-plate-row)[^{]*\{[^}]*border: 1px solid #414141/, `${path}: a field with the old border`);
  }
  assert.match(source("app/calculator/calculator.css"), /\.calc-field select \{[^}]*border: 1px solid var\(--field-line\)/);
});
