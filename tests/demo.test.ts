import test from "node:test";
import assert from "node:assert/strict";
import { parseDataset, sampleCSV } from "../lib/demo";

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
    ).errors.some((e) => e.includes("Duplicate coupon ID")),
  );
});
test("every row error starts its sentence with a capital and has no aside in brackets", () => {
  const broken = sampleCSV
    .replace("DEMO-002", "DEMO-001")
    .replace("48.2", "-1")
    .replace("16,2.08", "16.5,2.08")
    .replace("25,0,", "25,2,")
    .replace("D5766", "D9999");
  const rows = parseDataset(broken, "broken.csv").errors.filter((e) => /^Row \d+: /.test(e));
  assert.ok(rows.length >= 4);
  for (const e of rows) {
    assert.match(e, /^Row \d+: [A-Z0-9]/, e);
    assert.doesNotMatch(e, /\(D\d{4}\)/, e);
  }
});
test("checks specimen geometry and integer ply counts", () => {
  assert.ok(
    parseDataset(sampleCSV.replace("36,6,", "36,40,"), "hole.csv").errors.some(
      (e) => e.includes("less than the width"),
    ),
  );
  assert.ok(
    parseDataset(
      sampleCSV.replace("16,2.08", "16.5,2.08"),
      "plies.csv",
    ).errors.some((e) => e.includes("whole number")),
  );
  assert.ok(
    parseDataset(
      sampleCSV.replace("25,0,48.2", "25,2,48.2"),
      "unnotched.csv",
    ).errors.some((e) => e.includes("hole diameter of 0")),
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
