import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import type { Fields, JobStatus } from "../lib/studio-api";
import { isQuestion, routeMessage, type ChatState } from "../lib/chat-route";
import { followedAnswer, followedAsked, levelAsked } from "../lib/followed-ask";
import { curveLayout, niceStep } from "../lib/followed-curve";
import { changesBetween } from "../lib/model-versions";
import { failureAnswer, failureLines, marginNote } from "../lib/result-failure";
import { answerWords, readJobAnswer } from "../lib/run-history";
import { summaryAnswer } from "../lib/result-summary";
import { answerOf, answerStat, percentOf } from "../lib/studio-answer";
import { printed } from "../lib/studio-colors";
import { bannedIn, FOLLOWED_CHECK, FOLLOWED_DOCUMENTS, FOLLOWED_STAGE, followedJob, runDetail, runHeadline, runProblem, runStatus, runSteps, verificationOf } from "../lib/studio-copy";
import { buildValues, exampleForm, FOLLOWED_KEY, FOLLOWED_LABEL, FOLLOWED_WORDS, followedRow, followsShape, formFromValues, PLATE_TEST, rowErrorsFrom, type StudioForm } from "../lib/studio-form";
import { emptyPlate } from "../lib/studio-plate";

// Nonlinear geometry on the page (ADR-0142): the switch, the run's wording, the answer that does not scale, the curve and the chat.
// Every result here is the package's own: a clamped plate under pressure, solved linear and with its shape followed
// (`tests/fixtures/studio-followed/`), and the same plate under fifty times the pressure, where a ply reaches its limit on the way.

const fixture = (name: string) => JSON.parse(readFileSync(`tests/fixtures/studio-followed/${name}.json`, "utf8"));
const FOLLOWED = fixture("fields") as Fields, LINEAR = fixture("linear-fields") as Fields, FAILING = fixture("failing-summary") as Fields;
const plate: StudioForm = { ...exampleForm("2026-11-26"), test: PLATE_TEST, length: "200", width: "200" };
const on: StudioForm = { ...plate, ...followedRow(true) };
const coupon = exampleForm("2026-11-26");

test("the switch is a key of the form's rows: sent only for a plate with it on, and a run made with it reopens with it on", () => {
  assert.equal(followsShape(plate), false);
  assert.equal(followsShape(on), true);
  assert.equal(followsShape({ ...coupon, ...followedRow(true) }), false); // a coupon has no switch, whatever its rows hold
  assert.equal(buildValues(on)[FOLLOWED_KEY], true);
  assert.ok(!(FOLLOWED_KEY in buildValues(plate)) && !(FOLLOWED_KEY in buildValues({ ...coupon, ...followedRow(true) })));
  assert.equal(formFromValues(fixture("values"))[FOLLOWED_KEY], "yes"); // the run's own values file
  assert.ok(!formFromValues({ ...fixture("values"), nonlinear_geometry: false })[FOLLOWED_KEY]);
  assert.deepEqual(followedRow(false), { [FOLLOWED_KEY]: "" });
  assert.deepEqual(changesBetween({ form: plate, plate: emptyPlate() }, { form: on, plate: emptyPlate() }), ["Nonlinear geometry: off → on"]);
});

test("a setup the followed solve refuses is said under the switch, in the check's own words", () => {
  const checklist = { ...fixture("checklist"), state: "blocked" };
  const refusal = `${FOLLOWED_LABEL}: the mesh has 40000 elements in 8 layers, 320000 bricks, more than the 10000 a followed solve takes; a coarser mesh is followed`;
  checklist.items = checklist.items.map((item: { id: string }) => (item.id === "solver" ? { ...item, state: "fail", message: refusal, rows: [FOLLOWED_LABEL, "Element size (mm)"] } : item));
  assert.equal(rowErrorsFrom(checklist)[FOLLOWED_KEY], "The mesh has 40000 elements in 8 layers, 320000 bricks, more than the 10000 a followed solve takes; a coarser mesh is followed.");
});

