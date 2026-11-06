import { test } from "node:test";
import assert from "node:assert/strict";
import { KEPT, newProject, PROJECTS_KEY, projectTitle, readProjects, reduce, upsert, writeProjects, type StorageLike } from "../lib/project-store";
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
