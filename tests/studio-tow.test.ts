import { test } from "node:test";
import assert from "node:assert/strict";
import { newProject, projectOfRecord, readProjects, reduce, uploadOf, writeProjects, type CouponProject } from "../lib/project-store";
import { towTest, type ProjectRecord } from "../lib/studio-api";
import { readMessage } from "../lib/studio-chat";
import { blankForm, fieldByKey, FORM_VERSION, mergeRows, NO_STANDARD, standardsFor, withTest, wordsFor } from "../lib/studio-form";
import {
  failureCodeWords, nextSpecimen, pastedSpecimens, specimenFields, TOW_PANELS, TOW_TEST, towDefaults, towFields, towPanelState, towRowErrors, towValues,
} from "../lib/studio-tow";

/** The fibre tow test in the studio (ADR-0074): offered on the coupon form's Test list, its own rows and specimens, the values object the API
 * reads, the checklist's rows mapped back, and the project keeping the specimens. The page computes nothing: no number is checked here. */

test("the tow test is on the coupon form's Test list and has its own standard", () => {
  assert.ok(fieldByKey.test.words.includes(TOW_TEST));
  assert.deepEqual(standardsFor(TOW_TEST).map((p) => p.designation), ["ASTM D4018-23"]);
  const form = { ...blankForm(), test: TOW_TEST };
  assert.deepEqual(wordsFor(fieldByKey.standard, form), [NO_STANDARD, "ASTM D4018-23"]);
  // a coupon's standard goes back to none when the tow is picked, and the tow's when a coupon test is
  assert.equal(withTest({ ...blankForm(), test: "unnotched tension", standard: "ASTM D3039/D3039M-17" }, TOW_TEST).form.standard, NO_STANDARD);
  const back = withTest({ ...form, standard: "ASTM D4018-23" }, "unnotched tension");
  assert.equal(back.form.standard, NO_STANDARD);
  assert.match(back.note, /covers fibre tow tension, not unnotched tension/);
});

test("every tow row has a panel and the rows carry the standard's units, no Units row", () => {
  const panelled = TOW_PANELS.flatMap((p) => p.keys);
  for (const field of towFields) {
    assert.equal(panelled.filter((k) => k === field.key).length, 1, `${field.key} belongs to one panel`);
    assert.equal(field.unit, null, `${field.key} has no unit kind`);
  }
  assert.ok(towFields.some((f) => f.label === "Gauge length (mm)") && towFields.some((f) => f.label === "Measured density (g/cm³)"));
  assert.deepEqual(specimenFields.map((f) => f.key), ["id", "max_force", "force_lower", "force_upper", "failure_code", "status", "note"]);
});

test("picking the tow adds its rows at their defaults and never overwrites a typed row", () => {
  const form = { ...blankForm(), test: TOW_TEST };
  const added = towDefaults(form);
  assert.equal(added.bundles, "1");
  assert.equal(added.fibre, "");
  assert.deepEqual(towDefaults({ ...form, ...added }), {});
  assert.equal(towDefaults({ ...form, bundles: "3" }).bundles, undefined);
});

test("the values object: shared rows and the tow's, numbers parsed, blanks left out, specimens typed, no Units row", () => {
  const form = { ...blankForm(), ...towDefaults(blankForm()), test: TOW_TEST, standard: "ASTM D4018-23", filled_by: "A. Tester", date: "2026-11-09",
    fibre: "12K carbon", fibre_type: "carbon", mul: "0.800", fibre_density: "1.80", density_sample: "desized", tow_gauge_length: "150", failure_strain: "21000",
    speed: "ten" };
  const values = towValues(form, [{ ...nextSpecimen([]), max_force: "2150", force_lower: "", failure_code: "LGM" }]);
  assert.equal(values.form_version, FORM_VERSION);
  assert.equal(values.test, TOW_TEST);
  assert.equal(values.mul, 0.8);
  assert.equal(values.bundles, 1);
  assert.equal(values.speed, "ten"); // left as text: the API refuses it by row
  assert.equal(values.units, undefined);
  assert.equal(values.length, undefined); // a coupon's row is not sent
  assert.equal(values.notes, undefined);
  assert.deepEqual(values.specimens, [{ id: "1", max_force: 2150, failure_code: "LGM", status: "valid" }]);
});

test("specimens are numbered past the largest and pasted from a spreadsheet", () => {
  assert.equal(nextSpecimen([{ id: "1" }, { id: "4" }, { id: "x" }]).id, "5");
  assert.equal(nextSpecimen([]).status, "valid");
  const rows = pastedSpecimens("7\t2150\t101.5\t610.2\tLGM\t\t\n8,1650,,,GAT,rejected,slipped\n\n");
  assert.equal(rows.length, 2);
  assert.deepEqual(rows[0], { id: "7", max_force: "2150", force_lower: "101.5", force_upper: "610.2", failure_code: "LGM", status: "valid", note: "" });
  assert.equal(rows[1].status, "rejected");
  assert.equal(rows[1].note, "slipped");
});