test("a run with nonlinear geometry is worded as one: its own stage, no report step, and what stopped it without a program's name", () => {
  const stages = ["the setup check", "the input", "the decks", "the attempt", "our engine", "CalculiX", "the CalculiX record", FOLLOWED_STAGE, "the result", "the outputs"];
  const job = (more: Partial<JobStatus>) => ({ state: "running", stage: FOLLOWED_STAGE, stages, stages_done: [], outputs: {}, message: null, ...more }) as JobStatus;
  assert.ok(followedJob(job({})) && followedJob(job({ stage: "our engine" })) && followedJob({ documents: FOLLOWED_DOCUMENTS }));
  assert.ok(!followedJob({ stage: "our engine", stages: ["our engine", "the result"], documents: "written" }));
  assert.equal(runHeadline(job({})), "Solving with nonlinear geometry");
  assert.deepEqual(runSteps(job({})).map((s) => s.label), ["Queued", "Meshing", "Solving", "Post-processing"]); // no "Report ready"
  assert.equal(runSteps(job({})).map((s) => s.state).join(" "), "done done current waiting");
  const done = job({ state: "done", stage: "the outputs", documents: FOLLOWED_DOCUMENTS, result: "nonlinear geometry, the shape followed by CalculiX 2.21" });
  assert.equal(runSteps(done).map((s) => s.state).join(" "), "done done done done");
  assert.equal(runStatus(done, "Files"), "Done. No report is written of a run with nonlinear geometry.");
  assert.equal(runDetail(job({ stage: "our engine" })), "The linear solve comes first, as the check of the model. Nonlinear geometry follows.");
  // one solver gives this answer: said as a note, never as "verified" and never as a warning
  assert.deepEqual(verificationOf(done.result), { line: FOLLOWED_CHECK, verified: false, note: true });
  // a solve that stopped part way says how far it got, and how to go on, with no program named
  const stopped = job({ state: "stopped", message: "stopped at the followed solve: the solve with nonlinear geometry reached 50 % of the load and stopped there, the largest displacement 4.2 mm: no balance of forces was found" });
  const problem = runProblem(stopped) ?? "";
  assert.match(problem, /reached 50 % of the load and stopped there/);
  assert.match(problem, /turn nonlinear geometry off in the Analysis step/);
  for (const words of [problem, runHeadline(job({})), runStatus(done, "Files"), FOLLOWED_CHECK, ...Object.values(FOLLOWED_WORDS)]) assert.deepEqual(bannedIn(words), [], words);
});

