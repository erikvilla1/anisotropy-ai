/** The geometry of the contact page's globe (components/contact/contact-globe.tsx): where a place on the globe is seen once
 * the globe is turned, and which parts of a line are on the side that faces the eye. Pure numbers, no page.
 *
 * The globe is a sphere of radius 1 seen from far away (an orthographic view), so a point is drawn at its own x and y and its
 * z says which side it is on. x runs to the right, y up and z towards the eye. */

/** A place on the globe: degrees east and degrees north. */
export type Place = readonly [number, number];
/** A point on the unit sphere, from its middle: x to the right, y up, z towards the eye. */
export type Vector = readonly [number, number, number];
/** How the globe is turned: the place that faces the eye, which is drawn in the disc's middle. North stays up. */
export type Turn = { lon: number; lat: number };
/** A turn as nine numbers, three rows of three: the row for x, for y and for z. */
export type TurnMatrix = readonly number[];

const RADIANS = Math.PI / 180;

/** A place as a point on the sphere before any turn: 0 east, 0 north faces the eye, north is up and east to the right. */
export function toVector([lon, lat]: Place): Vector {
  const east = lon * RADIANS, north = lat * RADIANS;
  return [Math.cos(north) * Math.sin(east), Math.sin(north), Math.cos(north) * Math.cos(east)];
}

/** The turn that brings `turn`'s place to face the eye: first about the upright axis, until the place's meridian faces the
 * eye, then about the level axis across the view, until its latitude does. */
export function turnMatrix(turn: Turn): TurnMatrix {
  const east = turn.lon * RADIANS, north = turn.lat * RADIANS;
  const cosEast = Math.cos(east), sinEast = Math.sin(east), cosNorth = Math.cos(north), sinNorth = Math.sin(north);
  return [
    cosEast, 0, -sinEast,
    -sinNorth * sinEast, cosNorth, -sinNorth * cosEast,
    cosNorth * sinEast, sinNorth, cosNorth * cosEast,
  ];
}

/** A point as it is seen once the globe is turned. */
export function seenAs(point: Vector, matrix: TurnMatrix): Vector {
  const [x, y, z] = point;
  return [
    matrix[0] * x + matrix[1] * y + matrix[2] * z,
    matrix[3] * x + matrix[4] * y + matrix[5] * z,
    matrix[6] * x + matrix[7] * y + matrix[8] * z,
  ];
}

/** A place as it is seen once the globe is turned. */
export const turned = (place: Place, turn: Turn): Vector => seenAs(toVector(place), turnMatrix(turn));

/** Where a seen point is drawn on the unit disc: x to the right and y up, both from -1 to 1. */
export const flat = (seen: Vector): [number, number] => [seen[0], seen[1]];

/** Whether a seen point is on the side of the globe that faces the eye. A point on the limb, the disc's edge, counts as near. */
export const isNear = (seen: Vector): boolean => seen[2] >= 0;

/** Where the straight step from a near point to a far one leaves the near side: on the limb, the disc's edge, so at radius 1.
 * The step is short against the globe, so the point where it crosses the plane through the limb, pushed out to the sphere,
 * stands for the place the line itself crosses. */
export function limbCut(near: Vector, far: Vector): [number, number] {
  const along = near[2] / (near[2] - far[2]);
  const x = near[0] + (far[0] - near[0]) * along, y = near[1] + (far[1] - near[1]) * along;
  const length = Math.hypot(x, y);
  // Two points straight across the globe from one another cross at its middle, which is no place on the limb: the nearer end's side is taken.
  if (!(length > 1e-9)) {
    const side = Math.hypot(near[0], near[1]);
    return side > 1e-9 ? [near[0] / side, near[1] / side] : [1, 0];
  }
  return [x / length, y / length];
}

/** A line's points as numbers in a row, x, y and z of each, before any turn: what `nearRuns` reads. Made once for a line,
 * so a frame of the turning globe does no trigonometry for it. */
export function vectorsOf(line: readonly Place[]): Float32Array {
  const row = new Float32Array(line.length * 3);
  line.forEach((place, index) => row.set(toVector(place), index * 3));
  return row;
}

/** The parts of a line that are on the near side once the globe is turned, each as numbers in a row, x and y of each point on
 * the unit disc. Where the line goes round to the far side it is cut on the limb, and it starts again on the limb where it
 * comes back, so a coast meets the disc's edge and does not stop short of it. A part of one point is left out. */
export function nearRuns(line: ArrayLike<number>, matrix: TurnMatrix): number[][] {
  const runs: number[][] = [];
  let run: number[] | null = null;
  let before: Vector | null = null;
  for (let index = 0; index + 2 < line.length; index += 3) {
    const seen = seenAs([line[index], line[index + 1], line[index + 2]], matrix);
    if (isNear(seen)) {
      if (!run) {
        run = [];
        if (before) run.push(...limbCut(seen, before)); // coming back round: from the limb
      }
      run.push(seen[0], seen[1]);
    } else if (run && before) {
      run.push(...limbCut(before, seen)); // going round: to the limb
      if (run.length >= 4) runs.push(run);
      run = null;
    }
    before = seen;
  }
  if (run && run.length >= 4) runs.push(run);
  return runs;
}

/** The lines of latitude and longitude every `step` degrees, as places a few degrees apart: a faint net under the coasts.
 * The meridians stop short of the poles, where they would all meet in a knot. */
export function graticule(step: number, every = 5): Place[][] {
  const lines: Place[][] = [];
  for (let lon = -180; lon < 180; lon += step) {
    const line: Place[] = [];
    for (let lat = -90 + step / 2; lat <= 90 - step / 2 + 1e-9; lat += every) line.push([lon, lat]);
    lines.push(line);
  }
  for (let lat = -90 + step; lat < 90; lat += step) {
    const line: Place[] = [];
    for (let lon = -180; lon <= 180 + 1e-9; lon += every) line.push([lon, lat]);
    lines.push(line);
  }
  return lines;
}
