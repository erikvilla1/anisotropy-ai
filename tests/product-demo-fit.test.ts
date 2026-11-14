import test from "node:test";
import assert from "node:assert/strict";
import { boxOf, fitInto, roomBeside } from "../components/home/product-demo-fit";

// Where the demo's wing stands beside a beat's words (ADR-0098 amendment 3): the room the words leave and the fit into it.

const EYE = 12;
/** A slab's eight corners, 2000 by 600 by 300 mm about its middle, turned a little so that its ends differ in depth. */
const slab = (() => {
  const points: number[] = [];
  const turn = 0.9;
  for (const x of [-1000, 1000]) for (const y of [-300, 300]) for (const z of [-150, 150]) points.push(x * Math.cos(turn) + z * Math.sin(turn), y, -x * Math.sin(turn) + z * Math.cos(turn));
  return points;
})();

test("the room beside the words starts a gap past their column and ends near the stage's far edge", () => {
  // At 1873 px the column is 80 px in and 430 px wide (app/home-demo.css), so the room starts 64 px past 510.
  assert.deepEqual(roomBeside(true, 1873, 866), { left: 574, right: 1873 - 48, top: 0.12 * 866, bottom: 0.9 * 866 });
  // The other side mirrors it.
  const left = roomBeside(false, 1873, 866);
  assert.equal(left.left, 48);
  assert.equal(left.right, 1873 - 574);
  // On the narrowest stage that plays, the column is a share of the stage and the room is still wider than the column.
  const narrow = roomBeside(true, 1024, 600);
  assert.ok(Math.abs(narrow.left - (51.2 + 0.34 * 1024 + 36)) < 1e-9);
  assert.ok(narrow.right - narrow.left > 0.34 * 1024);
});

test("the wing is sized to just fill its room, standing in the room's middle and nowhere outside it", () => {
  for (const room of [{ left: 0.2, right: 5.4, bottom: -2.1, top: 2.0 }, { left: -5.4, right: -0.2, bottom: -1.0, top: 1.4 }, { left: -1, right: 1, bottom: -2.4, top: 2.4 }]) {
    const fit = fitInto(slab, 8, room, EYE);
    const box = boxOf(slab, 8, fit.unit, fit.x, fit.y, EYE);
    // Inside the room, to a hair.
    assert.ok(box.left >= room.left - 1e-3 && box.right <= room.right + 1e-3 && box.bottom >= room.bottom - 1e-3 && box.top <= room.top + 1e-3, JSON.stringify({ room, box }));
    // It fills the room one way or the other.
    const across = (box.right - box.left) / (room.right - room.left), up = (box.top - box.bottom) / (room.top - room.bottom);
    assert.ok(Math.abs(Math.max(across, up) - 1) < 2e-3, `${across} ${up}`);
    // And stands in its middle.
    assert.ok(Math.abs(box.left + box.right - room.left - room.right) < 4e-3 && Math.abs(box.bottom + box.top - room.bottom - room.top) < 4e-3);
  }
});

test("a point nearer the eye is drawn larger", () => {
  const far = boxOf([1, 1, -2, -1, -1, -2], 2, 1, 0, 0, EYE);
  const near = boxOf([1, 1, 2, -1, -1, 2], 2, 1, 0, 0, EYE);
  assert.ok(near.right - near.left > far.right - far.left);
  assert.ok(Math.abs(boxOf([1, 1, 0, -1, -1, 0], 2, 1, 0, 0, EYE).right - 1) < 1e-12);
});
