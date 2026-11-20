/**
 * The wing's chat (ADR-0128): what the page reads in a message by its own patterns, and how it answers from the engine's report. A change
 * of plies is read into the engine's form (`PlyChange`, `engine/src/anisotropy_engine/wing/changes.py`), every number taken from the
 * engineer's words, and the API previews it before the engineer applies it; a question about the wing is answered from the report the
 * page already holds, every number as the engine gave it; a question of why, how or which test is answered from the reference pages the
 * API's search finds. Nothing here computes a result. Pure: no React, no browser, so `tests/wing-chat.test.ts` runs it.
 */
import {
  answerWords, CHECK_NAMES, CHECK_WORDS, marginText, ruleTitle, shown, STRENGTH_LABELS, strengthWords, unitText, whereWords,
  type WingCase, type WingCheckName, type WingDescription, type WingPart, type WingReport, type WingRule, type WingRuleName,
} from "./wing";

/** Every way the wing's chat answers a message. */
export const WING_ROUTES = ["wing-change", "wing-result", "wing-rules", "wing-strengths", "wing-reference", "wing-command", "wing-unread"] as const;
export type WingRoute = (typeof WING_ROUTES)[number];

/** The parts whose plies a message may change, by the wing file's table. */
export type PlyPart = "skin" | "spar" | "spar_caps";
/** A change of plies as the engine's `PlyChange` takes it: `count` is the plies of the whole laminate, both halves; `start` and `end` are
 * fractions of the half span from the root. */
export type PlyChange = {
  action: "add_plies" | "remove_plies"; part: PlyPart; angle: number; count: number; start: number; end: number; placement: "beside" | "middle";
};
/** What a question of the results asks for. */
export type ResultTopic = "verdict" | "which" | WingCheckName | "skin" | "web" | "mass" | "tip_deflection" | "tip_twist" | "frequency"
  | "divergence" | "reversal" | "layup";

export type WingAsk =
  /** A change: read whole (`change`), or not (`problem`, in the page's words, and whether it asks back rather than declines). */
  | { route: "wing-change"; change: PlyChange | null; whole: boolean; problem: string | null; asks: boolean }
  | { route: "wing-result"; topic: ResultTopic; yesNo: boolean; part?: WingPart | null }
  | { route: "wing-rules"; rules: WingRuleName[]; part: WingPart | null; limit: boolean }
  | { route: "wing-strengths"; part: WingPart | null }
  /** A question of why, how or which test: the reference pages answer it, beside the wing's own facts on what it names. */
  | { route: "wing-reference"; topic: ResultTopic | null }
  | { route: "wing-command"; command: "step" | "check" }
  | { route: "wing-unread" };

export const PART_WORDS: Record<PlyPart, string> = { skin: "the skin", spar: "the spar webs", spar_caps: "the spar caps" };
const RULE_PART_WORDS: Record<WingPart, string> = { skin: "the skin", spar: "the spar webs", cap: "the spar caps", rib: "the ribs" };
const PLURAL: Record<WingPart, boolean> = { skin: false, spar: true, cap: true, rib: true };

/** A message as the patterns read it: lower case, one space, typographic signs made plain. */
function plain(text: string): string {
  return text.toLowerCase().replace(/[’‘]/g, "'").replace(/[−–—]/g, "-").replace(/º/g, "°").replace(/\s+/g, " ").trim();
}

const COUNT_WORDS: Record<string, number> = {
  a: 1, an: 1, one: 1, single: 1, two: 2, "a pair of": 2, "a couple of": 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, ten: 10, twelve: 12,
};
const COUNT = String.raw`(\d+|a pair of|a couple of|two|three|four|five|six|seven|eight|ten|twelve|one|single|an|a)`;
const ANGLE = String.raw`([+-]?\d+(?:\.\d+)?|zero|plus \d+|minus \d+)`;
const DEGREES = String.raw`(?:\s*(?:°|deg(?:ree)?s?\b|-degree\b))?`;
const PLIES = String.raw`(?:plies|ply|layers?)\b`;
// "2 0 plies", "two 0° plies", "2 x 0 deg plies", "2 more 0-degree plies"
const COUNT_ANGLE = new RegExp(String.raw`\b${COUNT}\s*(?:x|×)?\s*(?:more\s+|extra\s+|additional\s+)?${ANGLE}${DEGREES}\s*-?\s*${PLIES}`);
// "2 plies at 0°", "2 plies of 45", "two more plies at -45 degrees"
const COUNT_PLIES_AT = new RegExp(String.raw`\b${COUNT}\s*(?:more\s+|extra\s+|additional\s+)?${PLIES}\s*(?:at|of|@|oriented at)\s*${ANGLE}${DEGREES}`);
const PERCENT = String.raw`(\d+(?:\.\d+)?)\s*(?:%|percent\b|per cent\b)`;

const ADD = /\b(?:add|adding|put|place|insert|lay up|layup|more|extra|increase|reinforce|thicken|thicker|beef up|stiffen)\b/;
const REMOVE = /\b(?:remove|removing|take (?:out|off|away)|delete|cut|fewer|less|reduce|thin(?:ner)?|drop (?:\d|a |an |one|two|four|the))\b/;