test("a followed answer does not scale: the failure index at the applied load, and a share of the load only for a ply that reached its limit", () => {
  const holds = answerOf(FOLLOWED)!, fails = answerOf(FAILING)!;
  assert.ok(holds.followed && holds.appliedNow && !holds.earliest.fails && holds.earliest.applied === null && holds.earliest.fraction === null);
  assert.deepEqual(answerStat(FOLLOWED, printed), { fails: false, verdict: "Holds", factor: "7.956", measure: "failure index 0.1257", followed: true, outside: null,
    facts: "Tsai-Hill, ply 7 · 0°, the whole model, nonlinear geometry" });
  assert.equal(answerStat(LINEAR, printed)?.measure.startsWith("R = "), true); // a linear answer keeps its factor
  assert.ok(fails.earliest.fails && fails.earliest.criterion === "max_stress");
  assert.equal(percentOf(fails.earliest.fraction!), "78.4 %");
  assert.deepEqual(fails.earliest.between, [0.7, 0.8]);
  const said = failureLines(failureAnswer(FOLLOWED, "which ply fails first")!, printed);
  assert.equal(said.headline, "No ply fails: ply 7 (0°), top face is the closest");
  assert.match(said.loading, /^Its failure index is 0\.1257 at the applied load\. .* does not scale with the load, so no load at failure is given/);
  assert.ok(said.facts.includes("nonlinear geometry"));
  const failing = failureLines(failureAnswer(FAILING, "which ply fails first")!, printed);
  assert.equal(failing.headline, "Ply 7 (0°), top face fails first");
  assert.match(failing.loading, /^At about 78\.4 % of the applied load \(1\.176 MPa, 47080 N\), between the load levels at 70 % and 80 %\. /);
  for (const lines of [said, failing]) assert.doesNotMatch([lines.headline, lines.loading, lines.applied ?? ""].join(" "), /×|times the applied/);
  assert.match(marginNote("what is the margin", failureAnswer(FOLLOWED, "what is the margin")!, printed) ?? "", /the failure index is 0\.1257 at the applied load/);
  // the list of past analyses: the verdict at the applied load, never a multiple of it
  const answer = readJobAnswer({ basis: "whole", criterion: "tsai_hill", fails: false, factor: 7.956, ply: 7, angle: 0, face: "top", followed: true })!;
  assert.deepEqual(answerWords(answer, printed), { verdict: "Holds", loading: "the applied load", facts: ["ply 7 (0°), top face", "Tsai-Hill", "whole model", "nonlinear geometry"] });
  assert.equal(readJobAnswer({ ...answer, followed: false })?.followed, undefined);
  assert.match(summaryAnswer(FOLLOWED, "displacement", printed).lines.join(" "), /With nonlinear geometry; a linear solve of the same plate gives 3\.633 mm/);
  assert.equal(summaryAnswer(LINEAR, "displacement", printed).lines.length, 1);
});

test("the load against deflection curve is laid out from the package's levels, the linear line cut where it leaves the plot", () => {
  assert.deepEqual([0.9, 1.855, 8.4, 43, 0].map((v) => niceStep(v)), [0.5, 0.5, 5, 20, 1]);
  const followed = FOLLOWED.summary.followed!;
  const layout = curveLayout(followed, printed)!;
  assert.equal(layout.points.length, 10);
  assert.deepEqual(layout.points.map((p) => p.percent), [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]);
  assert.equal(printed(layout.points[9].value), "1.855");
  assert.equal(printed(layout.points[9].linear), "3.633");
  assert.equal(layout.xMax, 2);
  assert.deepEqual(layout.xTicks.map((t) => t.label), ["0", "0.5", "1", "1.5", "2"]);
  assert.deepEqual(layout.yTicks.map((t) => t.label), ["0 %", "25 %", "50 %", "75 %", "100 %"]);
  // the curve rises from the origin, each level further right and higher, inside the plot
  const xs = layout.points.map((p) => p.x), ys = layout.points.map((p) => p.y);
  assert.ok(xs.every((x, i) => (i === 0 ? x > layout.left : x > xs[i - 1]) && x <= layout.width - layout.right));
  assert.ok(ys.every((y, i) => (i === 0 ? y < layout.height - layout.bottom : y < ys[i - 1]) && y >= layout.top));
  assert.ok(layout.path.startsWith(`M${layout.left.toFixed(1)},${(layout.height - layout.bottom).toFixed(1)} L`));
  // the linear answer reaches 3.633 mm at the full load, past the plot's 2 mm: its line leaves at the right edge, part way up
  assert.ok(layout.linear.leaves && layout.linear.x2 === layout.width - layout.right && layout.linear.y2 > layout.top && layout.linear.y2 < layout.height - layout.bottom);
  // a linear line that stays inside ends at the full load
  const inside = curveLayout({ ...followed, curve: { ...followed.curve, linear: followed.curve.values.map((v) => 1.05 * v) } }, printed)!;
  assert.ok(!inside.linear.leaves && Math.abs(inside.linear.y2 - layout.top) < 1e-9);
  assert.equal(curveLayout({ ...followed, fractions: [] }, printed), null);
  assert.equal(curveLayout({ ...followed, curve: { ...followed.curve, values: followed.curve.values.map(() => 0) } }, printed), null);
});