test("the checklist's rows come back to the tow's rows and panels", () => {
  const checklist = {
    items: [
      { id: "identity", label: "Who and which fibre", state: "missing" as const, message: "Fibre: required", rows: ["Fibre", "Filled in by"] },
      { id: "test", label: "Tensile set-up", state: "fail" as const, message: "Gauge length (mm): a number is needed", rows: ["Gauge length (mm)"] },
      { id: "specimens", label: "Specimens tested", state: "missing" as const, message: "Specimens: required", rows: ["Specimens"] },
      { id: "standard", label: "Test standard", state: "warn" as const, message: "1 deviation", rows: [] },
    ],
    designation: null, coupon_exists: false, attempts: 0, state: "blocked" as const, problems: [],
  };
  assert.deepEqual(towRowErrors(checklist), { fibre: "Fibre: required", filled_by: "Fibre: required", tow_gauge_length: "Gauge length (mm): a number is needed",
    specimens: "Specimens: required" });
  assert.equal(towPanelState("tow-fibre", checklist), "missing");
  assert.equal(towPanelState("tow-project", checklist), "warn");
  assert.equal(towPanelState("tow-calculate", checklist), "none");
  assert.equal(towPanelState("tow-fibre", null), "none");
});

test("a failure code reads in words by Fig. 1's letters", () => {
  assert.equal(failureCodeWords("lgm"), "lateral, gauge, middle");
  assert.equal(failureCodeWords("GAT"), "grip or tab, at the grip or tab, top");
  assert.equal(failureCodeWords("QGM"), null);
  assert.equal(failureCodeWords("LG"), null);
});

test("the project keeps the specimens, in this browser and on the server", () => {
  const project = reduce(newProject(blankForm(), "2026-11-09T00:00:00Z", "p1"), { type: "specimens", specimens: [{ id: "1", max_force: "2150" }] });
  assert.deepEqual(project.specimens, [{ id: "1", max_force: "2150" }]);
  const store = new Map<string, string>();
  const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => { store.set(k, v); } };
  writeProjects([project], storage);
  assert.deepEqual((readProjects(storage)[0] as CouponProject).specimens, [{ id: "1", max_force: "2150" }]);
  // a project kept before the tow test has no specimens: it reads with none
  store.set("anisotropy.projects.v1", JSON.stringify([{ ...project, specimens: undefined }]));
  assert.deepEqual((readProjects(storage)[0] as CouponProject).specimens, []);
  const upload = uploadOf(project);
  assert.deepEqual(upload.content.specimens, [{ id: "1", max_force: "2150" }]);
  assert.equal(uploadOf(newProject()).content.specimens, undefined); // a coupon's upload is as it was
  const record: ProjectRecord = { id: "4f1c2e3d-5a6b-4c7d-8e9f-0a1b2c3d4e5f", kind: "fea", name: "tow", actor: "studio", user_email: null,
    content: { form: { test: TOW_TEST }, plate: {}, specimens: [{ id: "1", max_force: "2150", bad: 3 }, "nonsense"] }, form_version: "0.8", units: null,
    designation: null, last_check_run_id: null, created_at: "2026-11-09T00:00:00Z", updated_at: "2026-11-09T00:00:00Z" } as unknown as ProjectRecord;
  const read = projectOfRecord(record) as CouponProject;
  assert.deepEqual(read.specimens, [{ id: "1", max_force: "2150" }]);
});

test("the assistant reads a tow and D4018 and hands over to the panels' rows", () => {
  const read = readMessage("a T700 tow test to ASTM D4018");
  assert.equal(read.rows.test, TOW_TEST);
  assert.equal(read.rows.standard, "ASTM D4018-23");
  const merged = mergeRows({ ...blankForm(), test: "unnotched tension", standard: "ASTM D3039/D3039M-17" }, read.rows);
  assert.equal(merged.test, TOW_TEST);
  assert.equal(merged.standard, "ASTM D4018-23");
  assert.equal(readMessage("unnotched tension, 250 by 25 mm").rows.test, "unnotched tension");
});

test("the tow record goes to POST /v1/tow-tests with the project it belongs to", async () => {
  const calls: { url: string; init: RequestInit }[] = [];
  const original = globalThis.fetch;
  const checklist = { items: [], designation: null, coupon_exists: false, attempts: 0, state: "ready", problems: [] };
  globalThis.fetch = (async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return new Response(JSON.stringify({ run_id: "r1", state: "ready", checklist, result: { specimens: [], strength: null } }), { status: 200, headers: { "Content-Type": "application/json" } });
  }) as typeof fetch;
  try {
    const answer = await towTest("http://api.test/", { test: TOW_TEST }, undefined, "4f1c2e3d-5a6b-4c7d-8e9f-0a1b2c3d4e5f");
    assert.equal(calls[0].url, "http://api.test/v1/tow-tests");
    assert.deepEqual(JSON.parse(calls[0].init.body as string), { values: { test: TOW_TEST }, project_id: "4f1c2e3d-5a6b-4c7d-8e9f-0a1b2c3d4e5f" });
    assert.equal(answer.run_id, "r1");
    assert.equal(answer.state, "ready");
    assert.ok(answer.result);
  } finally {
    globalThis.fetch = original;
  }
});
