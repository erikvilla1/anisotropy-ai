import { test } from "node:test";
import assert from "node:assert/strict";
import {
  couponProjects, isUuid, KEPT, laminateProjects, mergeProjects, newLaminateProject, newProject, projectOfRecord, PROJECTS_KEY, projectTitle, readProjects, reduce,
  reduceLaminate, uploadOf, upsert, writeProjects, type StorageLike,
} from "../lib/project-store";
import type { ProjectRecord } from "../lib/studio-api";
import { blankDraft } from "../lib/laminate-chat";
import { blankForm } from "../lib/studio-form";

function memory(): StorageLike & { map: Map<string, string> } {
  const map = new Map<string, string>();
  return { map, getItem: (k) => map.get(k) ?? null, setItem: (k, v) => { map.set(k, v); } };
}

test("a new project is a blank coupon with no name, and the reducer stamps every change", () => {
  const project = newProject(blankForm(), "2026-11-06T10:00:00.000Z", "p1");
  assert.equal(project.kind, "fea");
  assert.equal(projectTitle(project), "Untitled coupon");
  assert.deepEqual(project.plate, { supports: [], loads: [], regions: [] });
  const named = reduce(project, { type: "rename", name: "OHT study" }, "2026-11-06T10:01:00.000Z");
  assert.equal(projectTitle(named), "OHT study");
  assert.equal(named.updated, "2026-11-06T10:01:00.000Z");
  const edited = reduce(named, { type: "form", form: { ...named.form, length: "250" } }, "2026-11-06T10:02:00.000Z");
  assert.equal(edited.form.length, "250");
  assert.equal(edited.name, "OHT study"); // a form edit keeps the name
  const plated = reduce(edited, { type: "plate", plate: { supports: [{ region: "Edge-Left", dofs: [1, 2], value: "0" }], loads: [], regions: [] } });
  assert.equal(plated.plate.supports.length, 1);
  assert.equal(reduce(plated, { type: "replace", project }).id, "p1");
});

test("projects are kept newest first under one key, read back whole, and storage trouble is not an error", () => {
  const storage = memory();
  assert.deepEqual(readProjects(storage), []);
  const a = newProject(blankForm(), "2026-11-06T10:00:00.000Z", "a");
  const b = newProject(blankForm(), "2026-11-06T11:00:00.000Z", "b");
  assert.ok(writeProjects(upsert(upsert([], a), b), storage));
  assert.deepEqual(readProjects(storage).map((p) => p.id), ["b", "a"]);
  const again = upsert(readProjects(storage), { ...a, name: "renamed" });
  assert.deepEqual(again.map((p) => p.id), ["a", "b"]); // the touched project moves to the front, once
  const many = Array.from({ length: KEPT + 5 }, (_, i) => newProject(blankForm(), "2026-11-06T10:00:00.000Z", `p${i}`)).reduce(upsert, [] as ReturnType<typeof readProjects>);
  assert.equal(many.length, KEPT);
  storage.map.set(PROJECTS_KEY, "{not json");
  assert.deepEqual(readProjects(storage), []);
  storage.map.set(PROJECTS_KEY, JSON.stringify([{ id: "x" }, b]));
  assert.deepEqual(readProjects(storage).map((p) => p.id), ["b"]); // a row without the shape is dropped, the rest kept
  const blocked: StorageLike = { getItem: () => { throw new Error("blocked"); }, setItem: () => { throw new Error("blocked"); } };
  assert.deepEqual(readProjects(blocked), []);
  assert.equal(writeProjects([a], blocked), false);
  assert.deepEqual(readProjects(null), []);
});

