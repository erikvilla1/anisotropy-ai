import { test } from "node:test";
import assert from "node:assert/strict";
import { statSync } from "node:fs";
import { join } from "node:path";
import { LENS_CAPTIONS, LENS_TIMING, lensModelAt } from "../lib/hero-lens";

// The hero lens (ADR-0071): the loop's timing as scripts/hero-lens.ts wrote it, and the caption it picks.

test("the lens's loop shows each model in turn, end to end, and every model has a caption", () => {
  const { duration, segments } = LENS_TIMING;
  assert.deepEqual(segments.map((s) => s.id), ["tension", "bending", "plate"]);
  assert.equal(segments[0].start, 0);
  for (let i = 1; i < segments.length; i++) assert.equal(segments[i].start, segments[i - 1].end, `${segments[i].id} starts where the last ends`);
  for (const s of segments) {
    assert.ok(s.end - s.start >= 3, `${s.id} stays long enough to read its caption`);
    assert.ok(LENS_CAPTIONS[s.id], `${s.id} has a caption`);
  }
  assert.ok(segments.at(-1)!.end < duration, "the loop's end belongs to the first model, which it fades back to");
});

test("the caption follows the loop's time, and wraps to the first model at the end", () => {
  assert.equal(lensModelAt(0), "tension");
  assert.equal(lensModelAt(6.5), "bending");
  assert.equal(lensModelAt(11.5), "plate");
  assert.equal(lensModelAt(LENS_TIMING.duration - 0.1), "tension");
});

test("the recording and its poster are committed and stay small", () => {
  const dir = join(__dirname, "..", "public", "assets", "hero-lens");
  assert.ok(statSync(join(dir, "lens.mp4")).size < 1_500_000, "lens.mp4 under 1.5 MB");
  assert.ok(statSync(join(dir, "lens.jpg")).size < 100_000, "lens.jpg under 100 kB");
});