function countOf(word: string): number {
  return COUNT_WORDS[word] ?? Number(word);
}

function angleOf(word: string): number {
  if (word === "zero") return 0;
  if (word.startsWith("plus ")) return Number(word.slice(5));
  if (word.startsWith("minus ")) return -Number(word.slice(6));
  return Number(word);
}

/** The part a message names, or "rib", or null; two parts named are "both". */
function partOf(text: string): PlyPart | "rib" | "both" | null {
  const found = new Set<PlyPart | "rib">();
  if (/\b(?:spar[\s-]*caps?|caps?|flanges?)\b/.test(text)) found.add("spar_caps");
  if (/\b(?:spar[\s-]*webs?|shear[\s-]*webs?|webs?)\b/.test(text) || /\bspars?\b(?![\s-]*caps?)/.test(text)) found.add("spar");
  if (/\bskins?\b/.test(text)) found.add("skin");
  if (/\bribs?\b/.test(text)) found.add("rib");
  if (found.size > 1) return "both";
  return found.size ? [...found][0] : null;
}

/** Where along the half span a message puts its change: from and to as fractions, the whole span when it names none, or a problem when it
 * names a place the patterns cannot put a number on ("near the root"). Every number is one the message writes. */
function spanOf(text: string): { start: number; end: number; whole: boolean } | { problem: string } {
  if (/\b(?:whole|full|entire|all along the|along the whole|everywhere|root to tip|from root to tip|all the way)\b/.test(text)) return { start: 0, end: 1, whole: false };
  const places: { at: number; value: number }[] = [];
  for (const m of text.matchAll(new RegExp(PERCENT, "g"))) places.push({ at: m.index ?? 0, value: Number(m[1]) / 100 });
  for (const m of text.matchAll(/\broot\b/g)) places.push({ at: m.index ?? 0, value: 0 });
  for (const m of text.matchAll(/\btip\b/g)) places.push({ at: m.index ?? 0, value: 1 });
  places.sort((a, b) => a.at - b.at);
  const percents = [...text.matchAll(new RegExp(PERCENT, "g"))];
  if (places.length >= 2) {
    const [a, b] = [places[0].value, places[places.length - 1].value];
    return { start: Math.min(a, b), end: Math.max(a, b), whole: false };
  }
  if (percents.length === 1) {
    const before = text.slice(0, percents[0].index ?? 0);
    const p = Number(percents[0][1]) / 100;
    if (/\b(?:outboard of|outboard from|beyond|past|after|from|starting at)\s*(?:the\s+)?$/.test(before)) return { start: p, end: 1, whole: false };
    return { start: 0, end: p, whole: false }; // "to 40 %", "the first 40 %", "inboard of 40 %"
  }
  if (places.length === 1 || /\b(?:near|close to|around|by|at|toward|towards)\s+the\s+(?:root|tip)\b|\binboard\b|\boutboard\b/.test(text)) {
    return { problem: "Say where along the half span, as a percentage: for example “from the root to 40% span”." };
  }
  return { start: 0, end: 1, whole: true };
}

/** A message read as a change of plies: whole, or with what is missing in the page's words. Null when the message is not a change. */
function changeOf(text: string): WingAsk | null {
  const adds = ADD.test(text), removes = REMOVE.test(text);
  const plies = /\bpl(?:y|ies)\b|\blayers?\b/.test(text);
  const part = partOf(text);
  const asking = /^(?:what|which|how|why|does|do|is|are|can i|should)\b/.test(text) && !/^(?:what if|what happens if|what would happen if|can you|could you)\b/.test(text);
  if (!(adds || removes) || asking || (!plies && part === null)) return null;
  const change = (problem: string, asks = true): WingAsk => ({ route: "wing-change", change: null, whole: false, problem, asks });
  if (part === "rib") return change("The chat changes the plies of the skin, the spar webs and the spar caps. The ribs are spaced evenly: set their spacing on the Geometry step.", false);
  if (part === "both") return change("One part at a time: the skin, the spar webs or the spar caps. Send each change as its own message.");
  if (part === null) return change("Which part: the skin, the spar webs or the spar caps? For example “add 2 0° plies to the spar caps”.");
  if (/±|\+\/-|plus or minus|plus-minus/.test(text)) {
    return change("One angle at a time: send “add 2 45° plies” and then “add 2 -45° plies”, so each change can be checked before the next.");
  }
  const found = text.match(COUNT_ANGLE) ?? text.match(COUNT_PLIES_AT);
  if (!found) return change(`How many plies, and at what angle? For example “${adds || !removes ? "add" : "remove"} 2 0° plies to ${PART_WORDS[part]} from the root to 40% span”.`);
  const count = countOf(found[1]), angle = angleOf(found[2]);
  if (!Number.isFinite(angle) || angle < -90 || angle > 180) return change(`${found[2]}° is not a ply angle: give one from −90° to 180°.`);
  if (count % 2) {
    return change(`${count} ${count === 1 ? "ply" : "plies"} cannot keep the laminate symmetric: plies go in pairs, one on each side of its middle (one on each face of a sandwich). Ask for ${count + 1}.`);
  }
  if (count > 40) return change(`${count} plies at once is more than the chat changes: 40 at most.`);
  const span = spanOf(text);
  if ("problem" in span) return change(span.problem);
  if (span.end - span.start < 1e-9) return change("The stretch is empty: say where it starts and where it ends, for example “from the root to 40% span”.");
  const placement = /\b(?:in|at|to) the (?:middle|centre|center|mid-?plane)\b|\bnext to the core\b|\bon the inside\b/.test(text) ? "middle" : "beside";
  return { route: "wing-change", whole: span.whole, problem: null, asks: false,
    change: { action: removes && !/\badd\b/.test(text) ? "remove_plies" : "add_plies", part, angle, count, start: span.start, end: span.end, placement } };
}