test("a laminate project keeps the draft of a problem beside the coupons, each kind picked out by its own workspace (ADR-0062, part 5)", () => {
  const storage = memory();
  const coupon = newProject(blankForm(), "2026-11-06T10:00:00.000Z", "c");
  const laminate = newLaminateProject(blankDraft(), "2026-11-06T11:00:00.000Z", "l");
  assert.equal(laminate.kind, "laminate");
  assert.equal(projectTitle(laminate), "Untitled laminate");
  const stated = reduceLaminate(laminate, { type: "draft", draft: { ...laminate.draft, system: "SI" } }, "2026-11-06T11:01:00.000Z");
  assert.equal(stated.draft.system, "SI");
  assert.equal(stated.updated, "2026-11-06T11:01:00.000Z");
  assert.equal(reduceLaminate(stated, { type: "rename", name: "ABD check" }).name, "ABD check");
  assert.ok(writeProjects(upsert(upsert([], coupon), stated), storage));
  const kept = readProjects(storage);
  assert.deepEqual(kept.map((p) => `${p.kind}:${p.id}`), ["laminate:l", "fea:c"]);
  assert.deepEqual(couponProjects(kept).map((p) => p.id), ["c"]);
  assert.deepEqual(laminateProjects(kept).map((p) => p.id), ["l"]);
  storage.map.set(PROJECTS_KEY, JSON.stringify([{ ...stated, draft: { system: "US" } }])); // a draft kept by an older page: the missing rows are blank, not absent
  const older = laminateProjects(readProjects(storage))[0];
  assert.deepEqual(older.draft, { ...blankDraft(), system: "US" });
});

test("a project goes to the server as the page states it and comes back whole; the later change wins when both sides hold it (ADR-0062, part 6)", () => {
  const coupon = reduce(newProject(blankForm(), "2026-11-06T10:00:00.000Z", "4f1c2e3d-5a6b-4c7d-8e9f-0a1b2c3d4e5f"), { type: "form", form: { ...blankForm(), length: "250", units: "mm-MPa" } }, "2026-11-06T10:01:00.000Z");
  const up = uploadOf(coupon);
  assert.deepEqual([up.kind, up.form_version, up.units], ["fea", "0.6", "mm-MPa"]);
  assert.deepEqual(up.content, { form: coupon.form, plate: coupon.plate });
  const laminate = newLaminateProject({ ...blankDraft(), system: "US" }, "2026-11-06T11:00:00.000Z", "5f1c2e3d-5a6b-4c7d-8e9f-0a1b2c3d4e5f");
  assert.deepEqual([uploadOf(laminate).kind, uploadOf(laminate).units, uploadOf(laminate).form_version], ["laminate", "US", null]);
  const record = (project: typeof coupon | typeof laminate, updated: string): ProjectRecord => ({
    id: project.id, ...uploadOf(project), designation: null, last_check_run_id: null, created_at: "2026-11-06T10:00:00+00:00", updated_at: updated, jobs: [],
  });
  const back = projectOfRecord(record(coupon, "2026-11-06T10:05:00+00:00"));
  assert.ok(back && back.kind === "fea");
  assert.deepEqual(back.form, coupon.form);
  assert.deepEqual(back.plate, coupon.plate);
  assert.equal(back.updated, "2026-11-06T10:05:00.000Z"); // the server's stamp, in this page's form
  const lam = projectOfRecord({ ...record(laminate, "2026-11-06T11:00:00+00:00"), content: { draft: { system: "SI" } } });
  assert.ok(lam && lam.kind === "laminate");
  assert.deepEqual(lam.draft, { ...blankDraft(), system: "SI" }); // an older draft is read whole
  assert.equal(projectOfRecord({ ...record(coupon, "x"), content: { rows: 1 } }), null); // not what this page writes
  const merged = mergeProjects([coupon, laminate], [projectOfRecord(record(coupon, "2026-11-06T10:05:00+00:00"))!, { ...laminate, id: "other", updated: "2026-11-06T09:00:00.000Z" }]);
  assert.deepEqual(merged.map((p) => `${p.id.slice(0, 4)}@${p.updated}`), ["5f1c@2026-11-06T11:00:00.000Z", "4f1c@2026-11-06T10:05:00.000Z", "othe@2026-11-06T09:00:00.000Z"]);
  const localNewer = mergeProjects([{ ...coupon, updated: "2026-11-06T12:00:00.000Z", name: "mine" }], [projectOfRecord(record(coupon, "2026-11-06T10:05:00+00:00"))!]);
  assert.equal(localNewer[0].name, "mine"); // the browser's edit after the server's copy stands
  assert.ok(isUuid(coupon.id) && !isUuid("m3kz9-abc"));
});
