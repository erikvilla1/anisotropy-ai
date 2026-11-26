import type { Fields } from "./studio-api";
import { FOLLOWED_WORDS, followsShape, PLATE_TEST, type StudioForm } from "./studio-form";

/** The Analysis step's switch by talking (ADR-0142): "turn on nonlinear geometry", "nlgeom off", "make it linear", "is nonlinear geometry
 * on?", "should I use large deflection?". The page's own patterns read it, so the switch is set at once, with no model to wait for, and
 * a question of it changes nothing. Every number in an answer is read from the result on the page. */

/** What a message asks of the switch: to set it, whether it is set, or whether it should be. */
export type FollowedAsk = "on" | "off" | "is-on" | "is-linear" | "advice" | "scales" | "level";

const NOT = String.raw`non[-\s]?lin(?:ea|ae|e|a)r`; // "nonlinear", "non-linear", "non linear", and the ways it is mistyped
/** What ends a message after the word that matters: "make it linear again, please." */
const ENDS = String.raw`(?=\s*,?\s*(?:(?:again|only|please|instead|now)\s*,?\s*){0,2}[.!?]*\s*$)`;
/** Every way the switch is named: ours, another program's keyword, and the textbook's words for what it does. "Nonlinear" alone names
 * it only before a word for the solve or at the end ("make it nonlinear"), so "the nonlinear answer" names a result, not the switch. */
const NAME = String.raw`(?:${NOT}\s+geom(?:etry|etri|tery|erty|trey)|geometric(?:al)?\s+${NOT}ity|geometrically\s+${NOT}|nl[-\s]?geom|large[-\s](?:displacement|deflection|deformation|rotation)s?(?:\s+(?:theory|effects?|analysis))?|${NOT}(?:\s+(?:analysis|solve|solution|step|run|statics?)\b|${ENDS}))`;
/** A linear solve named, never the "linear" inside "nonlinear", nor a linear anything else ("linear elastic", "linear elements"). */
const LINEAR = String.raw`(?<!non[-\s]?)\blinear(?:\s+(?:analysis|solve|solution|step|run|statics?|geometry|one)\b|${ENDS})`;
const THE = String.raw`(?:the\s+|a\s+|an\s+)?`;
const IT = String.raw`(?:it|this|that|the\s+(?:plate|model|analysis|step|solve|run))`;
const TURN = String.raw`(?:t(?:ur|ru)n|sw(?:it|ti|i)ch|put|take)`;
const any = (...patterns: string[]) => new RegExp(patterns.map((p) => `(?:${p})`).join("|"), "i");

const OFF = any(
  String.raw`\b${TURN}\s+(?:off\s+${THE}${NAME}|${THE}${NAME}\s+(?:back\s+)?off)`,
  String.raw`\b(?:disable|deactivate|remove|drop|skip|ignore|without|no|stop\s+using)\s+${THE}${NAME}`,
  String.raw`\b(?:do\s+not|don['’]?t|never|not)\s+(?:\w+\s+){0,2}${THE}${NAME}`,
  String.raw`\b${NAME}\s*(?:[:=]\s*|\s+(?:to\s+|is\s+)?)(?:off|no|false|disabled)\b`,
  String.raw`\b(?:make|run|solve|keep|do)\s+${IT}\s+(?:as\s+)?${THE}${LINEAR}`,
  String.raw`\b(?:back|return|switch|change|go)\s+(?:back\s+|it\s+)?to\s+${THE}${LINEAR}`,
  String.raw`\b(?:use|want|run|do)\s+${THE}${LINEAR}`,
  String.raw`^\s*${LINEAR}`,
);
const ON = any(
  String.raw`\b${TURN}\s+(?:on\s+${THE}${NAME}|${THE}${NAME}\s+(?:back\s+)?on)`,
  String.raw`\b(?:enable|activate|use|include|add|apply|allow|consider|want|need|account\s+for|try)\s+${THE}${NAME}`,
  String.raw`\b${NAME}\s*(?:[:=]\s*|\s+(?:to\s+|is\s+)?)(?:on|yes|true|enabled|active)\b`,
  String.raw`\b(?:make|run|solve|do)\s+${IT}\s+(?:as\s+|with\s+)?${THE}${NAME}`,
  String.raw`\b(?:run|solve|rerun|re-run|repeat|redo)\s+(?:\w+\s+){0,2}with\s+${THE}${NAME}`,
  String.raw`^\s*(?:and\s+|now\s+|again\s+)?with\s+${THE}${NAME}`,
  String.raw`\bfollow\s+(?:the\s+|its\s+)?(?:plate['’]?s\s+)?(?:deformed\s+)?shape\b`,
  String.raw`^\s*${NAME}\s*(?:please)?\s*[.!]*\s*$`,
);
const NAMED = new RegExp(String.raw`\b${NAME}`, "i");
const LINEAR_NAMED = new RegExp(LINEAR, "i");
const ADVICE = /^\s*(?:should|shall|would|when|do\s+(?:i|we|you)\s+(?:need|have|want)|does\s+(?:it|this|the\s+\w+)\s+need|is\s+it\s+worth|is\s+there\s+(?:a|any)\s+(?:need|point|reason)|will\s+it\s+(?:matter|change|help))\b/i;
const STATE = /^\s*(?:is|are|was|were|does|did|do|has|have|will)\b/i;