const RULE_WORDS: [WingRuleName, RegExp][] = [
  ["ten_percent", /\b(?:10|ten)\s*(?:%|percent|per cent)(?:\s*rule)?|\bpercentage rule\b|\beach direction\b/],
  ["in_a_row", /\bin a row\b|\bconsecutive\b|\bstack(?:ed)? together\b|\bgroup(?:ed|ing)?\b|\bcluster(?:ed|ing)?\b|\bblock(?:ed|ing)?\b|\bnext to each other\b/],
  ["balance", /\bbalanc/],
  ["symmetry", /\bsymmetr/],
  ["drop_ratio", /\bdrop(?:-?off)? ratio\b|\bramp\b|\btaper\b|\brun-?out\b|\bply drops?\b|\bdrop-?offs?\b/],
  ["drop_count", /\b(?:plies )?(?:end|ending|dropped|drop) at (?:one|a|the same) (?:place|station|point)\b|\bdropped at once\b|\bper drop\b/],
  ["drop_cover", /\b(?:cover|covering|outside|outer) ply\b/],
];

const RULE_PARTS: [WingPart, RegExp][] = [
  ["cap", /\b(?:spar[\s-]*caps?|caps?)\b/], ["spar", /\b(?:spar[\s-]*webs?|webs?)\b|\bspars?\b(?![\s-]*caps?)/], ["skin", /\bskins?\b/], ["rib", /\bribs?\b/],
];

function rulePart(text: string): WingPart | null {
  return RULE_PARTS.find(([, pattern]) => pattern.test(text))?.[0] ?? null;
}

/** How a message is answered on the wing's page: a change of plies previewed, a question of the results, the design rules or the strengths
 * answered from the report, a question of why, how or which test answered from the reference pages, a command, or "not read". */
export function readWingAsk(message: string): WingAsk {
  const text = plain(message);
  const change = changeOf(text);
  if (change) return change;
  if (/\b(?:step|cad)\b/.test(text) && /\b(?:export|download|save|get|give|make|send)\b/.test(text)) return { route: "wing-command", command: "step" };
  if (/\b(?:finite element|fe|fea) (?:check|model|run)\b|\bcheck (?:it )?with (?:the )?(?:finite element|fe)\b/.test(text) && /\b(?:run|start|check)\b/.test(text)) {
    return { route: "wing-command", command: "check" };
  }
  if (/\bastm\b|\btest methods?\b|\b(?:which|what) tests?\b|\bd\d{4}\b|\btested\b/.test(text)) return { route: "wing-reference", topic: null };
  // "what is a B-basis value?", "what does B-estimate mean?": a definition, from the pages; "what is the margin of the web?" is the wing's
  if (DEFINING.test(text) || /\bwhat does (?:a |an |the )?[\w\s-]+ mean\b/.test(text)) return { route: "wing-reference", topic: null };
  if (/\ballowables?\b|\b[ab][\s-]?basis\b|\bbasis\b|\bdesign values?\b|\bstrengths? (?:do|did|are|were) (?:you|we) us|\b(?:which|what) strengths?\b|\bmaterial (?:values|data|properties)\b/.test(text)) {
    return { route: "wing-strengths", part: rulePart(text) };
  }
  const rules = RULE_WORDS.filter(([, pattern]) => pattern.test(text)).map(([rule]) => rule);
  const allRules = /\bdesign rules?\b|\b(?:the|all) rules\b/.test(text);
  if (rules.length || allRules) {
    const limit = /^(?:what|how many|how much|how long|how steep|which)\b|\b(?:max(?:imum)?|min(?:imum)?|limit|should i use|allowed|can i)\b/.test(text)
      && !/^(?:does|do|is|are)\b|\b(?:meet|meets|pass|passes|satisf|comply|follow)/.test(text);
    return { route: "wing-rules", rules: rules.length ? rules : [...RULE_NAMES_CHECKED], part: rulePart(text), limit };
  }
  const yesNo = /^(?:does|do|is|are|will|would|can|did|has|have)\b/.test(text);
  const topic = topicOf(text);
  if (topic === "layup" && !/\bwhy\b/.test(text)) return { route: "wing-result", topic, yesNo, part: rulePart(text) };
  if (/\bwhy\b|\bhow (?:does|do|is|are|can|should)\b|\bexplain\b/.test(text)) return { route: "wing-reference", topic };
  if (topic) return { route: "wing-result", topic, yesNo };
  if (/\?$/.test(text) || /^(?:what|how|when|where|which|should)\b/.test(text)) return { route: "wing-reference", topic: null };
  return { route: "wing-unread" };
}

