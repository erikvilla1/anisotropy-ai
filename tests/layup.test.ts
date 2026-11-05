import test from "node:test";
import assert from "node:assert/strict";
import { expandLayup, layupText, MAX_PLIES } from "../lib/layup";

// Notation only (ADR-0001): the reader is the coupon chat's, plus the mirror an s asks for, bottom face first (ADR-0004).

test("a symmetric layup mirrors its half, a plain one is listed as written, both bottom first", () => {
  assert.deepEqual(expandLayup("[45/-45/0/90]s").layup, { angles: [45, -45, 0, 90, 90, 0, -45, 45], symmetric: true });
  assert.deepEqual(expandLayup("[0/45/-45/90]").layup, { angles: [0, 45, -45, 90], symmetric: false });
  assert.deepEqual(expandLayup("0/90").layup, { angles: [0, 90], symmetric: false });
  assert.deepEqual(expandLayup(" [±45]2 ").layup, { angles: [45, -45, 45, -45], symmetric: false });
  assert.deepEqual(expandLayup("[0_2/90]s").layup?.angles, [0, 0, 90, 90, 0, 0]);
  assert.equal(expandLayup("[0]").layup?.angles.length, 1);
});

test("what cannot be read is an error, never a guess", () => {
  for (const text of ["", "   ", "[abc]", "[45/-45/0/90]x", "[0/ninety]"]) {
    const read = expandLayup(text);
    assert.equal(read.layup, undefined, text);
    assert.ok(read.error && read.error.length > 10, text);
  }
});

test("a stack past the form's limit is refused and the error names the limit", () => {
  const read = expandLayup(`[0_${MAX_PLIES + 1}]`);
  assert.equal(read.layup, undefined);
  assert.match(read.error!, new RegExp(`${MAX_PLIES}`));
  assert.equal(expandLayup(`[0_${MAX_PLIES}]s`).layup?.angles.length, 2 * MAX_PLIES);
});

test("the text of a stack lists its angles", () => {
  assert.equal(layupText([45, -45, 0]), "[45/-45/0]");
});