/** Whether the answer scales with the load: "if I double the pressure does the stress double?", "does it scale with the load?". */
const LOAD = String.raw`(?:the\s+|my\s+)?(?:applied\s+)?(?:load(?:ing|s)?|pressure|force|displacement|travel)`;
const SCALES = any(
  String.raw`\b(?:doubl\w*|twice|tripl\w*|halv\w*)\s+${LOAD}\b`, String.raw`\b${LOAD}\s+(?:is\s+|were\s+|was\s+)?(?:doubled|halved|tripled)\b`,
  String.raw`\bscal\w*\s+(?:linearly\s+)?with\s+${LOAD}\b`, String.raw`\bproportional\s+to\s+${LOAD}\b`,
);
/** A share of the load a followed plate's deflection is asked at: "at half the load", "at 50 % of the load", "at 30%". */
const OF_LOAD = String.raw`\s+(?:of\s+)?(?:the\s+)?(?:applied\s+)?(?:load(?:ing)?|pressure|force)\b`;
const LEVEL = new RegExp(String.raw`\b(?:at|for|under)\s+(?:(half)${OF_LOAD}|(a\s+quarter)${OF_LOAD}|(\d+(?:\.\d+)?)\s*(?:%|percent|per\s+cent)(?:${OF_LOAD})?)`, "i");
const MOVES = /\b(?:deflection|displacement|deflect\w*|moves?|sag\w*)\b/i;

/** The share of the load a message names, or null. */
export function levelAsked(text: string): number | null {
  const found = LEVEL.exec(text);
  if (!found || !MOVES.test(text)) return null;
  return found[1] ? 0.5 : found[2] ? 0.25 : Number(found[3]) / 100;
}

/** What a message asks of the switch, or null. `question` says the message asks rather than tells (`isQuestion` of the chat's routes):
 * a question never sets the switch. `followed` says the result on the page is a followed one, whose deflection at a share of the load
 * can be read. "What is nonlinear geometry?" is the glossary's, read before this. */
export function followedAsked(text: string, question: boolean, followed = false): FollowedAsk | null {
  const named = NAMED.test(text);
  if (question) {
    if (SCALES.test(text)) return "scales";
    if (followed && levelAsked(text) !== null) return "level";
    if (!named && !LINEAR_NAMED.test(text)) return null;
    if (ADVICE.test(text)) return named ? "advice" : null;
    if (STATE.test(text)) return named ? "is-on" : "is-linear";
    return null;
  }
  if (OFF.test(text)) return "off";
  if (ON.test(text)) return "on";
  return null;
}

/** What the chat answers, and what the switch becomes (null when the message changes nothing). */
export type FollowedAnswer = { title: string; lines: string[]; set: boolean | null; problem?: boolean };

/** A share of the thickness, in two figures: "3.2 times" or "0.12 of". */
const share = (ratio: number): string => (ratio >= 1 ? `${Number(ratio.toPrecision(2))} times` : `${Number(ratio.toPrecision(2))} of`);
const HOW = "Say “turn on nonlinear geometry”, or tick it in the Analysis step.";