const DEFINING = /^(?:what's|whats|what is|what are)\s+(?:a |an )?(?:b-basis|a-basis|b-estimates?|allowables?|basis values?|design values?|ply drops?|run-?outs?|margins? of safety|buckling|shear flow|spar caps?|10 ?% rule|balance|symmetry)\b/;
const RULE_NAMES_CHECKED: WingRuleName[] = ["ten_percent", "in_a_row", "balance", "symmetry", "drop_count", "drop_ratio", "drop_cover"];

function topicOf(text: string): ResultTopic | null {
  if (/\blay-?ups?\b|\bstacking sequence\b|\bstacks?\b(?! together)|\bply angles\b|\bwhat plies\b|\bhow many plies (?:does|do|are|is)\b/.test(text)) return "layup";
  if (/\bdiverg/.test(text)) return "divergence";
  if (/\breversal\b/.test(text)) return "reversal";
  if (/\bfrequenc|\bnatural\b|\bvibrat|\bhz\b|\bmodes?\b/.test(text)) return "frequency";
  if (/\btwist/.test(text)) return "tip_twist";
  if (/\bdeflect|\bdisplace|\bhow (?:far|much) (?:does )?(?:it|the (?:tip|wing)) (?:bend|move)|\btip (?:moves|travel)/.test(text)) return "tip_deflection";
  if (/\bmass\b|\bweight\b|\bweigh(?:s)?\b|\bheavy\b|\bkg\b/.test(text)) return "mass";
  const web = /\b(?:spar[\s-]*webs?|webs?|spars?)\b/.test(text), skin = /\bskins?\b/.test(text);
  const buckling = /\bbuckl/.test(text), strength = /\bstrength\b|\bplies\b|\bply\b|\bfail(?:ure|s)?\b|\bbreak/.test(text);
  if (/\bwhich (?:part|check|member)\b|\bwhat (?:part|check) (?:fails|governs)\b|\bfails? first\b|\bgovern|\bcritical\b|\bweakest\b|\blowest margin\b|\bsmallest margin\b|\bworst\b/.test(text) && !web && !skin) {
    return "which";
  }
  if (web) return buckling ? "web buckling" : strength && !/\bmargin\b/.test(text) ? "spar plies" : "web";
  if (skin) return buckling ? "skin buckling" : strength && !/\bmargin\b/.test(text) ? "skin plies" : "skin";
  if (/\bmargins?\b|\bpass(?:es)?\b|\bfail(?:s)?\b|\bsafe\b|\bok(?:ay)?\b|\bhold(?:s)?\b|\bstrong enough\b|\bverdict\b/.test(text)) return "verdict";
  return null;
}

// --------------------------------------------------------------------------------------------------------- the page's answers

/** What the chat says: its kind, the answer as the heading, the lines under it (the basis first), and what it read. */
export type WingSaid = { kind: string; heading: string; lines: string[]; data: Record<string, unknown>; panel?: string };

const said = (kind: string, heading: string, lines: string[] = [], data: Record<string, unknown> = {}, panel?: string): WingSaid =>
  ({ kind, heading, lines, data, ...(panel ? { panel } : {}) });

/** The lowest ultimate margin of one check over every case run, with the case and where; null when nothing loads it. */
export function lowestOf(report: WingReport, check: WingCheckName): { margin: number; case: WingCase } | null {
  let best: { margin: number; case: WingCase } | null = null;
  for (const c of report.cases) {
    const m = c.checks[check]?.margin_ultimate;
    if (m !== null && m !== undefined && Number.isFinite(m) && (!best || m < best.margin)) best = { margin: m, case: c };
  }
  return best;
}

function caseWords(c: WingCase): string {
  return `case ${c.number} (${c.label})`;
}

function checkLine(report: WingReport, check: WingCheckName): string {
  const found = lowestOf(report, check);
  if (!found) return `${CHECK_WORDS[check]}: nothing loads it in the cases run.`;
  return `${CHECK_WORDS[check]} ${marginText(found.margin)}: ${whereWords(found.case.checks[check], report.units)}, ${caseWords(found.case)}.`;
}

const capital = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1);

/** The basis of every margin, in one line (criterion 5): ultimate load, the strengths' basis, the hand calculation. */
function basisLine(report: WingReport): string {
  const basis = strengthWords(report.material);
  return `At ultimate load${basis ? `, on ${basis}` : ""}, by the hand calculation of the ${report.cases.length} case${report.cases.length === 1 ? "" : "s"} run.`;
}

