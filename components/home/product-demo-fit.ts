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

/** The room beside a beat's words, in pixels of the stage from its left and its top: from the words' column and a gap to
 * near the stage's far edge, and most of its height. The column's place and width are those of app/home-demo.css
 * (`.product-demo-beat[data-side]`: `clamp(32px, 5vw, 80px)` in, `min(430px, 34%)` wide); the two are kept in step by hand.
 * `right` says the room is to the right of words set at the left. */
export function roomBeside(right: boolean, wide: number, tall: number): { left: number; right: number; top: number; bottom: number } {
  const margin = Math.min(80, Math.max(32, 0.05 * wide));
  const column = Math.min(430, 0.34 * wide);
  const gap = Math.min(64, Math.max(36, 0.035 * wide));
  const inner = margin + column + gap, outer = 0.6 * margin;
  return { left: right ? inner : outer, right: right ? wide - outer : wide - inner, top: 0.12 * tall, bottom: 0.9 * tall };
}