const ask = (text: string, followed = false) => followedAsked(text, isQuestion(text), followed);

test("the chat reads the switch however it is named, and a question of it never sets it", () => {
  for (const text of ["turn on nonlinear geometry", "turn nonlinear geometry on", "nlgeom on", "NLGEOM=YES", "enable large deflection", "use large displacement theory",
    "make it nonlinear", "run it with nonlinear geometry", "can you turn on nlgeom?", "switch on geometric nonlinearity", "turn on non-linear geometry please",
    "trun on nonlinar geometry", "swtich on non linear geometry", "follow the shape", "include large deformations", "set nlgeom to on", "run again with nlgeom"]) assert.equal(ask(text), "on", text);
  for (const text of ["turn off nonlinear geometry", "nlgeom off", "NLGEOM=NO", "make it linear", "go back to linear", "use a linear solve", "no nlgeom", "without large deflection",
    "don't use nonlinear geometry", "disable nlgeom", "linear please", "switch back to a linear analysis", "make it linear again please"]) assert.equal(ask(text), "off", text);
  for (const text of ["is nonlinear geometry on?", "is nlgeom on", "does it use nonlinear geometry?", "was this solved with large deflection", "is it nonlinear?"]) assert.equal(ask(text), "is-on", text);
  for (const text of ["is this a linear analysis?", "is it linear"]) assert.equal(ask(text), "is-linear", text);
  for (const text of ["should I turn on nonlinear geometry?", "do i need nlgeom", "when should I use large deflection?", "do I need nonlinear geometry for this plate?"]) assert.equal(ask(text), "advice", text);
  for (const text of ["if I double the pressure does the stress double?", "does the stress scale with the load?", "is the deflection proportional to the pressure?"]) assert.equal(ask(text), "scales", text);
  // what belongs to another reader, or names something else that is linear or nonlinear
  for (const text of ["what is nonlinear geometry", "how does nonlinear geometry work", "why is the nonlinear answer smaller", "is the nonlinear answer right?",
    "is the linear elastic modulus right?", "use linear elements", "make it linear elastic", "show me the stress with nonlinear geometry", "which ply fails first with nonlinear geometry",
    "fix the left edge", "pressure of 0.03 MPa on the face", "make it 30 wide", "is the failure load proportional to the width?", "double the load"]) assert.equal(ask(text), null, text);
  // a share of the load is read only where the result holds its levels
  assert.equal(levelAsked("what is the deflection at half the load"), 0.5);
  assert.equal(levelAsked("displacement at 30 % of the load"), 0.3);
  assert.equal(levelAsked("what is the stress at half the thickness"), null);
  assert.equal(ask("what is the deflection at half the load", true), "level");
  assert.equal(ask("what is the deflection at half the load"), null);
});