function resultAnswer(ask: Extract<WingAsk, { route: "wing-result" }>, report: WingReport): WingSaid {
  const u = report.units, d = report.design;
  if (!report.cases.length && ["verdict", "which", ...CHECK_NAMES, "skin", "web", "tip_deflection", "tip_twist"].includes(ask.topic)) {
    return said("none", "No case could run yet", ["Every case still needs a value: the list under the results says which."], {}, "wing-loads");
  }
  const g = report.governing;
  switch (ask.topic) {
    case "verdict": case "which": {
      const words = answerWords(report);
      if (!g) return said("none", words.verdict, [words.detail]);
      const check = report.cases.find((c) => c.number === g.case && c.altitude === g.altitude)?.checks[g.check];
      const member = check?.member ? capital(check.member) : CHECK_WORDS[g.check];
      const heading = ask.topic === "which" ? `${member} first: ${marginText(g.margin_ultimate)}`
        : `${report.passes ? "Yes" : "No"}: ${words.verdict.charAt(0).toLowerCase()}${words.verdict.slice(1)}`;
      return said("result", heading, [words.detail, basisLine(report)], { topic: ask.topic, check: g.check, margin: g.margin_ultimate });
    }
    case "skin": case "web": {
      const checks: WingCheckName[] = ask.topic === "skin" ? ["skin plies", "skin buckling"] : ["spar plies", "web buckling"];
      const found = checks.map((c) => ({ check: c, low: lowestOf(report, c) })).filter((x) => x.low);
      if (!found.length) return said("none", `Nothing loads the ${ask.topic === "skin" ? "skins" : "webs"} yet`);
      const low = found.reduce((a, b) => (b.low!.margin < a.low!.margin ? b : a));
      const name = ask.topic === "skin" ? "Skin" : "Web";
      const heading = ask.yesNo ? `${low.low!.margin >= 0 ? "Yes" : "No"}: ${name.toLowerCase()} margin ${marginText(low.low!.margin)}` : `${name}: lowest margin ${marginText(low.low!.margin)}`;
      return said("result", heading, [...checks.map((c) => checkLine(report, c)), basisLine(report)], { topic: ask.topic, check: low.check, margin: low.low!.margin });
    }
    case "skin plies": case "spar plies": case "skin buckling": case "web buckling": {
      const low = lowestOf(report, ask.topic);
      if (!low) return said("none", `${CHECK_WORDS[ask.topic]}: nothing loads it yet`);
      const heading = ask.yesNo ? `${low.margin >= 0 ? "Yes" : "No"}: ${CHECK_WORDS[ask.topic].toLowerCase()} ${marginText(low.margin)}` : `${CHECK_WORDS[ask.topic]}: ${marginText(low.margin)}`;
      return said("result", heading, [checkLine(report, ask.topic), basisLine(report)], { topic: ask.topic, check: ask.topic, margin: low.margin });
    }
    case "mass": {
      const parts = [`skins ${shown(d.mass_skins, 3)}`, ...(d.mass_caps ? [`spar caps ${shown(d.mass_caps, 3)}`] : []), `spar webs ${shown(d.mass_spars, 3)}`,
        ...(d.mass_core ? [`core ${shown(d.mass_core, 3)}`] : [])];
      return said("result", `${shown(d.mass)} ${unitText(u.mass)}, one side of the wing`,
        [`The box between the spars: ${parts.join(", ")} ${unitText(u.mass)}. Ribs, fittings and the parts ahead of and behind the box are not counted.`,
          "From the plies' and the core's density, by the hand calculation."], { topic: "mass", value: d.mass });
    }
    case "tip_deflection": case "tip_twist": {
      const key = ask.topic;
      const top = report.cases.reduce((a, b) => (Math.abs(b[key]) > Math.abs(a[key]) ? b : a));
      const unit = unitText(key === "tip_deflection" ? u.deflection : u.twist);
      const what = key === "tip_deflection" ? "Tip deflection" : "Tip twist";
      return said("result", `${what} ${shown(top[key])} ${unit}, ${`case ${top.number}`}`,
        [`The largest of the ${report.cases.length} cases run: ${caseWords(top)}, by the hand calculation.`], { topic: key, value: top[key], case: top.number });
    }
    case "frequency":
      return said("result", `First bending frequency ${shown(d.first_bending_frequency)} ${unitText(u.frequency)}`,
        ["One side of the wing, by the hand calculation. The finite element check works the vibration modes in full."], { topic: "frequency", value: d.first_bending_frequency });
    case "layup": return layupAnswer(null, null); // answered from the description, by wingAnswer
    case "divergence": case "reversal": {
      const a = report.aeroelastic;
      const speed = ask.topic === "divergence" ? a?.divergence_speed : a?.reversal_speed;
      const never = ask.topic === "divergence" ? a?.divergence_never : a?.reversal_never;
      const over = ask.topic === "divergence" ? a?.divergence_over_dive : a?.reversal_over_dive;
      const what = ask.topic === "divergence" ? "Divergence" : "Aileron reversal";
      if (!a || (speed === null && !never)) return said("none", `${what} not worked yet`, [a?.needs.length ? `It needs: ${a.needs.join(", ")}.` : "It needs the wing's aerodynamic values on the Loads step."], {}, "wing-loads");
      if (never) return said("result", `${what}: none at any speed`, ["By the hand calculation of the wing's stiffness and its aerodynamic values."], { topic: ask.topic });
      return said("result", `${what} at ${shown(speed)} ${unitText(u.speed)}`,
        [`${over !== null && over !== undefined ? `${shown(over)} times the dive speed` : "The dive speed is not set"}, by the hand calculation.`], { topic: ask.topic, value: speed });
    }
  }
}

