import type { ModelProgram } from "./studio-api";

/** A request for the model as a file for the engineer's own program (ADR-0129): "download abaqus model", "export to Ansys", "give me the
 * inp", "can I get this as an ansys file?". The chat answers with the same buttons the model's own "Download model" menu holds; the
 * file is the fea package's, written from the rows as they stand. Nothing here reads a row or a number.
 *
 * Not a request: bringing a model in ("import an ansys model"), running elsewhere ("can you run it in ansys?"), sending the coupon to
 * the engineer's own Abaqus (the card under the results), a question about a file ("what is an input file?"), and the report. */

const NAMED: [ModelProgram, RegExp][] = [
  ["abaqus", /\b(?:abaqus|abqus|abacus)\b|\.?\binp\b/i],
  ["ansys", /\b(?:ansys|anssy|ansy|anys|apdl|mapdl|workbench)\b|\.?\bcdb\b/i],
];
/** The program a message names, or null when it names none or both. */
export function programNamed(text: string): ModelProgram | null {
  const named = NAMED.filter(([, pattern]) => pattern.test(text)).map(([program]) => program);
  return named.length === 1 ? named[0] : null;
}

const DOWNLOAD = /\b(?:downloads?|downloading|donwload|dowload|downlod|downlaod|dwnload|exports?|exporting|exprot)\b/i;
const GET = /\b(?:give|get|send|write|make|create|generate|produce|output|need|want|save)\b/i;
const MODEL = /\b(?:models?|modle|mdoel|decks?|mesh|input(?:\s+files?)?)\b/i;
const FILE = /\b(?:files?|models?|modle|mdoel|decks?|inputs?|inp|cdb|mesh|version|format)\b/i;
const OTHER_WAY = /\b(?:import\w*|upload\w*|bring|read|open|load|run|solve|compare)\b/i; // a file coming in, or work done elsewhere
const BARE = /^\s*(?:the\s+|an?\s+)?(?:abaqus|ansys)\s+(?:model|file|deck|input(?:\s+file)?|version)\s*(?:please|pls|plz)?\s*[?.!]*\s*$/i;
const BARE_FILE = /^\s*(?:the\s+)?\.?(?:inp|cdb)(?:\s+file)?\s*(?:please|pls|plz)?\s*[?.!]*\s*$/i;
const WHAT_IS = /^\s*(?:what|why|how|where|which|when|who)\b/i; // a question about a file is not a request for one, unless it asks how to get it
const OPEN_THERE = /\b(?:open|use|take|have)\s+(?:this|it|that|the\s+(?:model|coupon|plate)|my\s+(?:model|coupon|plate))\s+(?:in|into|to|for|with)\b/i; // "can I open this in Ansys?"
const INPUT_FILE = /\binput\s+files?\b|\bdecks?\b/i;
const HOW_TO_GET = /^\s*how\s+(?:do|can|could|would)\s+(?:i|we|you)\s+(?:get|download|export|save)\b|^\s*where\s+(?:do|can)\s+(?:i|we)\s+(?:get|download|find)\b/i;

/** Whether a message asks for the model as a file, and for which program (null: none named, or both). Null when it asks nothing of the kind. */
export function modelFileAsked(text: string): { program: ModelProgram | null } | null {
  if (WHAT_IS.test(text) && !HOW_TO_GET.test(text)) return null;
  const named = NAMED.some(([, pattern]) => pattern.test(text));
  const program = programNamed(text);
  if (BARE.test(text) || BARE_FILE.test(text)) return { program };
  if (DOWNLOAD.test(text) && (named || MODEL.test(text)) && !/\bimport\w*|\bupload\w*/i.test(text)) return { program };
  if (named && OPEN_THERE.test(text) && !/\bimport\w*|\bupload\w*|\brun\b|\bsolve\b/i.test(text)) return { program };
  if (named && GET.test(text) && FILE.test(text) && !OTHER_WAY.test(text)) return { program };
  if (GET.test(text) && INPUT_FILE.test(text) && !OTHER_WAY.test(text)) return { program };
  if (HOW_TO_GET.test(text) && (named || MODEL.test(text))) return { program };
  return null;
}

/** What the chat knows when it answers one. */
export type ModelFileContext = {
  /** The Ansys file is offered to this visitor (`Offered.ansysModel`). */
  ansys: boolean;
  /** An imported model or a past run has the stage: its rows are not the setup's. */
  readOnly: boolean;
};
/** The answer: a heading, its lines, and the files offered as buttons, in order. Every word is the product's (ADR-0091): a program is
 * named only as the engineer's own, in the name of the file that opens in it. */
export type ModelFileAnswer = { title: string; lines: string[]; offers: ModelProgram[] };

export function modelFileAnswer(program: ModelProgram | null, c: ModelFileContext): ModelFileAnswer {
  if (c.readOnly) {
    return { title: "Set up a coupon to download its model", offers: [],
      lines: ["The file is written from the inputs of a coupon set up here, so it is not offered for an imported model or a past run yet."] };
  }
  if (program === "ansys" && !c.ansys) {
    return { title: "Not as an Ansys file yet", offers: ["abaqus"],
      lines: ["The Ansys file is not offered yet.", "Today the model downloads as the file below."] };
  }
  const offers: ModelProgram[] = program ? [program] : c.ansys ? ["abaqus", "ansys"] : ["abaqus"];
  return { title: "Download the model", offers,
    lines: ["The model as it is set up now: the mesh, the layup, the material, the supports and the loads, ready to run in your own copy of the program.",
      ...(offers.includes("ansys") ? ["Compare the Ansys file's reaction with the one shown here before relying on it."] : [])] };
}
