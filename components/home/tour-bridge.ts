/** The bridge from the hero into the tour: as the page scrolls off the hero, the hero's clip (or its still) shrinks into a
 * card, lies back into the 3D view's perspective and lands on the top ply of the laminate, which has stood behind it all
 * along; then the clip fades and the ply it lay on is seen. The clip is the hero's own element, moved with one CSS transform;
 * nothing is copied or redrawn. This file is the geometry: where the top ply's face is on screen, and the transform that
 * carries a rectangle onto it. */

import { AZIMUTH_START, BRIDGE_EXPLODE_FROM, smooth, span } from "./tour-timeline";

// The 3D view's camera and stack, as components/home/laminate-scene.tsx sets them (CAMERA_POSITION, CAMERA.fov, WIDTH, DEPTH,
// STACK_HEIGHT, FitWidth, Turn). They are repeated here because that file exports none of them: if the view's camera or the
// stack's size changes there, these must follow, or the clip will land beside the ply instead of on it.
const CAMERA_POSITION = [1.75, -1.95, 1.25] as const;
const CAMERA_FOV_DEG = 30;
const FACE_WIDTH = 1.4; // x, along the 0° fiber
const FACE_DEPTH = 0.9; // y, across
const STACK_HEIGHT = 0.42;
const FULL_ASPECT = 4 / 3; // below this the view zooms out to keep the stack's width in frame

export type Point = [number, number];
export type Rect = { x: number; y: number; width: number; height: number };

/** The corners of the top ply's face in the view's own pixels, for a view `width` by `height` whose camera is turned by
 * `azimuthDeg`: the far-left corner first, then clockwise as seen from above, so a picture laid on them reads upright along
 * the fibers. The stack is closed (not exploded). */
export function topFace(width: number, height: number, azimuthDeg: number): [Point, Point, Point, Point] {
  const radius = Math.hypot(CAMERA_POSITION[0], CAMERA_POSITION[1]);
  const bearing = Math.atan2(CAMERA_POSITION[1], CAMERA_POSITION[0]) + (azimuthDeg * Math.PI) / 180;
  const eye = [radius * Math.cos(bearing), radius * Math.sin(bearing), CAMERA_POSITION[2]];
  const distance = Math.hypot(eye[0], eye[1], eye[2]);
  // The camera looks at the origin with z up: its backward axis, then right, then up (as three.js builds them).
  const back = eye.map((value) => value / distance);
  const rightLength = Math.hypot(back[1], back[0]);
  const right = [-back[1] / rightLength, back[0] / rightLength, 0];
  const up = [back[1] * right[2] - back[2] * right[1], back[2] * right[0] - back[0] * right[2], back[0] * right[1] - back[1] * right[0]];
  const aspect = width / Math.max(height, 1);
  const zoom = Math.min(1, aspect / FULL_ASPECT);
  const tangent = Math.tan((CAMERA_FOV_DEG * Math.PI) / 360) / zoom;
  const z = STACK_HEIGHT / 2;
  const corners: [number, number][] = [[-1, 1], [1, 1], [1, -1], [-1, -1]];
  return corners.map(([sx, sy]) => {
    const point = [(sx * FACE_WIDTH) / 2 - eye[0], (sy * FACE_DEPTH) / 2 - eye[1], z - eye[2]];
    const dot = (axis: number[]) => point[0] * axis[0] + point[1] * axis[1] + point[2] * axis[2];
    const depth = -dot(back);
    const ndcX = dot(right) / (depth * tangent * aspect);
    const ndcY = dot(up) / (depth * tangent);
    return [(ndcX * 0.5 + 0.5) * width, (0.5 - ndcY * 0.5) * height] as Point;
  }) as [Point, Point, Point, Point];
}

/** The CSS `matrix3d` that carries the rectangle `from` (in an element's own pixels, its origin at the element's top left
 * corner, with `transform-origin: 0 0`) onto the four points `to`: top left, top right, bottom right, bottom left. */
export function quadTransform(from: Rect, to: [Point, Point, Point, Point]): string {
  const [[x0, y0], [x1, y1], [x2, y2], [x3, y3]] = to;
  const dx1 = x1 - x2, dx2 = x3 - x2, dx3 = x0 - x1 + x2 - x3;
  const dy1 = y1 - y2, dy2 = y3 - y2, dy3 = y0 - y1 + y2 - y3;
  const det = dx1 * dy2 - dx2 * dy1;
  const g = det ? (dx3 * dy2 - dx2 * dy3) / det : 0;
  const h = det ? (dx1 * dy3 - dx3 * dy1) / det : 0;
  // The unit square onto the points, then the rectangle onto the unit square.
  const a = (x1 - x0 + g * x1) / from.width, b = (x3 - x0 + h * x3) / from.height;
  const d = (y1 - y0 + g * y1) / from.width, e = (y3 - y0 + h * y3) / from.height;
  const gu = g / from.width, hv = h / from.height;
  const c = x0 - a * from.x - b * from.y;
  const f = y0 - d * from.x - e * from.y;
  const w = 1 - gu * from.x - hv * from.y;
  const n = (value: number) => (Math.abs(value) < 1e-10 ? "0" : value.toPrecision(8));
  return `matrix3d(${n(a)},${n(d)},0,${n(gu)},${n(b)},${n(e)},0,${n(hv)},0,0,1,0,${n(c)},${n(f)},0,${n(w)})`;
}

