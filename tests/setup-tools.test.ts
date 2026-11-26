import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { readPlateEdit } from "../lib/plate-edits";
import type { StudioForm } from "../lib/studio-form";
import type { PlateLists } from "../lib/studio-plate";
import { workspaceValues } from "../lib/tension-screen";

// The page and the API's setup tools agree (ADR-0143): `tests/fixtures/setup-tools/plate-setup.json` holds what the page writes for three
// plates and what its sentence reader makes of fourteen sentences. This test holds the page to it; `api/tests/test_setup_tools.py` holds
// the API's typed changes to the same file, so a change on one side that the other does not follow fails one of the two.
type Case = { name: string; form: StudioForm; plate: PlateLists; values: Record<string, unknown> };
type Edit = { text: string; changes: unknown[]; done: string[]; after: PlateLists };
type Coupon = { name: string; form: StudioForm; values: Record<string, unknown> };
const FIXTURE = JSON.parse(readFileSync("tests/fixtures/setup-tools/plate-setup.json", "utf8")) as {
  values: Case[]; edits: { form: StudioForm; start: PlateLists; cases: Edit[] }; coupons: Coupon[] };
const NO_LISTS: PlateLists = { supports: [], loads: [], regions: [] };

test("a plate's values are what the page writes, rows and lists alike", () => {
  assert.equal(FIXTURE.values.length, 3);
  for (const c of FIXTURE.values) assert.deepEqual(workspaceValues(c.form, c.plate, false), c.values, c.name);
});

test("a coupon's values are what the page sends for a run, which the planner's run sends too (ADR-0144)", () => {
  // `api/tests/test_planner.py` holds `planner.run_values` to the same cases
  assert.equal(FIXTURE.coupons.length, 3);
  for (const c of FIXTURE.coupons) assert.deepEqual(workspaceValues(c.form, NO_LISTS, false), c.values, c.name);
});

test("each sentence the page reads makes the change the API's typed change makes", () => {
  const { form, start, cases } = FIXTURE.edits;
  assert.equal(cases.length, 14);
  for (const c of cases) {
    const read = readPlateEdit(c.text, form, start);
    assert.ok(read && !read.notes.length, `the page reads “${c.text}”`);
    assert.deepEqual(read.done, c.done, c.text);
    assert.deepEqual(read.lists, c.after, c.text);
    assert.ok(c.changes.length > 0, `“${c.text}” names its typed change`);
  }
});