test("the chat's answer sets the switch on a plate, says why not on a coupon, and answers a question from the result on the page", () => {
  const said = (text: string, form: StudioForm, fields: Fields | null = null) => followedAnswer(ask(text, Boolean(fields?.summary.followed))!, form, fields, printed, text);
  assert.deepEqual(said("turn on nonlinear geometry", plate), { title: "Nonlinear geometry is on", lines: [FOLLOWED_WORDS.on], set: true });
  assert.deepEqual(said("turn on nonlinear geometry", on), { title: "Nonlinear geometry is already on", lines: [FOLLOWED_WORDS.on], set: null });
  assert.deepEqual(said("make it linear", on), { title: "Nonlinear geometry is off", lines: [FOLLOWED_WORDS.off], set: false });
  assert.equal(said("make it linear", plate).set, null);
  assert.deepEqual(said("turn on nonlinear geometry", coupon), { title: "Not applied", lines: [FOLLOWED_WORDS.coupon], set: null, problem: true });
  assert.equal(said("is nlgeom on", on).title, "Yes, nonlinear geometry is on");
  assert.equal(said("is nlgeom on", plate).title, "No, the solve is linear");
  assert.equal(said("is it linear", on).title, "No, nonlinear geometry is on");
  assert.equal(said("is it linear", coupon).title, "Yes, the solve is linear");
  // whether it is needed: from the linear result's deflection against the thickness, both the package's
  const needed = said("do I need nonlinear geometry?", plate, LINEAR);
  assert.equal(needed.title, "Yes: it deflects 2.5 times its thickness");
  assert.match(needed.lines[0], /^Largest displacement out of its plane 3\.633 mm, thickness 1\.463 mm/);
  const small = { ...LINEAR, summary: { ...LINEAR.summary, deflection: { value: 0.2, thickness: 1.463, ratio: 0.1367, past_linear: false } } } as Fields;
  assert.equal(said("do I need nonlinear geometry?", plate, small).title, "No: it deflects 0.14 of its thickness");
  assert.equal(said("do I need nonlinear geometry?", plate).title, "When it deflects more than about half its thickness");
  assert.match(said("do I need nonlinear geometry?", on, FOLLOWED).lines[0], /^Largest displacement 1\.855 mm, 48\.93 % smaller than the 3\.633 mm of a linear solve/);
  assert.equal(said("should I use large deflection?", coupon).title, "No: not on a coupon");
  // whether the answer scales, and the deflection at a share of the load
  assert.match(said("if I double the pressure does the stress double?", on, FOLLOWED).title, /^No: /);
  assert.match(said("if I double the pressure does the stress double?", plate, LINEAR).title, /^Yes: /);
  assert.equal(said("what is the deflection at half the load", on, FOLLOWED).title, "1.265 mm at 50 % of the load");
  assert.match(said("what is the deflection at half the load", on, FOLLOWED).lines[0], /A linear solve gives 1\.816 mm there\.$/);
  assert.equal(said("what is the displacement at 45 % of the load", on, FOLLOWED).title, "No load level at 45 %");
  for (const text of ["turn on nonlinear geometry", "is nlgeom on", "do I need nonlinear geometry?", "if I double the pressure does the stress double?", "what is the deflection at half the load"]) {
    for (const [form, fields] of [[plate, null], [on, FOLLOWED], [plate, LINEAR], [coupon, null]] as [StudioForm, Fields | null][]) {
      const answer = followedAnswer(ask(text, Boolean(fields?.summary.followed)) ?? "on", form, fields, printed, text);
      assert.deepEqual(bannedIn([answer.title, ...answer.lines].join(" ")), [], text);
      assert.ok(answer.title.length <= 60, answer.title);
    }
  }
});

test("the switch is read before a model or the setup's patterns, and never on an imported model or a past run", () => {
  const state = (form: StudioForm, more: Partial<ChatState> = {}): ChatState => ({ form, readOnly: false, results: false, facts: false, api: true, modelReads: true, onPlate: form.test === PLATE_TEST,
    plates: true, plate: emptyPlate(), here: [], ready: true, step: null, about: null, thread: null, sections: true, ...more });
  assert.deepEqual(routeMessage("turn on nonlinear geometry", state(plate)), { route: "followed", ask: "on" });
  assert.deepEqual(routeMessage("turn on nonlinear geometry", state(coupon)), { route: "followed", ask: "on" });
  assert.deepEqual(routeMessage("turn on nonlinear geometry", state(plate, { readOnly: true })), { route: "read-only" });
  assert.equal(routeMessage("what is NLGEOM", state(plate)).route, "term"); // what it is stays the glossary's
  assert.deepEqual(routeMessage("what is the deflection at half the load", state(on, { results: true })), { route: "followed", ask: "level" });
  assert.equal(routeMessage("what is the deflection at half the load", state(plate, { results: true })).route, "summary"); // a linear result holds no levels
  assert.equal(routeMessage("fix the left edge", state(on)).route, "plate-edit");
});
