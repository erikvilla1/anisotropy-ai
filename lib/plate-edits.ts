/**
 * A plate's boundary conditions and loads changed by a sentence, read by the page's own patterns (ADR-0101 amendment 4): "fix the left
 * edge", "XSYMM on the top edge", "pull the right edge with 2 kN", "pressure of 0.1 MPa on the face", "remove the load on the right edge".
 * Nothing waits for a model: a message every clause of which is read here is applied at once, and one with a clause this does not read
 * is left whole to the next reader (a model, where one reads; ADR-0101). The words mean what they mean everywhere on the plate: held or
 * fixed with no direction is x, y and z; clamped, built-in, encastre or a fixed support is all six; pinned is x, y and z; simply supported
 * is z; XSYMM, YSYMM and ZSYMM, and U1 to UR3, are Abaqus's (ADR-0110); tension pulls along an edge's outward normal. Nothing here computes
 * a result, and `intake.check_form` still judges every entry by name.
 *
 * Also here: a tension coupon's own grips and pull written as a plate's lists (`plateFromCoupon`), so an engineer who asks for a boundary
 * condition of their own starts from the test's, not from nothing.
 */
import type { Preview } from "./studio-api";
import { heldWords } from "./studio-copy";
import { NO_STANDARD, fieldByKey, formDefinition, isIsotropic, unitLabels, unitsOf, withTest, type StudioForm } from "./studio-form";
import { DOF_WORDS, PLATE_TEST, regionOptions, type PlateLists, type PlateLoad, type PlateSupport } from "./studio-plate";
import { tensionReady } from "./tension-screen";

export type PlateEdit = {
  lists: PlateLists;
  /** What was changed, one line each, in the words the model tree lists them. */
  done: string[];
  /** What was read and not done, with the reason: a pressure on an edge, a hole the plate does not have. */
  notes: string[];
  /** The tab the change lives under. */
  tab: "conditions" | "loads";
};

