import test from "node:test";
import assert from "node:assert/strict";
import { BESIDE_TALL, BESIDE_WIDE, boxOf, fitInto, roomAbove, roomBeside } from "../components/home/product-demo-fit";

// Where the demo's wing stands (ADR-0098 amendments 3 and 4): the room a beat's words leave, beside them or over them, and
// the fit into it.

const EYE = 12;
/** A slab's eight corners, 2000 by 600 by 300 mm about its middle, turned a little so that its ends differ in depth. */
const slab = (() => {
  const points: number[] = [];
  const turn = 0.9;
  for (const x of [-1000, 1000]) for (const y of [-300, 300]) for (const z of [-150, 150]) points.push(x * Math.cos(turn) + z * Math.sin(turn), y, -x * Math.sin(turn) + z * Math.cos(turn));
  return points;
})();

test("the room beside the words is at most about half the stage wide, nearer the words than the far edge, and mirrors", () => {
  // At 1873 px the words' column is 80 px in and 430 px wide (app/home-demo.css) and the space they leave starts 64 px past
  // it, at 574, and ends 48 px from the far edge.
  const right = roomBeside(1, 1873, 866);
  assert.ok(Math.abs(right.right - right.left - BESIDE_WIDE * 1873) < 1e-9);
  assert.ok(right.left > 574 && right.right < 1873 - 48);
  assert.ok(right.left - 574 < 1873 - 48 - right.right, "nearer the words than the far edge");
  assert.ok(Math.abs(right.bottom - right.top - BESIDE_TALL * 866) < 1e-9);
  assert.ok(right.top > 0 && right.bottom < 866);
  // The other side mirrors it, and between the two the room slides across the stage, as wide as ever.
  const left = roomBeside(-1, 1873, 866);
  assert.ok(Math.abs(left.left - (1873 - right.right)) < 1e-9 && Math.abs(left.right - (1873 - right.left)) < 1e-9);
  const middle = roomBeside(0, 1873, 866);
  assert.ok(Math.abs(middle.left + middle.right - 1873) < 1e-9);
  assert.ok(Math.abs(middle.right - middle.left - (left.right - left.left)) < 1e-9);
  // On the narrowest stage that plays the room keeps inside the space the words leave, which starts a gap past the column,
  // and is still wider than the column.
  const narrow = roomBeside(1, 1024, 600);
  assert.ok(narrow.left >= 51.2 + 0.34 * 1024 + 36 - 1e-9);
  assert.ok(narrow.right <= 1024 - 0.6 * 51.2 + 1e-9);
  assert.ok(narrow.right - narrow.left > 0.34 * 1024);
});

test("the room over the words is in the stage's middle and ends above where the words begin", () => {
  const room = roomAbove(1440, 900, 500);
  assert.ok(Math.abs(room.left + room.right - 1440) < 1e-9);
  assert.ok(Math.abs(room.right - room.left - 0.66 * 1440) < 1e-9);
  assert.ok(Math.abs(room.top - 72) < 1e-9 && Math.abs(room.bottom - (500 - 63)) < 1e-9);
  // On a wide, low stage its width follows the height, so the wing does not outgrow the window.
  const low = roomAbove(1873, 600, 380);
  assert.ok(Math.abs(low.right - low.left - 0.66 * 1.6 * 600) < 1e-9);
  // With no words on the stage the room is the stage itself, less a margin; and the room over words never closes up.
  assert.deepEqual(roomAbove(1000, 500), { left: 80, right: 920, top: 50, bottom: 420 });
  assert.ok(roomAbove(1440, 900, 120).bottom - roomAbove(1440, 900, 120).top >= 0.2 * 900 - 1e-9);
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
