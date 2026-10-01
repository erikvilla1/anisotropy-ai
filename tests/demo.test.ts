import test from "node:test";
import assert from "node:assert/strict";
import {
  emptyScope,
  makeReply,
  parseDataset,
  sampleCSV,
  scopeErrors,
  scopeQuestions,
  latexReport,
} from "../lib/demo";

test("sample data passes preview validation", () => {
  const result = parseDataset(sampleCSV, "example.csv", true);
  assert.equal(result.rows.length, 3);
  assert.deepEqual(result.errors, []);
});
test("malformed, empty and incomplete datasets cannot be submitted", () => {
  assert.ok(parseDataset("", "empty.csv").errors.length);
  assert.ok(
    parseDataset("coupon_id\nC-1", "missing.csv").errors.some((e) =>
      e.includes("Missing columns"),
    ),
  );
  assert.ok(
    parseDataset(sampleCSV.replace("48.2", "-1"), "negative.csv").errors.some(
      (e) => e.includes("positive number"),
    ),
  );
  assert.ok(
    parseDataset(
      sampleCSV.replace("DEMO-002", "DEMO-001"),
      "duplicate.csv",
    ).errors.some((e) => e.includes("duplicate")),
  );
});
test("checks specimen geometry and integer ply counts", () => {
  assert.ok(
    parseDataset(sampleCSV.replace("36,6,", "36,40,"), "hole.csv").errors.some(
      (e) => e.includes("less than width"),
    ),
  );
  assert.ok(
    parseDataset(
      sampleCSV.replace("16,2.08", "16.5,2.08"),
      "plies.csv",
    ).errors.some((e) => e.includes("integer")),
  );
  assert.ok(
    parseDataset(
      sampleCSV.replace("25,0,48.2", "25,2,48.2"),
      "unnotched.csv",
    ).errors.some((e) => e.includes("hole_d_mm = 0")),
  );
});
test("handles quoted CSV fields, whitespace and UTF-8 BOM", () => {
  const result = parseDataset(
    "\uFEFF" + sampleCSV.replace("DEMO-001", '"COUPON, 001"'),
    "quoted.csv",
  );
  assert.equal(result.rows[0].coupon_id, "COUPON, 001");
  assert.deepEqual(result.errors, []);
});
test("scope retains user inputs across follow-ups without inventing results", () => {
  const first = makeReply(
    "Scope a carbon epoxy D5766 coupon, 250 x 36 mm, 20 kN",
    emptyScope,
  );
  const next = makeReply("Use a factor of safety of 1.5", first.scope);
  assert.equal(next.scope.test_standard, "ASTM D5766");
  assert.equal(next.scope.width_mm, 36);
  assert.equal(next.scope.length_mm, 250);
  assert.equal(next.scope.applied_load_kN, 20);
  assert.equal(next.scope.safety_factor, 1.5);
  assert.equal(emptyScope.width_mm, null);
  assert.ok(!("failure_load" in next.scope));
});
test("chooses response types from the question", () => {
  assert.equal(makeReply("Compare D3039 and D5766", emptyScope).kind, "table");
  assert.equal(
    makeReply("What test data should I upload?", emptyScope).kind,
    "checklist",
  );
  assert.equal(makeReply("Give me JSON", emptyScope).kind, "json");
  assert.equal(makeReply("What is Anisotropy AI?", emptyScope).kind, "overview");
});
test("comparing standards does not replace the chosen coupon type", () => {
  const scoped = makeReply("Scope a D5766 coupon", emptyScope);
  const compared = makeReply("Compare D3039 and D5766", scoped.scope);
  assert.equal(compared.scope.test_standard, "ASTM D5766");
});
test("captures expanded geometry, layup and boundary inputs across follow-ups", () => {
  const first = makeReply(
    "Carbon epoxy D5766, 250 x 36 x 2.08 mm, 6 mm hole, 16 plies, [45/-45/0/90]2s",
    emptyScope,
  ).scope;
  assert.equal(first.length_mm, 250);
  assert.equal(first.width_mm, 36);
  assert.equal(first.thickness_mm, 2.08);
  assert.equal(first.hole_diameter_mm, 6);
  assert.equal(first.ply_count, 16);
  assert.equal(first.layup, "[45/-45/0/90]2s");
  const next = makeReply(
    "20 kN, factor of safety 1.5, allowed angles: 0, ±45, 90; clamped at one end; room temperature dry",
    first,
  ).scope;
  assert.equal(next.allowed_angles, "0, ±45, 90");
  assert.ok(next.boundary_conditions);
  assert.ok(next.environment);
  assert.deepEqual(scopeQuestions(next), []);
  assert.deepEqual(scopeErrors(next), []);
});
test("rejects invalid draft geometry and escapes LaTeX text", () => {
  assert.ok(
    scopeErrors({ ...emptyScope, width_mm: 10, hole_diameter_mm: 12 }).length,
  );
  assert.ok(scopeErrors({ ...emptyScope, ply_count: 4.5 }).length);
  assert.ok(
    scopeErrors({
      ...emptyScope,
      test_standard: "ASTM D5766",
      hole_diameter_mm: 0,
    }).length,
  );
  const report = latexReport({
    ...emptyScope,
    material: "A&B_1% \\input{private}",
  });
  assert.ok(report.includes("A\\&B\\_1\\%"));
  assert.ok(!report.includes("\\input{private}"));
  assert.ok(report.includes("No engineering conclusion is available"));
});