/** What the wing's own report says of what a question of why names, so the reason is read beside the numbers it is about: the check's
 * lowest margin, and what governs when that is another check (criterion 6: "why does the web buckle first?" of a wing whose skin governs). */
function whyFacts(topic: ResultTopic, report: WingReport): string[] {
  const checks: WingCheckName[] = topic === "skin" ? ["skin plies", "skin buckling"] : topic === "web" ? ["spar plies", "web buckling"]
    : (CHECK_NAMES as readonly string[]).includes(topic) ? [topic as WingCheckName] : [];
  const g = report.governing;
  const lines = checks.map((c) => checkLine(report, c));
  if (g && (topic === "which" || topic === "verdict" || checks.length)) {
    lines.push(checks.includes(g.check) ? `${CHECK_WORDS[g.check]} governs this wing.` : `${CHECK_WORDS[g.check]} governs this wing, not ${checks.map((c) => CHECK_WORDS[c].toLowerCase()).join(" or ")}: ${marginText(g.margin_ultimate)}.`);
  }
  return lines;
}

const LAYUP_TABLES: [WingPart, string][] = [["skin", "skin"], ["spar", "spar"], ["cap", "spar_caps"], ["rib", "rib"]];

/** The layups of the wing as its description holds them: each part's laminate and its zones along the span, a sandwich with its core. */
function layupAnswer(part: WingPart | null, wing: WingDescription | null): WingSaid {
  if (!wing) return said("none", "The wing is being read", ["Ask again once its answer is shown."]);
  const stack = (value: unknown) => (Array.isArray(value) ? `[${value.join("/")}]s` : "–");
  const lines: string[] = [];
  let heading = "";
  for (const [name, table] of LAYUP_TABLES) {
    if (part !== null && name !== part) continue;
    const t = wing[table];
    if (typeof t !== "object" || t === null || Array.isArray(t)) continue;
    const zones = Array.isArray(t.zones) ? (t.zones as unknown as { start: number; end: number; half_stack: number[] }[]) : [];
    const core = typeof t.core === "string" || typeof t.core_thickness === "number";
    const label = capital(RULE_PART_WORDS[name].replace(/^the /, ""));
    const own = `${stack(t.half_stack)}${core ? ", each face of a sandwich round its core" : ""}`;
    lines.push(`${label}: ${own}${zones.length ? ", outside its zones" : ""}.`);
    for (const z of zones) lines.push(`${label}, ${spanText(z.start, z.end)}: ${stack(z.half_stack)}.`);
    if (!heading) heading = `${label}: ${stack(t.half_stack)}${zones.length ? ` and ${zones.length} zone${zones.length === 1 ? "" : "s"}` : ""}`;
  }
  if (!lines.length) return part === "cap" ? said("none", "No spar caps on this wing yet", ["Add them on the Layup step."], {}, "wing-layup")
    : said("none", "No such part on this wing");
  if (part === null) heading = "The wing's layups";
  return said("result", heading, [...lines, "Each is the outer half from the outside in; the other half mirrors it."], { topic: "layup", part }, "wing-layup");
}