export function followedAnswer(ask: FollowedAsk, form: StudioForm, fields: Fields | null, print: (value: number) => string, text = ""): FollowedAnswer {
  const plate = form.test === PLATE_TEST, on = followsShape(form);
  if (ask === "scales") { // whether the answer scales with the load: yes for a linear solve, no once the shape is followed
    return plate && on ? { title: "No: with nonlinear geometry it does not scale", set: null,
      lines: ["The plate stiffens as it deflects, so doubling the load does not double a displacement or a stress. Change the load and run again for its answer."] }
      : { title: "Yes: the solve is linear", lines: ["Every displacement and stress scales with the load, and the failure index with it."], set: null };
  }
  if (ask === "level") {
    const curve = fields?.summary.followed, asked = levelAsked(text);
    if (!fields || !curve || asked === null) return { title: "No load levels in this result", lines: ["A run with nonlinear geometry keeps the deflection at every load level."], set: null };
    const unit = curve.curve.unit, node = curve.curve.label.split(".").pop();
    const at = curve.fractions.findIndex((f) => Math.abs(f - asked) < 1e-9);
    const percent = (f: number) => `${Number((100 * f).toPrecision(3))} %`;
    if (at >= 0) return { title: `${print(Math.abs(curve.curve.values[at]))} ${unit} at ${percent(asked)} of the load`, set: null,
      lines: [`The displacement at node ${node}, where it is largest at the full load, with nonlinear geometry. A linear solve gives ${print(Math.abs(curve.curve.linear[at]))} ${unit} there.`] };
    const near = curve.fractions.map((f, i) => ({ f, i })).sort((a, b) => Math.abs(a.f - asked) - Math.abs(b.f - asked)).slice(0, 2).sort((a, b) => a.f - b.f);
    return { title: `No load level at ${percent(asked)}`, set: null,
      lines: [`The load rose in ${curve.fractions.length} levels. The nearest are ${near.map(({ f, i }) => `${percent(f)} (${print(Math.abs(curve.curve.values[i]))} ${unit})`).join(" and ")}, at node ${node}.`] };
  }
  if (!plate) { // a coupon pulled along its length has no switch, said in one line with why
    if (ask === "on" || ask === "advice") return { title: ask === "on" ? "Not applied" : "No: not on a coupon", lines: [FOLLOWED_WORDS.coupon], set: null, problem: ask === "on" };
    if (ask === "off") return { title: "The solve is already linear", lines: [FOLLOWED_WORDS.off], set: null };
    return { title: ask === "is-on" ? "No, the solve is linear" : "Yes, the solve is linear", lines: [FOLLOWED_WORDS.off, FOLLOWED_WORDS.coupon], set: null };
  }
  switch (ask) {
    case "on": return on ? { title: "Nonlinear geometry is already on", lines: [FOLLOWED_WORDS.on], set: null }
      : { title: "Nonlinear geometry is on", lines: [FOLLOWED_WORDS.on], set: true };
    case "off": return on ? { title: "Nonlinear geometry is off", lines: [FOLLOWED_WORDS.off], set: false }
      : { title: "The solve is already linear", lines: [FOLLOWED_WORDS.off], set: null };
    case "is-on": return { title: on ? "Yes, nonlinear geometry is on" : "No, the solve is linear", lines: [on ? FOLLOWED_WORDS.on : FOLLOWED_WORDS.off, ...(on ? [] : [HOW])], set: null };
    case "is-linear": return { title: on ? "No, nonlinear geometry is on" : "Yes, the solve is linear", lines: [on ? FOLLOWED_WORDS.on : FOLLOWED_WORDS.off], set: null };
    case "advice": {
      const unit = fields?.labels.length ?? "";
      const followed = fields?.summary.followed ?? null;
      if (fields && followed) { // the result on the page is a followed one: what following the shape changed
        const linear = followed.linear;
        const changed = linear.change_percent !== null && linear.change ? `${print(linear.change_percent)} % ${linear.change} than` : "the same as";
        return { title: "It is on, and this result has it", set: null,
          lines: [`Largest displacement ${print(fields.summary.max_displacement.value)} ${unit}, ${changed} the ${print(Math.abs(linear.largest))} ${unit} of a linear solve of the same plate.`] };
      }
      const deflection = fields?.summary.deflection ?? null;
      if (deflection) { // a linear result on the page: how far it leaves its plane against its thickness, both the package's
        const yes = deflection.past_linear;
        return { title: `${yes ? "Yes" : "No"}: it deflects ${share(deflection.ratio)} its thickness`, set: null,
          lines: [`Largest displacement out of its plane ${print(deflection.value)} ${unit}, thickness ${print(deflection.thickness)} ${unit}, in the linear result on the page.`,
            yes ? "Past about half the thickness the stretch of the plate's middle carries part of the load, and a linear solve overstates the deflection."
              : "Below about half the thickness a linear solve holds.",
            ...(yes && !on ? [HOW] : [])] };
      }
      return { title: "When it deflects more than about half its thickness", set: null,
        lines: ["The stretch of the plate's middle then carries part of the load, and a linear solve overstates the deflection.",
          on ? "It is on now." : "It is off now: run the analysis, then ask again, and the deflection is compared with the thickness."] };
    }
  }
}
