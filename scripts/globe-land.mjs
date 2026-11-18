#!/usr/bin/env node
// Writes lib/globe-land.json, the coasts and borders the contact page's globe draws (components/contact/contact-globe.tsx).
//
//     node scripts/globe-land.mjs <path to world-atlas's countries-110m.json>
//
// The source is the public npm package world-atlas, version 2 (TopoJSON built from Natural Earth's 1:110m countries; Natural
// Earth's data is in the public domain, the package is under the ISC licence, kept word for word in the file this writes).
// The package is not a dependency of the site: fetch it into a folder of its own (`npm pack world-atlas@2`, then unpack),
// and give this script the file's path. Nothing is fetched in a visitor's browser.
//
// A TopoJSON file stores every stretch of coast or border once, as an "arc" shared by the shapes on either side of it. The
// globe draws lines, not filled shapes, so the arcs are all it needs, each drawn once. An arc is a list of whole-number steps:
// the first pair is a position, every later pair the step from the pair before; a position times `transform.scale` plus
// `transform.translate` is degrees east and degrees north. Each point is rounded to a tenth of a degree, which is finer than
// the globe is ever drawn; a point that rounds onto the one before it is left out, and so is a line left with one point.

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "lib", "globe-land.json");
const LICENCE = [
  "Copyright 2013-2019 Michael Bostock",
  "Permission to use, copy, modify, and/or distribute this software for any purpose with or without fee is hereby granted, provided that the above copyright notice and this permission notice appear in all copies.",
  'THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.',
];

const path = process.argv[2];
if (!path) {
  console.error("usage: node scripts/globe-land.mjs <path to world-atlas's countries-110m.json>");
  process.exit(1);
}
const topology = JSON.parse(readFileSync(path, "utf8"));
if (topology.type !== "Topology" || !Array.isArray(topology.arcs) || !topology.transform) {
  console.error(`${path} is not a quantized TopoJSON topology`);
  process.exit(1);
}
const [scaleX, scaleY] = topology.transform.scale;
const [fromX, fromY] = topology.transform.translate;
const tenth = (value) => Math.round(value * 10) / 10 + 0; // + 0 so no -0

const lines = [];
let read = 0;
for (const arc of topology.arcs) {
  let x = 0, y = 0;
  const line = [];
  for (const [stepX, stepY] of arc) {
    x += stepX;
    y += stepY;
    read += 1;
    const place = [tenth(x * scaleX + fromX), tenth(y * scaleY + fromY)];
    if (!Number.isFinite(place[0]) || !Number.isFinite(place[1]) || Math.abs(place[0]) > 180 || Math.abs(place[1]) > 90) {
      console.error(`a point of ${path} is not a place on the globe: ${place}`);
      process.exit(1);
    }
    const last = line[line.length - 1];
    if (!last || last[0] !== place[0] || last[1] !== place[1]) line.push(place);
  }
  if (line.length >= 2) lines.push(line);
}

const record = {
  what: "The world's coasts and borders as lines, each drawn once, for the contact page's globe: degrees east and degrees north, to a tenth of a degree",
  source: "The npm package world-atlas, version 2, file countries-110m.json: TopoJSON built from Natural Earth's 1:110m countries (naturalearthdata.com, public domain)",
  licence: ["world-atlas is under the ISC licence:", ...LICENCE],
  made_by: "scripts/globe-land.mjs",
  lines,
};
writeFileSync(OUT, JSON.stringify(record) + "\n", "utf8");
const kept = lines.reduce((sum, line) => sum + line.length, 0);
console.log(`lib/globe-land.json: ${lines.length} lines of ${topology.arcs.length} arcs, ${kept} points of ${read}, ${Math.round(readFileSync(OUT).length / 1024)} KB`);