function rulesAnswer(ask: Extract<WingAsk, { route: "wing-rules" }>, report: WingReport): WingSaid {
  const limits = report.rule_limits;
  const judged = report.rules.filter((r) => ask.rules.includes(r.rule) && (ask.part === null || r.part === ask.part));
  const where = (r: WingRule) => `${capital(RULE_PART_WORDS[r.part].replace(/^the /, ""))}${r.span && (r.span[0] > 1e-9 || r.span[1] < 1 - 1e-9) ? `, ${spanText(r.span[0], r.span[1])}` : ""}${r.at !== null ? `, at ${shown(100 * r.at, 3)} % of the half span` : ""}`;
  const unmet = judged.filter((r) => !r.met), metRules = judged.filter((r) => r.met);
  const lines = judged.length > 4
    ? [...unmet.map((r) => `${where(r)}: ${r.words}`), ...(metRules.length ? [`Met: the other ${metRules.length} judgement${metRules.length === 1 ? "" : "s"}, listed on the Layup step.`] : [])]
    : judged.map((r) => `${where(r)}: ${r.words}`);
  if (ask.limit) {
    const rule = ask.rules[0];
    const limit = rule === "ten_percent" ? `At least ${shown(limits.min_percent)} % of the plies in each direction`
      : rule === "in_a_row" ? `At most ${limits.max_in_a_row} plies of one angle in a row`
      : rule === "drop_ratio" ? `A run-out ${shown(limits.drop_ratio)} times the thickness dropped`
      : rule === "drop_count" ? `At most ${limits.max_dropped} plies ending at one place` : null;
    if (limit) {
      const missed = judged.filter((r) => !r.met);
      return said("rule-limit", limit, [
        `This wing's limit, set in the Design rules box of the Layup step and checked ${rule.startsWith("drop") ? "at every change of layup along the span" : "on every layup"}.`,
        judged.length ? (missed.length ? `Not met: ${[...new Set(missed.map(where))].join("; ")}.` : "Every layup of this wing meets it.") : "No ply drop on this wing yet: its layups do not change along the span.",
      ], { rules: ask.rules, limit: true }, "wing-layup");
    }
  }
  if (!judged.length) {
    const part = ask.part ? RULE_PART_WORDS[ask.part] : "this wing";
    if (ask.part === "cap") return said("none", "No spar caps on this wing yet", ["Add them on the Layup step; the rules then judge their layup too."], {}, "wing-layup");
    return said("none", `Nothing to judge on ${part.replace(/^the /, "")}`,
      [ask.rules.every((r) => r.startsWith("drop")) ? "A ply drop is where a layup changes along the span; this wing's layups do not change." : "The rules judge the layups of the skin, the spar webs, the spar caps and the ribs."]);
  }
  const met = judged.every((r) => r.met);
  const parts = [...new Set(judged.map((r) => r.part))];
  const named = ask.rules.filter((r) => judged.some((j) => j.rule === r));
  let heading: string;
  if (parts.length === 1) {
    const part = parts[0], plural = PLURAL[part];
    const failed = named.filter((r) => judged.some((j) => j.rule === r && !j.met));
    heading = met ? `Yes: ${RULE_PART_WORDS[part]} ${plural ? "meet" : "meets"} ${ruleList(named, limits)}`
      : `No: ${RULE_PART_WORDS[part]} ${plural ? "miss" : "misses"} ${ruleList(failed, limits)}`;
  } else {
    const missing = parts.filter((p) => judged.some((j) => j.part === p && !j.met));
    heading = met ? `Yes: every part meets ${ruleList(named, limits)}` : `No: ${missing.length} of ${parts.length} parts miss a rule`;
  }
  if (heading.length > 60) heading = met ? "Yes: every rule asked is met" : "No: not every rule asked is met";
  return said("rules", heading, [...lines, "A rule not met is a warning: no margin changes with it."], { rules: named, part: ask.part, met }, "wing-layup");
}