type Option = { name: string; kind: "edge" | "area" };
const SIDES = ["left", "right", "top", "bottom"] as const;
const capital = (word: string) => word.charAt(0).toUpperCase() + word.slice(1);
/** A straight edge's outward normal in the plate's axes: the direction's number and the sign of a pull along it (as the API's guard). */
const EDGE_NORMAL: Record<string, [number, number]> = { "Edge-Left": [1, -1], "Edge-Right": [1, 1], "Edge-Bottom": [2, -1], "Edge-Top": [2, 1] };
const AXIS: Record<string, number> = { x: 1, y: 2, z: 3 };
const NAMED: [RegExp, number[]][] = [
  [/\bxsymm\b/, [1, 5, 6]], [/\bysymm\b/, [2, 4, 6]], [/\bzsymm\b/, [3, 4, 5]],
  [/\b(?:encastre|clamp(?:ed|s)?|built[- ]in|fully[- ]fixed|fixed supports?|cantilever(?:ed)?)\b/, [1, 2, 3, 4, 5, 6]],
  [/\b(?:pin|pins|pinned|hinged?)\b/, [1, 2, 3]],
  [/\bsimpl[ey][- ]support(?:ed|s)?\b|\bsimple supports?\b/, [3]],
];
const CODES: [RegExp, number][] = [[/\bu1\b/, 1], [/\bu2\b/, 2], [/\bu3\b/, 3], [/\bur1\b/, 4], [/\bur2\b/, 5], [/\bur3\b/, 6]];
const HOLDS = /\b(?:fix(?:ed|es)?|hold(?:s)?|held|support(?:ed|s)?|restrain(?:ed|s)?|constrain(?:ed|s)?|lock(?:ed|s)?|ground(?:ed)?|anchor(?:ed)?|symmetr(?:y|ic)|mirror|frictionless|roller|sliding)\b/;
const REMOVES = /\b(?:remove|delete|free|release|unfix|unpin|unclamp|clear|drop|take (?:off|away)|get rid of|unsupported|unconstrained)\b/;
const NOT_AN_EDIT = /\?\s*$|^\s*(?:what|which|where|why|how|is|are|does|do|did|can|could|should|would|will|show|list|tell)\b|\b(?:don'?t|do not|never|without|instead of)\b/;
const NUMBER = String.raw`[-+−]?\s?(?:\d+(?:[.,]\d+)?|\.\d+)(?:e[-+]?\d+)?`;
// what a number is by the unit written after it, the longest unit first: a moment before a force, a pressure before a length
const UNITS: [string, "moment" | "force" | "stress" | "length" | "angle", number][] = [
  ["kn[·.* -]?m", "moment", 1e3], ["n[·.* -]?mm", "moment", 1e-3], ["n[·.* -]?m", "moment", 1], ["lbf?[·.* -]?in", "moment", 0.1129848290276167],
  ["in[·.* -]?lbf?", "moment", 0.1129848290276167],
  ["mpa", "stress", 1e6], ["kpa", "stress", 1e3], ["gpa", "stress", 1e9], ["pa", "stress", 1], ["psi", "stress", 6894.757293168361], ["ksi", "stress", 6894757.293168361],
  ["kn", "force", 1e3], ["mn", "force", 1e6], ["newtons?", "force", 1], ["n", "force", 1], ["lbf", "force", 4.4482216152605], ["lbs?", "force", 4.4482216152605],
  ["kips?", "force", 4448.2216152605],
  ["mm", "length", 1e-3], ["cm", "length", 1e-2], ["m", "length", 1], ["inch(?:es)?", "length", 0.0254], ["in", "length", 0.0254],
  ["degrees?", "angle", Math.PI / 180], ["deg", "angle", Math.PI / 180], ["°", "angle", Math.PI / 180], ["radians?", "angle", 1], ["rad", "angle", 1],
];
const QUANTITY = new RegExp(String.raw`(${NUMBER})\s*(${UNITS.map(([unit]) => unit).join("|")})(?![a-z])`, "g");
const BARE = new RegExp(String.raw`(?<![a-z0-9.])(${NUMBER})(?![a-z0-9.°])`, "g");
/** What one of a row's units is in SI, by its label. */
const IN_SI: Record<string, number> = { N: 1, lbf: 4.4482216152605, MPa: 1e6, Pa: 1, psi: 6894.757293168361, ksi: 6894757.293168361, mm: 1e-3, m: 1, in: 0.0254 };
/** A moment on a region is not read into a load yet: the package's own check of one against a hand calculation is still to be made. */
const NO_MOMENT = "A moment is not offered yet: say the force and where it acts, or turn the edge by an angle.";

const numberOf = (text: string) => Number(text.replace(/\s/g, "").replace("−", "-").replace(",", "."));
const written = (value: number) => String(Number(value.toPrecision(12)));
const plain = (text: string) => text.toLowerCase().replace(/[“”"’']/g, "'").replace(/\s+/g, " ").trim();

/** Whether a typed word is a side's name with one slip of the keys ("lefft", "rigt", "botom"), as the API's guard reads it (ADR-0101
 * amendment 3); a slip of a word of three letters is a swap alone ("tpo", not "tip"). */
function oneSlip(word: string, side: string): boolean {
  if (word === side || Math.abs(word.length - side.length) > 1) return word === side;
  if (word.length === side.length) {
    const diff = [...word].map((letter, i) => (letter === side[i] ? -1 : i)).filter((i) => i >= 0);
    const swapped = diff.length === 2 && diff[1] === diff[0] + 1 && word[diff[0]] === side[diff[1]] && word[diff[1]] === side[diff[0]];
    return swapped || (diff.length === 1 && side.length > 3);
  }
  if (side.length <= 3) return false;
  const [short, long] = word.length < side.length ? [word, side] : [side, word];
  return [...long].some((_, i) => long.slice(0, i) + long.slice(i + 1) === short);
}

/** The regions a clause names, among those the plate has; `missing` names what it asks for and the plate has not (a hole, a tab). None
 * named: an empty list. "here" and "this edge" mean the regions of the element clicked, when exactly one of them fits the words. */
function regionsIn(clause: string, options: Option[], here: string[]): { regions: string[]; missing: string | null } {
  const has = (name: string) => options.some((o) => o.name === name);
  const found: string[] = [];
  let missing: string | null = null;
  const take = (name: string, what: string) => { if (has(name)) found.push(name); else missing = missing ?? what; };
  const tabs = /\btabs?\b/.test(clause);
  // a side is named by its word, or by its word with one slip when "edge", "side" or "tab" follows it
  const sides = SIDES.filter((side) => new RegExp(String.raw`\b${side}\b(?!\s+(?:now|away|here|there|face|surface|ply|plies|layer))`).test(clause)
    || [...clause.matchAll(/\b([a-z]+)\s+(?:edges?|sides?|tabs?)\b/g)].some((m) => m[1] !== side && oneSlip(m[1], side)));
  if (tabs) for (const side of sides.length ? sides : (["bottom", "top"] as const)) take(`Tab-${capital(side)}`, "tabs: give it a tab length first");
  else if (/\b(?:all|every|each|four|4)\s+(?:the\s+|four\s+|4\s+|of the\s+)?(?:edges?|sides?)\b|\bperimeter\b|\ball around\b/.test(clause)) found.push(...Object.keys(EDGE_NORMAL));
  else for (const side of sides) take(`Edge-${capital(side)}`, `${side} edge`);
  if (/\bholes?\b/.test(clause)) take("Hole", "hole");
  if (/\b(?:face|surface|whole plate|entire plate)\b/.test(clause)) take("Face", "face");
  if (!found.length && /\b(?:here|this (?:edge|side|face|surface|one|region)|that (?:edge|side|face|surface)|the (?:selected|clicked|picked) (?:edge|side|face|one|region|element))\b/.test(clause)) {
    const kind = /\b(?:edge|side)\b/.test(clause) ? "edge" : /\b(?:face|surface)\b/.test(clause) ? "area" : null;
    const fits = here.filter((name) => options.some((o) => o.name === name && (kind === null || o.kind === kind)));
    if (fits.length === 1) found.push(fits[0]);
  }
  return { regions: [...new Set(found)], missing };
}

type Quantity = { value: number; kind: "moment" | "force" | "stress" | "length" | "angle"; said: string };
/** The numbers a clause writes with a unit, each in SI, and the numbers it writes bare. */
function quantitiesIn(clause: string): { withUnit: Quantity[]; bare: number[] } {
  const withUnit: Quantity[] = [];
  let rest = clause;
  for (const match of clause.matchAll(QUANTITY)) {
    const unit = UNITS.find(([pattern]) => new RegExp(`^(?:${pattern})$`).test(match[2]))!;
    withUnit.push({ value: numberOf(match[1]) * unit[2], kind: unit[1], said: match[0].trim() });
    rest = rest.replace(match[0], " ");
  }
  // a code's digit (U1, CF2) and a count of edges are no values
  const bare = [...rest.replace(/\b(?:u|ur|cf|cm)[1-6]\b|\b(?:four|4)\s+(?:edges|sides)\b|\ball (?:six|6)\b/g, " ").matchAll(BARE)].map((m) => numberOf(m[1]));
  return { withUnit, bare };
}

/** The direction a clause gives a force or a move, and its sign: an axis written ("in x", "along -y", "CF2", "U1"), down or up (z), or
 * tension and compression, pull and push, which take the edge's outward normal. Null when none is written. */
function directionIn(clause: string, region: string, rotation: boolean): { dof: number; sign: number; sense?: "tension" | "compression" } | { problem: string } | null {
  const code = rotation ? /\b(?:ur|cm)([123])\b/.exec(clause) : /\b(?:cf|u)([123])\b/.exec(clause);
  if (code) return { dof: Number(code[1]) + (rotation ? 3 : 0), sign: 1 };
  const axis = rotation ? /\babout\s+(?:the\s+)?([-+−]?)\s?([xyz])\b/.exec(clause)
    : /\b(?:in|along|toward|towards|against)\s+(?:the\s+)?(?:(negative|minus|positive|plus)\s+)?([-+−]?)\s?([xyz])\b|(?:^|\s)([-+−]?)([xyz])[- ]?(?:direction|axis)\b|(?:^|\s)([-+−])([xyz])\b/.exec(clause);
  if (axis) {
    const parts = axis.slice(1).filter((part) => part !== undefined);
    const letter = parts.find((part) => /^[xyz]$/.test(part))!;
    const minus = parts.some((part) => /^(?:-|−|negative|minus)$/.test(part)) || (!rotation && /\bagainst\b/.test(axis[0]));
    return { dof: AXIS[letter] + (rotation ? 3 : 0), sign: minus ? -1 : 1 };
  }
  if (rotation) return null;
  if (/\bdown(?:ward|wards)?\b/.test(clause)) return { dof: 3, sign: -1 };
  if (/\bup(?:ward|wards)?\b|\bout[- ]of[- ]plane\b/.test(clause)) return { dof: 3, sign: 1 };
  const sense = /\b(?:tension|tensile|pull(?:s|ed|ing)?|stretch(?:ed|es)?)\b/.test(clause) ? "tension" : /\b(?:compression|compressive|push(?:es|ed|ing)?|compress(?:ed|es)?)\b/.test(clause) ? "compression" : null;
  if (!sense) return null;
  const normal = EDGE_NORMAL[region];
  if (!normal) return { problem: `${capital(sense)} has no one direction on ${region}: name the direction, x, y or z.` };
  return { dof: normal[0], sign: sense === "tension" ? normal[1] : -normal[1], sense };
}

/** The directions a clause holds, by a name, by codes, by axes written, or x, y and z for a hold with none; null when it holds nothing. */
function heldIn(clause: string, region: string, kind: "edge" | "area"): number[] | { problem: string } | null {
  const named = NAMED.filter(([pattern]) => pattern.test(clause)).flatMap(([, dofs]) => dofs);
  const coded = CODES.filter(([pattern]) => pattern.test(clause)).map(([, dof]) => dof);
  if (named.length || coded.length) return [...new Set([...named, ...coded])].sort((a, b) => a - b);
  if (!HOLDS.test(clause)) return null;
  const normal = EDGE_NORMAL[region]?.[0] ?? (kind === "area" ? 3 : null);
  if (/\b(?:symmetr(?:y|ic)|mirror)\b/.test(clause)) {
    const about = /\b([xyz])[- ]?symmetr|\bsymmetr(?:y|ic)\s+(?:in|about|across)\s+(?:the\s+)?([xyz])\b/.exec(clause);
    const across = about ? AXIS[about[1] ?? about[2]] : normal;
    if (!across) return { problem: `Symmetry on ${region} needs its axis: say XSYMM, YSYMM or ZSYMM.` };
    return across === 1 ? [1, 5, 6] : across === 2 ? [2, 4, 6] : [3, 4, 5];
  }
  // the axes written: "in x and y", "x, y and z", "z only"; and the turns: "tilt about x", "rotation about z", "all rotations"
  const turns = [...clause.matchAll(/\b(?:tilt|turn|rotation|rotations|rotate)s?\s+about\s+(?:the\s+)?([xyz])\b/g)].map((m) => AXIS[m[1]] + 3);
  const all = /\b(?:all|every)\s+rotations?\b|\brotations\b(?!\s+about)/.test(clause) ? [4, 5, 6] : [];
  const moves = [...clause.replace(/\b(?:tilt|turn|rotation|rotations|rotate)s?\s+about\s+(?:the\s+)?[xyz]\b/g, " ")
    .matchAll(/(?:^|[\s,(/])([xyz])(?=$|[\s,.)/])/g)].map((m) => AXIS[m[1]]);
  const stated = [...new Set([...moves, ...turns, ...all])].sort((a, b) => a - b);
  if (stated.length) return stated;
  if (/\b(?:frictionless|sliding)\b/.test(clause)) return normal ? [normal] : { problem: `A frictionless support on ${region} needs its direction: x, y or z.` };
  if (/\broller\b/.test(clause)) return { problem: "A roller holds one direction: say which, x, y or z." };
  return [1, 2, 3];
}

const holdLine = (region: string, dofs: number[]) => heldWords(region, dofs, dofs.map((d) => DOF_WORDS[d] ?? `direction ${d}`));
const CLAUSES = new RegExp(String.raw`\s*(?:;|\.(?=\s|$)|,?\s+then\s+|,?\s+and\s+(?=(?:also\s+|then\s+)?(?:fix|clamp|pin|hold|apply|add|put|remove|delete|free|release|clear|load|pull|push|press|move|set|make|simply|[-+−]?\d))`
  + String.raw`|,\s*(?=(?:fix|clamp|pin|hold|apply|add|put|remove|delete|free|release|clear|load|pull|push|press|move|set|make|[-+−]?\d)))\s*`, "i");

const JOINED = new RegExp(String.raw`\b(?:all|every|each|both|four|4)\b|\bperimeter\b|\btabs\b|\b(?:${SIDES.join("|")})(?:\s*(?:,|and|&|\+)\s*(?:the\s+)?(?:${SIDES.join("|")}))+\s+(?:edges|sides)\b`);
const ACTS = (part: string): boolean => REMOVES.test(part) || HOLDS.test(part) || NAMED.some(([pattern]) => pattern.test(part))
  || CODES.some(([pattern]) => pattern.test(part)) || /\bcf[1-3]\b/.test(part) || new RegExp(QUANTITY.source).test(part);
/** A clause that joins two changes, each on a region of its own, by "and" or a comma ("encastre the left edge and CF2 = 500 N on the right
 * edge"), as its parts; "fix the left and right edges" is one change on two regions and stays whole. */
function parts(clause: string, options: Option[], here: string[]): string[] {
  for (const join of clause.matchAll(/\s*(?:,|\band\b)\s*/g)) {
    const a = clause.slice(0, join.index).trim(), b = clause.slice(join.index! + join[0].length).trim();
    const names = (part: string) => regionsIn(part, options, here).regions.length > 0 || /\b(?:face|surface|holes?|tabs?)\b/.test(part);
    if (a && b && names(a) && names(b) && ACTS(a) && ACTS(b)) return [...parts(a, options, here), ...parts(b, options, here)];
  }
  return [clause];
}

/**
 * The plate's lists after a message, or null when the message is not, clause for clause, a change this reads. A new hold on a region takes
 * the place of the one it had, and a new force along a direction, or a new pressure, of the one that was there: the engineer is changing
 * a boundary condition, and two that disagree on one region are never what was meant.
 */
export function readPlateEdit(text: string, form: StudioForm, current: PlateLists, here: string[] = []): PlateEdit | null {
  const message = plain(text);
  if (!message || NOT_AN_EDIT.test(message)) return null;
  const options = regionOptions(form, current);
  const kindOf = (name: string) => options.find((o) => o.name === name)?.kind ?? "edge";
  const labels = unitLabels(unitsOf(form));
  const inRow = (value: number, label: string) => written(value / (IN_SI[label] ?? 1));
  let lists = current;
  const done: string[] = [], notes: string[] = [];
  let tab: PlateEdit["tab"] | null = null;
  const dofWord = (dof: number) => DOF_WORDS[dof] ?? `direction ${dof}`;

  const clauses = message.split(CLAUSES).map((part) => part.trim().replace(/^(?:please|also|and)\s+/, "")).filter(Boolean).flatMap((clause) => parts(clause, options, here));
  for (const clause of clauses) {
    const { regions, missing } = regionsIn(clause, options, here);
    if (missing && !regions.length) { notes.push(`This plate has no ${missing}.`); continue; }
    // two regions in one clause are one change on both only when they are plainly joined ("the left and right edges", "all four edges",
    // "the tabs"); "the bottom edge is bolted down and the top edge carries 10 kN" is two statements, and which is which is not guessed
    if (regions.length > 1 && !JOINED.test(clause)) return null;

    // ---- taking a hold or a load away
    if (REMOVES.test(clause)) {
      const wide = /\b(?:all|every|everything)\b/.test(clause);
      const ofLoads = /\b(?:loads?|forces?|pressures?|moments?)\b/.test(clause);
      const ofHolds = /\b(?:bcs?|boundary conditions?|supports?|constraints?|restraints?|holds?|symmetry)\b|\b(?:free|release|unfix|unpin|unclamp|unsupported|unconstrained)\b/.test(clause);
      const both = !ofLoads && !ofHolds;
      if (!regions.length && !wide) return null;
      const on = (region: string) => !regions.length || regions.includes(region);
      const supports = ofHolds || both ? lists.supports.filter((s) => !on(s.region)) : lists.supports;
      const loads = ofLoads || both ? lists.loads.filter((l) => !on(l.region)) : lists.loads;
      const freed = [...new Set(lists.supports.filter((s) => !supports.includes(s)).map((s) => s.region))];
      const unloaded = [...new Set(lists.loads.filter((l) => !loads.includes(l)).map((l) => l.region))];
      for (const region of freed) done.push(`${region}: no longer held`);
      for (const region of unloaded) done.push(`${region}: load removed`);
      if (!freed.length && !unloaded.length) notes.push(`Nothing to remove${regions.length ? ` on ${regions.join(", ")}` : ""}: ${ofLoads && !ofHolds ? "no load is there" : ofHolds && !ofLoads ? "nothing is held there" : "nothing is held or loaded there"}.`);
      lists = { ...lists, supports, loads };
      tab = tab ?? (unloaded.length && !freed.length ? "loads" : "conditions");
      continue;
    }

    const { withUnit, bare } = quantitiesIn(clause);
    if (withUnit.length + bare.length > 1) return null; // two values in one clause: which is which is not this reader's to guess
    const quantity = withUnit[0] ?? null;
    const says = (pattern: RegExp) => pattern.test(clause);
    const kind = quantity?.kind
      ?? (bare.length ? (says(/\bpressure\b/) ? "stress" : says(/\b(?:moment|torque)\b/) ? "moment" : says(/\b(?:force|load|tension|compression)\b/) ? "force"
        : says(/\b(?:displace(?:ment|d)?|move[sd]?)\b/) ? "length" : says(/\b(?:rotat(?:e|ed|ion))\b/) ? "angle" : null) : null);
    if (bare.length && !kind) return null;

    if (kind) {
      const amount = quantity ? quantity.value : null; // SI; a bare number is in the row's own unit
      // ---- a pressure on an area
      if (kind === "stress") {
        const targets = regions.length ? regions : ["Face"];
        const edge = targets.find((region) => kindOf(region) !== "area");
        if (edge) { notes.push(`A pressure acts on an area, and ${edge} is an edge.`); continue; }
        const sign = says(/\b(?:suction|vacuum|from below|from underneath|upward|upwards)\b/) ? -1 : 1;
        const value = amount !== null ? Number(inRow(amount, labels.stress)) : bare[0];
        if (!value) return null;
        const pressure = written(sign * value);
        for (const region of targets) {
          lists = { ...lists, loads: [...lists.loads.filter((l) => !(l.region === region && l.kind === "pressure")), { region, kind: "pressure", pressure }] };
          done.push(`${region}: pressure of ${pressure} ${labels.stress}${sign < 0 ? ", lifting the plate" : ", pressing down on the plate"}`);
        }
        tab = tab ?? "loads";
        continue;
      }
      if (kind === "moment") { if (!notes.includes(NO_MOMENT)) notes.push(NO_MOMENT); continue; }
      if (!regions.length) return null;
      // ---- a force, the total over its region
      if (kind === "force") {
        const value = amount !== null ? Number(inRow(amount, labels.force)) : bare[0];
        if (!value) return null;
        for (const region of regions) {
          const direction = directionIn(clause, region, false);
          if (direction === null) return null;
          if ("problem" in direction) { notes.push(direction.problem); continue; }
          const total = written(direction.sense ? Math.abs(value) * direction.sign : value * direction.sign);
          const load: PlateLoad = { region, kind: "force", dof: direction.dof, total };
          lists = { ...lists, loads: [...lists.loads.filter((l) => !(l.region === region && l.kind === "force" && l.dof === direction.dof)), load] };
          done.push(`${region}: force of ${total} ${labels.force} along ${dofWord(direction.dof)}${direction.sense ? ` (${direction.sense})` : ""}`);
        }
        tab = tab ?? "loads";
        continue;
      }
      // ---- an edge or a face moved or turned by a set amount: a boundary condition with a value
      const value = amount !== null ? (kind === "angle" ? amount : Number(inRow(amount, labels.length))) : bare[0];
      if (!value) return null;
      for (const region of regions) {
        const direction = directionIn(clause, region, kind === "angle");
        if (direction === null) return null;
        if ("problem" in direction) { notes.push(direction.problem); continue; }
        const moved = written(direction.sense ? Math.abs(value) * direction.sign : value * direction.sign);
        const kept = lists.supports.filter((s) => s.region !== region || !s.dofs.includes(direction.dof))
          .concat(lists.supports.filter((s) => s.region === region && s.dofs.includes(direction.dof) && !s.value.trim() && s.dofs.length > 1)
            .map((s) => ({ ...s, dofs: s.dofs.filter((d) => d !== direction.dof) })));
        lists = { ...lists, supports: [...kept, { region, dofs: [direction.dof], value: moved }] };
        done.push(`${region}: ${kind === "angle" ? "turned" : "moved"} ${moved} ${kind === "angle" ? "rad" : labels.length} ${kind === "angle" ? "about" : "along"} ${kind === "angle" ? "xyz"[direction.dof - 4] : dofWord(direction.dof)}`);
      }
      tab = tab ?? "conditions";
      continue;
    }

    // ---- a hold
    if (!regions.length) return null;
    let read = false;
    for (const region of regions) {
      const dofs = heldIn(clause, region, kindOf(region));
      if (dofs === null) return null;
      read = true;
      if ("problem" in dofs) { if (!notes.includes(dofs.problem)) notes.push(dofs.problem); continue; }
      const moving = lists.supports.filter((s) => s.region === region && s.value.trim() && !dofs.includes(s.dofs[0]));
      const support: PlateSupport = { region, dofs, value: "" };
      lists = { ...lists, supports: [...lists.supports.filter((s) => s.region !== region), ...moving, support] };
      done.push(holdLine(region, dofs));
    }
    if (!read) return null;
    tab = tab ?? "conditions";
  }
  if (!done.length && !notes.length) return null;
  return { lists, done, notes, tab: tab ?? "conditions" };
}

/** Whether a message, on a tension coupon, asks for a boundary condition or a load on a region only a plate has: it names an edge, the
 * face, the hole or a tab, and reads as a change. A coupon's own pull ("pull it with 2 kN") names no region and stays the coupon's. */
export function asksPlateEdit(text: string, form: StudioForm): boolean {
  const asPlate = asPlateOf(form);
  return regionsNamed(text, form).length > 0 && readPlateEdit(text, asPlate, EMPTY) !== null;
}
const EMPTY: PlateLists = { supports: [], loads: [], regions: [] };
/** The coupon as the plate it would be: every region a plate of its shape has can be named, its tabs too (a coupon under a standard states
 * no tab length of its own, and the test gives it one). */
const asPlateOf = (form: StudioForm): StudioForm => ({ ...form, test: PLATE_TEST, tab_length: Number(form.tab_length) > 0 ? form.tab_length : "1" });
/** The plate regions a message names, on the coupon taken as a plate. */
export const regionsNamed = (text: string, form: StudioForm): string[] => regionsIn(plain(text), regionOptions(asPlateOf(form), EMPTY), []).regions;
/** Whether a message names a region a tension test does not act on, a side edge, the face or a hole: then it is no word about the coupon's
 * own pull, whatever else the coupon's patterns read in it ("pull the right edge with 2 kN"). */
export const namesOffAxis = (text: string, form: StudioForm): boolean => regionsNamed(text, form).some((name) => !/^(?:Edge|Tab)-(?:Top|Bottom)$/.test(name));

// ----------------------------------------------------------------------------------------------- from a tension coupon

type Built = Pick<Preview, "units" | "geometry" | "held" | "loaded">;

/** The tests held by two grips, which a plate's regions can hold the same way: a straight strip pulled or pushed, with or without a hole. */
const GRIPPED_TESTS = ["", "unnotched tension", "unnotched compression", "open-hole tension"];
/** Whether a coupon can be carried over to boundary conditions of the engineer's own: a strip of plies held by its grips. A dog-bone's
 * outline and one isotropic material are not a plate's to take (ADR-0054). */
export const canBecomePlate = (form: StudioForm): boolean =>
  GRIPPED_TESTS.includes((form.test ?? "").trim()) && !isIsotropic(form) && !(form.narrow_width ?? "").trim();

/**
 * A tension coupon as a plate held and loaded the same way (ADR-0089 amendment 8): the test's rows with the test "plate" and no standard,
 * and the coupon's own grips and pull as the plate's first boundary conditions and load. From the model the setup built (`built`, the
 * preview) where there is one: its size, what each grip holds and how far or how hard the top one is pulled. Without one, from the rows:
 * the bottom end fixed, the top end free to move along the coupon, and the pull the rows state. `carried` says each in a line. A form
 * that is no coupon yet (no material or no layup, and no model built) carries nothing: it is a plate to hold and load from nothing.
 */
function usual_pull(form: StudioForm, chosen: Record<string, string>): { control: string; value: number; dof: number; set: string } | null {
  const usual = formDefinition.tension && formDefinition.tension.units === unitsOf(form) ? formDefinition.tension : null;
  const control = (form.control ?? "").trim() || usual?.control || "displacement";
  const value = Number(chosen.value ?? (usual && control === usual.control ? usual.value : NaN));
  return Number.isFinite(value) && value !== 0 ? { control, value, dof: 2, set: "Grip-Top" } : null;
}

export function plateFromCoupon(form: StudioForm, built: Built | null, chosen: Record<string, string> = {}): { form: StudioForm; lists: PlateLists; carried: string[] } {
  const next: StudioForm = { ...withTest(form, PLATE_TEST).form, standard: NO_STANDARD, specimen: "" };
  const same = built && built.units === unitsOf(form) ? built : null;
  if (same) for (const key of ["length", "width", "tab_length"] as const) {
    const value = same.geometry[key];
    if (!(next[key] ?? "").trim() && typeof value === "number") next[key] = written(value);
  }
  // the element size the test chose stays, so the model is the test's until something is changed; with no check yet the package chooses
  const usual = String(fieldByKey.element_size?.defaults?.[unitsOf(form)] ?? fieldByKey.element_size?.default ?? "");
  if (!(next.element_size ?? "").trim() || next.element_size === usual) next.element_size = chosen.element_size ?? "";
  const tabs = Number(next.tab_length) > 0;
  const region = (set: string) => (/bottom/i.test(set) ? (tabs ? "Tab-Bottom" : "Edge-Bottom") : tabs ? "Tab-Top" : "Edge-Top");
  const supports: PlateSupport[] = [];
  const loads: PlateLoad[] = [];
  const grips = same ? same.held.filter((h) => /^Grip-(?:Bottom|Top)$/.test(h.set)) : [];
  if (!same && !tensionReady(form)) return { form: next, lists: { supports: [], loads: [], regions: [] }, carried: [] };
  if (grips.length) {
    for (const set of [...new Set(grips.map((h) => h.set))]) {
      const dofs = [...new Set(grips.filter((h) => h.set === set).flatMap((h) => h.dofs))].sort((a, b) => a - b);
      supports.push({ region: region(set), dofs, value: "" });
    }
  } else {
    supports.push({ region: region("Grip-Bottom"), dofs: [1, 2, 3, 4, 5, 6], value: "" }, { region: region("Grip-Top"), dofs: [1, 3, 4, 5, 6], value: "" });
  }
  const pull = same?.loaded && /^Grip-/.test(same.loaded.set) ? { control: same.loaded.control, value: same.loaded.value, dof: same.loaded.dof, set: same.loaded.set }
    : (form.value ?? "").trim() && Number.isFinite(Number(form.value)) ? { control: (form.control ?? "").trim() || "displacement", value: Number(form.value), dof: 2, set: "Grip-Top" }
    // no pull written and no model built (a row of the coupon still missing, or no answer): the pull the test is given when none is
    // written, which the Loads step already shows ("1 mm pull"), so what the engineer saw is what comes across
    : usual_pull(form, chosen);
  if (pull && pull.value) {
    const on = region(pull.set);
    if (pull.control === "force") loads.push({ region: on, kind: "force", dof: pull.dof, total: written(pull.value) });
    else {
      // the moved direction is its own entry with its value; the grip's hold keeps the others
      for (const s of supports) if (s.region === on) s.dofs = s.dofs.filter((d) => d !== pull.dof);
      supports.push({ region: on, dofs: [pull.dof], value: written(pull.value) });
    }
  }
  const labels = unitLabels(unitsOf(next));
  const carried = [
    ...supports.filter((s) => !s.value && s.dofs.length).map((s) => holdLine(s.region, s.dofs)),
    ...supports.filter((s) => s.value).map((s) => `${s.region}: moved ${s.value} ${labels.length} along ${DOF_WORDS[s.dofs[0]] ?? "y"}`),
    ...loads.map((l) => (l.kind === "force" ? `${l.region}: force of ${l.total} ${labels.force} along ${DOF_WORDS[l.dof] ?? "y"}` : "")),
  ].filter(Boolean);
  return { form: next, lists: { supports: supports.filter((s) => s.dofs.length), loads, regions: [] }, carried };
}

/** What the chat says once a tension coupon is carried over, under what was changed: whose the boundary conditions now are, and what
 * was kept of the test's. */
export const ownWords = (carried: string[]): string => "These are now your own boundary conditions, so the model no longer follows the tension test standard."
  + (carried.length ? ` Kept from the test: ${carried.join("; ")}.` : "")
  + (carried.some((line) => /^Edge-/.test(line)) ? " No tab length is set, so the ends are held along their edges." : "");
