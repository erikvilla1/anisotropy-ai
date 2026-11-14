/** Where the demo's wing stands when a beat's words are set at one side of the stage (ADR-0098 amendment 3): the room the
 * words leave, and the size and place at which the wing just fills it. Arithmetic only, so it can be tested without a
 * graphics card; the view (product-demo-scene.tsx) hands it the wing's nodes as the pose has turned them. */

export type Box = { left: number; right: number; bottom: number; top: number };

/** The box that points take on the screen, in the world's units at the model's distance. The points are already turned as
 * the wing is and are in millimetres about the wing's middle, three numbers a point; `unit` is the world's units a
 * millimetre, `x` and `y` where the middle stands, and `eye` how far the camera is from the model's plane. A point nearer the
 * eye is drawn larger, as the camera draws it. */
export function boxOf(points: ArrayLike<number>, count: number, unit: number, x: number, y: number, eye: number): Box {
  const box = { left: Infinity, right: -Infinity, bottom: Infinity, top: -Infinity };
  for (let index = 0; index < count * 3; index += 3) {
    const near = eye / (eye - unit * points[index + 2]);
    const across = (x + unit * points[index]) * near;
    const up = (y + unit * points[index + 1]) * near;
    if (across < box.left) box.left = across;
    if (across > box.right) box.right = across;
    if (up < box.bottom) box.bottom = up;
    if (up > box.top) box.top = up;
  }
  return box;
}

/** The size and the place at which the points just fill a room on the screen and stand in its middle. A few passes: the
 * camera's perspective makes the box's size depend a little on the size itself. */
export function fitInto(points: ArrayLike<number>, count: number, room: Box, eye: number): { unit: number; x: number; y: number } {
  let unit = 1e-4, x = 0, y = 0;
  for (let pass = 0; pass < 6; pass++) {
    const box = boxOf(points, count, unit, x, y, eye);
    unit *= Math.min((room.right - room.left) / (box.right - box.left), (room.top - room.bottom) / (box.top - box.bottom));
    const sized = boxOf(points, count, unit, x, y, eye);
    x += (room.left + room.right - sized.left - sized.right) / 2;
    y += (room.bottom + room.top - sized.bottom - sized.top) / 2;
  }
  return { unit, x, y };
}

export type Room = { left: number; right: number; top: number; bottom: number };

/** The room beside a beat's words, in pixels of the stage from its left and its top. The space the words leave runs from
 * their column and a gap to near the stage's far edge, and over most of the stage's height; the column's place and width
 * are those of app/home-demo.css (`.product-demo-beat[data-side]`: `clamp(32px, 5vw, 80px)` in, `min(430px, 34%)` wide),
 * kept in step by hand. The wing does not get all of that space: its room is at most `BESIDE_WIDE` of the stage's width and
 * `BESIDE_TALL` of its height, so on a wide window it is not the whole picture (ADR-0098 amendment 6), and it stands in the
 * space a little nearer the words than the far edge. `beside` is 1 for the room to the right of words set at the left and
 * -1 for the room to the left of words set at the right; between the two the room slides across the stage, and at 0 it
 * stands in the middle. */
export const BESIDE_WIDE = 0.52;
export const BESIDE_TALL = 0.62;
/** Of the width the room leaves free in its space, the share that lies on the words' side. */
const BESIDE_NEAR = 0.35;
export function roomBeside(beside: number, wide: number, tall: number): Room {
  const side = Math.max(-1, Math.min(1, beside));
  const margin = Math.min(80, Math.max(32, 0.05 * wide));
  const column = Math.min(430, 0.34 * wide);
  const gap = Math.min(64, Math.max(36, 0.035 * wide));
  const inner = margin + column + gap, outer = 0.6 * margin;
  const space = wide - inner - outer; // what the words leave, across
  const across = Math.min(space, BESIDE_WIDE * wide);
  // Where the space begins as it slides, then the free width's share that lies to the room's left: the near share when the
  // words are at the left, the far share when they are at the right.
  const from = outer + ((inner - outer) * (side + 1)) / 2;
  const left = from + (space - across) * (0.5 - (0.5 - BESIDE_NEAR) * side);
  const up = Math.min(0.78 * tall, BESIDE_TALL * tall);
  const top = 0.51 * tall - up / 2;
  return { left, right: left + across, top, bottom: top + up };
}

/** The room over a beat's words when they stand under the wing: in the stage's middle, 0.66 of the stage wide (of 1.6 times
 * its height on a wider stage, so the wing does not outgrow a low window), from a little down the stage to a little above
 * where the words begin. `under` is how far down the stage the words begin, in pixels, as the page measures it. Where there
 * are no words on the stage (the beats lie under it, not on it) the room is the stage itself, less a margin and the room
 * the pool of light under the wing takes. */
export function roomAbove(wide: number, tall: number, under?: number): Room {
  if (under === undefined) return { left: 0.08 * wide, right: 0.92 * wide, top: 0.1 * tall, bottom: 0.84 * tall };
  const half = 0.33 * Math.min(wide, 1.6 * tall);
  const top = 0.08 * tall;
  return { left: wide / 2 - half, right: wide / 2 + half, top, bottom: Math.max(under - 0.07 * tall, top + 0.2 * tall) };
}