/** Rules as a heading names them: "the 10 % rule", "balance and symmetry". */
function ruleList(rules: WingRuleName[], limits: WingReport["rule_limits"]): string {
  const name = (r: WingRuleName) => (r === "ten_percent" ? `the ${ruleTitle(r, limits)}` : r === "balance" ? "balance" : r === "symmetry" ? "symmetry" : `the rule on ${ruleTitle(r, limits).toLowerCase()}`);
  const names = rules.map(name);
  return names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}` : names[0] ?? "the rules";
}

function spanText(start: number, end: number): string {
  const at = (f: number) => (f < 1e-9 ? "the root" : f > 1 - 1e-9 ? "the tip" : `${shown(100 * f, 3)} %`);
  return `from ${at(start)} to ${at(end)}`;
}

function strengthsAnswer(ask: Extract<WingAsk, { route: "wing-strengths" }>, report: WingReport): WingSaid {
  const m = report.material;
  if (!m) return said("none", "No strengths to show yet");
  const basis = m.strength_basis === "B-basis" ? "B-basis strengths" : m.strength_basis === "mean" ? "Test-mean strengths" : "The strengths typed in";
  const lines = m.strengths.map((s) => `${STRENGTH_LABELS[s.role] ?? s.role} ${shown(s.value)} ${unitText(report.units.stress)}${s.basis ? `, ${s.basis}` : ""}${s.page ? `, p. ${s.page}` : ""}`);
  if (ask.part) lines.unshift(`Every part uses the same ply material, so ${RULE_PART_WORDS[ask.part]} use these.`);
  if (m.estimates.length) lines.push(`${m.estimates.map((r) => (STRENGTH_LABELS[r] ?? r).toLowerCase()).join(" and ")}: B-estimates, since the report recommends no B-basis value for them.`.replace(/^./, (c) => c.toUpperCase()));
  if (m.strength_basis === "mean") lines.push("Test means are not design values: half of all production is weaker. Choose B-basis on the Material step for design.");
  if (m.source) lines.push(`From: ${m.source}${m.dataset ? ` (${m.dataset})` : ""}.`);
  return said("strengths", `${basis} of ${m.name}`, lines, { basis: m.strength_basis }, "wing-material");
}

/** The page's own answer to a message, from the engine's report: nothing here asks the API. A change is shown as read, before the API
 * previews it; a question of why answers with the reference pages the component fetches (`kind` "reference"). */
export function wingAnswer(ask: WingAsk, report: WingReport | null, wing: WingDescription | null = null): WingSaid {
  switch (ask.route) {
    case "wing-change":
      if (!ask.change) return said(ask.asks ? "ask" : "refused", ask.asks ? "One question" : "Not a change the chat makes", [ask.problem ?? ""]);
      return said("preview", "Preview of a change", [changeLine(ask.change, ask.whole)], { change: ask.change });
    case "wing-command":
      return ask.command === "step"
        ? said("said", "Download STEP is in Shape for CAD", ["It builds the wing's surfaces, every part named and cut where its layup changes."], { command: "step" }, "wing-shape")
        : said("said", "The finite element check is under the results", ["Start it there: it checks the wing as it stands, in the background."], { command: "check" });
    case "wing-reference":
      return said("reference", "Answered from our reference pages", report && ask.topic ? whyFacts(ask.topic, report) : [], { topic: ask.topic });
    case "wing-unread":
      return said("redirect", "Not a question I can read yet", ["Ask “which part fails first?”, “does the skin meet the 10% rule?” or “add 2 0° plies to the spar caps from the root to 40% span”."]);
    default:
      if (!report) return said("none", "The wing is being worked", ["Ask again once its answer is shown."]);
      if (ask.route === "wing-result") return ask.topic === "layup" ? layupAnswer(ask.part ?? null, wing) : resultAnswer(ask, report);
      if (ask.route === "wing-rules") return rulesAnswer(ask, report);
      return strengthsAnswer(ask, report);
  }
}

/** A change as the page read it, before the engine words it: what the engineer checks the reading by. */
export function changeLine(change: PlyChange, whole: boolean): string {
  const count = { 2: "Two", 4: "Four", 6: "Six", 8: "Eight", 10: "Ten", 12: "Twelve" }[change.count] ?? String(change.count);
  const angle = `${change.angle > 0 && change.angle !== 90 ? "+" : ""}${change.angle}°`.replace("-", "−");
  const verb = change.action === "add_plies" ? "added to" : "taken from";
  const tip = change.end > 1 - 1e-9, root = change.start < 1e-9;
  const span = whole ? "along the whole span (say a stretch to change only part of it)" : root && tip ? "along the whole span"
    : tip ? `from ${shown(100 * change.start, 3)} % of the half span to the tip` : `${spanText(change.start, change.end)} of the half span`;
  return `${count} ${angle} plies ${verb} ${PART_WORDS[change.part]} ${span}${change.placement === "middle" ? ", at the middle" : ""}.`;
}

/** Whether the wing has spar caps, so the page offers a change to them only then. */
export function hasSparCaps(wing: WingDescription): boolean {
  return typeof wing.spar_caps === "object" && wing.spar_caps !== null && !Array.isArray(wing.spar_caps);
}

/** A row of the preview's table: a quantity as it is and as changed, in the report's units. */
export type PreviewRow = { label: string; before: string; after: string; better: boolean | null };

export type WingSummary = {
  passes: boolean; governing: { case: number; label: string; check: WingCheckName; margin_ultimate: number | null } | null;
  lowest: Partial<Record<WingCheckName, number>>; mass: number; tip_deflection: number; first_bending_frequency: number;
};

/** The API's preview of a change (ADR-0128), as the page reads it. */
export type WingChangePreview = {
  run_id: string | null; engine_version: string; change: PlyChange; words: string; wing: WingDescription;
  before: WingSummary; after: WingSummary; units: Record<string, string>; rules: WingRule[];
};

/** The preview's table: the lowest margin, each check's lowest margin, the mass, the largest tip deflection and the first bending
 * frequency, before and after, each as the engine gave it; `better` says which way it moved for the wing (null: unchanged or no way). */
export function previewRows(p: WingChangePreview): PreviewRow[] {
  const u = p.units;
  const margin = (s: WingSummary) => s.governing?.margin_ultimate ?? null;
  const rows: PreviewRow[] = [{ label: "Lowest margin", before: marginText(margin(p.before)), after: marginText(margin(p.after)), better: moved(margin(p.before), margin(p.after), 1) }];
  for (const check of CHECK_NAMES) {
    const a = p.before.lowest[check] ?? null, b = p.after.lowest[check] ?? null;
    if (a === null && b === null) continue;
    rows.push({ label: CHECK_WORDS[check], before: marginText(a), after: marginText(b), better: moved(a, b, 1) });
  }
  rows.push({ label: `Mass, one side (${unitText(u.mass)})`, before: shown(p.before.mass), after: shown(p.after.mass), better: moved(p.before.mass, p.after.mass, -1) });
  rows.push({ label: `Largest tip deflection (${unitText(u.deflection)})`, before: shown(p.before.tip_deflection), after: shown(p.after.tip_deflection), better: moved(p.before.tip_deflection, p.after.tip_deflection, -1) });
  rows.push({ label: `First bending frequency (${unitText(u.frequency)})`, before: shown(p.before.first_bending_frequency), after: shown(p.after.first_bending_frequency), better: null });
  return rows;
}

function moved(before: number | null, after: number | null, good: 1 | -1): boolean | null {
  if (before === null || after === null || Math.abs(after - before) <= 1e-12 * Math.max(1, Math.abs(before))) return null;
  return (after - before) * good > 0;
}

/** The rules of the part changed that the change leaves unmet, in the page's sentence each. */
export function previewWarnings(p: WingChangePreview): string[] {
  return p.rules.filter((r) => !r.met).map((r) => `${capital(RULE_PART_WORDS[r.part].replace(/^the /, ""))}${r.at !== null ? ` at ${shown(100 * r.at, 3)} %` : r.span && (r.span[0] > 1e-9 || r.span[1] < 1 - 1e-9) ? `, ${spanText(r.span[0], r.span[1])}` : ""}: ${r.words}`);
}