/** What the bridge needs to know of the page: the box the hero's clip plays in, with its corner radius, and the 3D view's
 * box, both in the window's pixels while the hero is held in the window. */
export type BridgeGeometry = { media: Rect & { radius?: number }; view: Rect };

export type BridgeFrame = {
  /** The hero's words, badge and button: their opacity, and how far they have drifted up, in pixels. */
  copy: number; lift: number;
  /** The shades the hero lays over its clip for the words' sake. */
  shade: number;
  /** The hero's black ground around the box: its opacity. It goes first, so what the shrinking clip uncovers is the stage. */
  ground: number;
  /** The clip: the part of it that is kept (a CSS `inset()`), its transform, its opacity, and whether it is still drawn. */
  clip: string; transform: string; opacity: number; media: boolean;
};

const mix = (from: number, to: number, share: number) => from + (to - from) * share;
// The bridge in the first screen of scroll: the words leave, the clip shrinks into a card, the card lies back onto the top
// ply, the clip fades off the ply, and (in the timeline) the plies separate.
const COPY = [0, 0.26] as const;
const GROUND = [0, 0.12] as const;
const CARD = [0.03, 0.46] as const;
const TILT = [0.32, 0.7] as const;
const FADE = [0.66, BRIDGE_EXPLODE_FROM - 0.02] as const;
const CARD_WIDTH = 0.48; // the flat card's width, as a share of the window's
const CARD_RADIUS = 14; // the card's corner radius on screen, in pixels

export function bridgeFrame(t: number, geometry: BridgeGeometry): BridgeFrame {
  const { media, view } = geometry;
  const card = smooth(span(t, CARD[0], CARD[1]));
  const tilt = smooth(span(t, TILT[0], TILT[1]));
  // The part of the clip that is kept takes the face's proportions, cut from the middle.
  const aspect = FACE_WIDTH / FACE_DEPTH;
  const keptWidth = Math.min(media.width, media.height * aspect);
  const keptHeight = keptWidth / aspect;
  const insetX = (card * (media.width - keptWidth)) / 2;
  const insetY = (card * (media.height - keptHeight)) / 2;
  const kept: Rect = { x: insetX, y: insetY, width: media.width - 2 * insetX, height: media.height - 2 * insetY };
  // The flat card: the kept part, scaled about its middle, moving from the window's middle to the view's.
  const scale = mix(1, (CARD_WIDTH * media.width) / keptWidth, card);
  const centreX = mix(media.x + media.width / 2, view.x + view.width / 2, card);
  const centreY = mix(media.y + media.height / 2, view.y + view.height / 2, card);
  const halfWidth = (kept.width * scale) / 2, halfHeight = (kept.height * scale) / 2;
  const flat: Point[] = [[centreX - halfWidth, centreY - halfHeight], [centreX + halfWidth, centreY - halfHeight],
    [centreX + halfWidth, centreY + halfHeight], [centreX - halfWidth, centreY + halfHeight]];
  // The top ply's face, where the card lands.
  const face = topFace(view.width, view.height, AZIMUTH_START).map(([x, y]) => [x + view.x, y + view.y] as Point);
  const to = flat.map(([x, y], index) => [mix(x, face[index][0], tilt) - media.x, mix(y, face[index][1], tilt) - media.y] as Point);
  // The corners go from the box's own radius to the card's, and are square again when the card is a ply.
  const radius = (mix(media.radius ?? 0, CARD_RADIUS, card) * (1 - tilt)) / scale;
  const opacity = 1 - span(t, FADE[0], FADE[1]);
  return {
    copy: 1 - span(t, COPY[0], COPY[1]),
    lift: -28 * smooth(span(t, COPY[0], COPY[1])),
    shade: 1 - span(t, CARD[0], 0.3),
    ground: 1 - span(t, GROUND[0], GROUND[1]),
    clip: `inset(${insetY.toFixed(2)}px ${insetX.toFixed(2)}px round ${radius.toFixed(2)}px)`,
    transform: quadTransform(kept, to as [Point, Point, Point, Point]),
    opacity,
    media: opacity > 0,
  };
}
