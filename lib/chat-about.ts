import { LAYUP_CHOICES, layupNotation, nextStep, unitsNamed } from "./studio-chat";
import { libraryOptions, unitLabels, unitsOf, unitWords, type StudioForm } from "./studio-form";

/** Questions the chat answers in fixed words, with no model and no change to the setup (ADR-0121 amendment 2): who the assistant is and
 * what it does, the setup's units and whether another system is offered, whether a material of one's own can be used, which layup to
 * use, what a coupon needs, whether von Mises suits a composite ply, and another program named. The first real-model run of the question
 * banks (2026-11-20) found each of these answered "Not sure what to change", or read as a change: "can I use inches?" switched the units.
 * A value of the setup asked for ("what is the width?") is read from the setup's own rows (amendment 4). What a model file is, where the
 * report is, and a model brought in from a program whose files are not read here came from the real-model run of the downloads' questions
 * (ADR-0129 amendment 1). A key, a password or another person's work asked for is answered here too, before any model sees the message
 * (ADR-0139): none of them is on the page.
 *
 * Nothing here names a tool, a vendor or a model (ADR-0091), and nothing here is a number of a result. */

export type AboutTopic = "identity" | "abilities" | "instructions" | "other-program" | "units" | "units-other" | "own-material" | "layup-advice"
  | "needs" | "mises" | "setup-value" | "model-file-what" | "report" | "bring-in" | "others";

const IDENTITY = [
  /^\s*(?:who|what)\s+(?:are|r)\s+(?:you|u)\b/i,
  /^\s*who\s+(?:made|built|created|trained|wrote|makes|owns|programmed|designed)\s+(?:you|u|this|it)\b/i,
  /^\s*(?:are|r)\s+(?:you|u)\s+(?:an?\s+)?(?:chat\s*gpt|gpt|claude|gemini|copilot|grok|llama|ai|bot|chatbot|robot|human|person|real person|llm|language model|openai)\b/i,
  /^\s*(?:what|which)\s+(?:ai|llm|language model)\b/i,
  /^\s*(?:what|which)\s+model\s+(?:are\s+you|r\s+u|powers\s+you|is\s+this\s+chat)\b/i,
  /\b(?:powered|made|built)\s+by\s+(?:what|which|whom)\b/i,
];
const ABILITIES = [
  /^\s*what\s+(?:can|could)\s+(?:you|u|i|this)\s+(?:do|help(?:\s+me)?(?:\s+with)?|ask|answer)\b/i,
  /^\s*(?:what|how)\s+(?:do|does)\s+(?:you|this|it)\s+work\b/i,
  /^\s*how\s+(?:can|do|could)\s+(?:you|u)\s+help\b/i,
  /^\s*what\s+(?:are|r)\s+(?:you|u)\s+(?:for|able\s+to\s+do|capable\s+of|good\s+at)\b/i,
  /^\s*what\s+(?:questions|things|kinds?\s+of\s+(?:questions|things))\s+can\s+i\s+ask\b/i,
];
const INSTRUCTIONS = /\b(?:system\s+prompt|your\s+(?:instructions|prompt|rules|guidelines|configuration|initial\s+prompt)|(?:ignore|disregard|forget)\s+(?:all\s+|any\s+|the\s+|your\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|messages|prompts?|rules)|jailbreak|developer\s+mode)\b/i;
/** A key, a password or the hidden prompt asked for (ADR-0139): none of them is on the page, and none is said. */
const SECRETS = /\b(?:api[\s_-]*keys?|passwords?|credentials?|secret\s+keys?|(?:access|auth(?:entication)?|bearer)\s+tokens?|env(?:ironment)?\s+(?:variables?|vars?)|hidden\s+(?:prompt|instructions|rules))\b/i;
/** Another person's work asked for ("the runs of the other users", "what did the previous user ask"): this page holds only the engineer's own. */
const OTHERS = /\b(?:other|another|previous|last|earlier|different)\s+(?:users?|persons?|people|customers?|accounts?|sign-?ins?)\b|\b(?:someone|somebody|anyone|anybody)\s+else\b|\b(?:everyone|everybody)(?:'s|’s)|\ball\s+(?:the\s+)?users\b|\bwho\s+else\b|\bemails?\s+(?:address\s+)?of\b/i;
const PROGRAM = /\b(abaqus|ansys|nastran|femap|hypermesh|comsol|ls-?dyna|calculix|patran|optistruct|solidworks\s+simulation)\b/i;
const ASKS_TO_RUN = /^\s*(?:can|could|will|would|do|does|is|are)\b.*\b(?:run|solve|use|using|work|send|export|open|done)\b/i;
const UNITS = [
  /^\s*(?:what|which)\s+(?:units?|unit\s+system|system\s+of\s+units)\b/i,
  /^\s*(?:what|which)\s+(?:are|r)\s+(?:the|your|its)\s+units\b/i,
  /^\s*in\s+what\s+units\b/i,
  /^\s*units?\s*\??\s*$/i,
];
const CAN_USE = /^\s*(?:can|could|may)\s+(?:i|we|you)\s+(?:use|work|state|enter|give|type|have|put|do|switch|change|set)\b|^\s*(?:do|does)\s+(?:you|it|this)\s+(?:support|take|accept|do|work|handle|allow|read|understand)\b|^\s*is\s+(?:it|there)\s+(?:possible|a\s+way)\b|^\s*(?:are|is)\s+\S+(?:\s+\S+)?\s+(?:supported|allowed|ok|okay)\b/i;
const OWN_MATERIAL = /\b(?:my|our|own|custom|new|different|other)\s+(?:own\s+)?(?:materials?|prepregs?|fibres?|fibers?|resins?|properties)\b/i;
const OWN_ASKS = /^\s*(?:can|could|may|how|where|is\s+it\s+possible|do\s+you|does\s+it|what\s+if)\b/i;
const LAYUP = /\b(?:layups?|lay-ups?|stacking\s+sequences?|laminates?)\b/i;
const ADVICE = /\b(?:should|recommend\w*|suggest\w*|best|good|typical|common|usual|standard|advice|ideas?)\b/i;
const NEEDS = [
  /^\s*what\s+(?:do|does)\s+(?:i|you|we|it)\s+need\b/i,
  /^\s*what\s+(?:info|information|inputs?|data|details|values)\s+(?:do|does)\s+(?:you|it|i)\b/i,
  /^\s*how\s+do\s+i\s+(?:set\s*up|start|begin|make|create|build)\b/i,
  /^\s*what(?:'s|’s|\s+is)\s+needed\b/i,
  /^\s*where\s+do\s+i\s+(?:start|begin)\b/i,
];
/** What a model file is ("what is an Abaqus input file?", "whats a cdb"): a question about the file, not a request for it (ADR-0129 amendment 1). */
const FILE_WHAT = /^\s*what(?:'s|’s|s|\s+is|\s+are)\s+(?:an?\s+|the\s+|this\s+)?(?:(?:abaqus|abqus|ansys|apdl|solver)\s+)?(?:input\s+files?|\.?inp(?:\s+files?)?|\.?cdb(?:\s+files?)?|input\s+decks?|decks?|model\s+files?)\s*(?:for)?\s*\??\s*$/i;
/** The report asked for, or where it is ("download the report", "where is the pdf"). "report the stress in ply 3" asks for a value. */
const REPORT = /\b(?:the|a|my|this|its|pdf|full|final)\s+report\b|\breport\s+(?:pdf|file)\b|\bpdf\b/i;
const REPORT_ASKS = /\b(?:downloads?|donwload|dowload|downlod|downlaod|get|give|send|make|write|create|generate|print|save|export|need|want|find|see|open|where|how)\b|^\s*(?:is|can|could|do|does)\b/i;
/** A model brought in from a program whose files are not read here ("import an ansys model", "can I upload a nastran file?"). */
const BRING_IN = /\b(?:import\w*|upload\w*|bring\s+in|read\s+in|load)\b/i;
const NOT_READ_HERE = /\b(ansys|anssy|ansy|apdl|mapdl|workbench|nastran|femap|hypermesh|comsol|ls-?dyna|patran|optistruct|solidworks)\b|\.?\bcdb\b/i;
const MISES = /\b(?:von\s*-?\s*mis+es|mises|tresca)\b/i;
const MISES_ASKS = /^\s*(?:is|are|can|could|should|does|do|would|will)\b|\b(?:valid|apply|applies|applicable|ok|okay|suitable|appropriate|meaningful|good)\b.*\?\s*$/i;
/** The setup's rows a question may ask the value of, longest name first, as the engineer names them. */
const SETUP_ROWS: { key: string; name: string; words: string }[] = [
  { key: "ply_thickness", name: "Ply thickness", words: "ply\\s+thickness" },
  { key: "tab_length", name: "Tab length", words: "tab\\s+length|(?<=(?:the|its|my|our|this)\\s+)tabs?" }, // "what are tabs?" asks what they are
  { key: "element_size", name: "Element size", words: "(?:element|mesh)\\s+size" },
  { key: "thickness", name: "Thickness", words: "thickness" },
  { key: "width", name: "Width", words: "width" },
  { key: "length", name: "Length", words: "length" },
  { key: "layup", name: "Layup", words: "lay-?up|stacking\\s+sequence" },
  { key: "library", name: "Material", words: "material" },
];
const OF_IT = "(?:\\s+(?:of|on|for|in)\\s+(?:the\\s+|this\\s+|my\\s+|our\\s+)?(?:coupon|specimen|model|laminate|setup|it))?(?:\\s+(?:is\\s+|are\\s+)?(?:now|set\\s+to|here|used|it|this))?\\s*\\??\\s*$";
const SETUP_ASKED = SETUP_ROWS.map((row) => ({ ...row,
  asked: new RegExp(`^\\s*(?:what(?:'s|’s|s|\\s+is|\\s+was|\\s+are)?|which)\\s+(?:is\\s+)?(?:the\\s+|its\\s+|my\\s+|our\\s+|this\\s+)?(?:coupon'?s\\s+|specimen'?s\\s+)?(?:${row.words})${OF_IT}`, "i") }));
const HOW = /^\s*how\s+(wide|long|thick)\s+(?:is|are)\s+(?:it|the\s+(?:coupon|specimen|laminate|tabs?))\s*\??\s*$/i;
const HOW_ROW: Record<string, string> = { wide: "width", long: "length", thick: "thickness" };

/** The row of the setup a question asks the value of ("what is the width?", "how wide is it?"), or null. */
export function setupRowAsked(text: string): string | null {
  const how = HOW.exec(text);
  if (how) return /\btabs?\b/i.test(text) && how[1].toLowerCase() === "long" ? "tab_length" : HOW_ROW[how[1].toLowerCase()];
  return SETUP_ASKED.find((row) => row.asked.test(text))?.key ?? null;
}

/** The topic a message asks about, or null. A message with a value in it is a change, not a question of what is offered ("can I use
 * inches?" is asked; "use 0.5 in tabs" is not). On an imported model or a past run only what changes nothing of a setup is answered. */
export function aboutAsked(text: string, readOnly = false): AboutTopic | null {
  if (INSTRUCTIONS.test(text) || SECRETS.test(text)) return "instructions";
  if (OTHERS.test(text)) return "others";
  if (IDENTITY.some((p) => p.test(text))) return "identity";
  if (ABILITIES.some((p) => p.test(text))) return "abilities";
  if (FILE_WHAT.test(text)) return "model-file-what";
  if (BRING_IN.test(text) && NOT_READ_HERE.test(text) && !/\d/.test(text)) return "bring-in";
  if (REPORT.test(text) && REPORT_ASKS.test(text) && !/^\s*why\b/i.test(text) && !/\breport\s+(?:of|on|about)\b/i.test(text)) return "report";
  if (PROGRAM.test(text) && ASKS_TO_RUN.test(text) && !/\bimport/i.test(text)) return "other-program";
  if (MISES.test(text) && MISES_ASKS.test(text) && !/^\s*why\b/i.test(text)) return "mises";
  if (UNITS.some((p) => p.test(text))) return "units";
  if (readOnly) return null;
  if (setupRowAsked(text)) return "setup-value";
  if (unitsNamed(text) && CAN_USE.test(text) && !/\d/.test(text)) return "units-other";
  if (OWN_MATERIAL.test(text) && OWN_ASKS.test(text) && !/\d/.test(text)) return "own-material";
  if (LAYUP.test(text) && ADVICE.test(text) && !/\[/.test(text) && /^\s*(?:what|which|any|suggest|recommend|is|are|should|can|could|do)\b|\?\s*$/i.test(text)) return "layup-advice";
  if (NEEDS.some((p) => p.test(text))) return "needs";
  return null;
}

/** What the chat knows when it answers one. */
export type AboutContext = { form: StudioForm; results: boolean; readOnly: boolean };

/** The word "switch to …" takes for a system (`isSwitchRequest` reads each). */
const SWITCH_WORD: Record<string, string> = { "in-psi": "inches", "in-ksi": "ksi", "m-Pa": "metres", "mm-MPa": "millimetres" };

/** The answer: a heading that answers, and a line or two under it. Fixed words, the setup's own units, no number of a result. */
export function aboutAnswer(topic: AboutTopic, text: string, c: AboutContext): { title: string; lines: string[] } {
  const units = unitsOf(c.form);
  switch (topic) {
    case "identity":
      return { title: "Anisotropy's assistant", lines: [
        "I set up, check and explain composite analyses on this page. Every number I show is read from the analysis, never written by me."] };
    case "abilities":
      return c.results
        ? { title: "Ask about this result, or change it", lines: [
          "For example “which ply fails first?”, “stress in ply 3 at element 120”, “why does ply 4 fail first?” or “show the working”.",
          "To change the coupon, say it: “make it 35 mm wide”."] }
        : { title: "Set up, check and run a coupon", lines: [
          "Say what it is, for example “IM7/8552, [45/0/-45/90]s, 250 x 25 mm, 56 mm tabs”, then “check” and “run”.",
          "Ask what a word means too, for example “what is a boundary condition?”."] };
    case "instructions":
      return { title: "Not something I share", lines: [
        c.results ? "Ask about this result instead, for example “which ply fails first?” or “stress in ply 3 at element 120”."
          : "Ask about the setup instead, for example “is it ready to run?” or “what is a boundary condition?”."] };
    case "others":
      return { title: "Only your own work", lines: [
        "This chat sees the page you have open and nothing of anyone else's: no other person's analyses, questions or sign-in.",
        "Your own past analyses are under “Your analyses” on the start page."] };
    case "other-program": {
      const named = (PROGRAM.exec(text)?.[1] ?? "").toLowerCase();
      return { title: "Solved here", lines: [
        "Run solves the model on this page and checks the answer with a second solver, so no other program is needed.",
        ...(c.results && !c.readOnly && named === "abaqus"
          ? ["To compare with your own copy, use the card under the results: it sends this coupon there and reads its results back beside these."] : [])] };
    }
    case "model-file-what":
      return { title: "A text file that holds the whole model", lines: [
        "It states the mesh, the layup, the material, the supports and the loads in one program's own commands, so that program builds and solves the same model.",
        "To get this model as one, say “download the model”."] };
    case "report":
      return { title: "The report is under Files", lines: [
        "After a run, Files beneath the results lists “Report (PDF)”. If it is not written yet, pressing it writes it in about half a minute.",
        ...(c.results ? [] : ["There is no result yet: say “run” first."])] };
    case "bring-in": {
      const ansys = /\b(?:ansys|anssy|ansy|apdl|mapdl|workbench)\b|\.?\bcdb\b/i.test(text);
      return { title: ansys ? "An Ansys model cannot be brought in yet" : "A model from that program cannot be brought in yet", lines: [
        ...(c.readOnly ? [] : ["Set the coupon up here instead, for example “IM7/8552, [45/0/-45/90]s, 250 x 25 mm, 56 mm tabs”.",
          "The other way works: say “download the model” for a file your own program opens."])] };
    }
    case "mises":
      return { title: "No, not for a composite ply", lines: [
        "Von Mises and Tresca suit a metal, which yields the same way in every direction; a ply is many times stronger along its fibres than across them.",
        "Each ply is judged by maximum stress, Tsai-Hill or Tsai-Wu against its own strengths. Von Mises is shown for comparison only."] };
    case "units": {
      const lab = unitLabels(units);
      const other = units === "in-psi" || units === "in-ksi" ? "mm-MPa" : "in-psi";
      return { title: unitWords(units), lines: [
        `Lengths in ${lab.length}, stresses in ${lab.stress}, forces in ${lab.force}, moduli in ${lab.modulus}.`,
        `Say “switch to ${SWITCH_WORD[other]}” for ${unitWords(other)}.`] };
    }
    case "units-other": {
      const named = unitsNamed(text)!;
      if (named === units) return { title: `Yes: it is in ${unitWords(units)} now`, lines: [] };
      return { title: `Yes: ${unitWords(named)}`, lines: [
        `Say “switch to ${SWITCH_WORD[named]}”. Sizes already given are cleared, since nothing is converted.`] };
    }
    case "own-material":
      return { title: "Yes, your own material", lines: [
        "Under Material, choose “My own material…” and give its stiffnesses E1, E2 and G12, its Poisson's ratio ν12, the ply thickness and where the numbers come from.",
        "Add its five strengths to check failure."] };
    case "layup-advice":
      return { title: "The layup is your choice", lines: [
        `Common ones: ${LAYUP_CHOICES.map((l) => `${l.title.toLowerCase().replace(/ \(shear\)$/, "")} ${l.notation}`).join(", ")}.`,
        "Say one, or type your own."] };
    case "setup-value": {
      const key = setupRowAsked(text)!;
      const name = SETUP_ROWS.find((row) => row.key === key)!.name;
      const material = c.form.library ? libraryOptions.find((m) => m.id === c.form.library)?.name ?? c.form.library : c.form.own_E1?.trim() ? "your own material" : "";
      const value = key === "layup" ? layupNotation(c.form) : key === "library" ? material
        : c.form[key]?.trim() ? `${c.form[key].trim()} ${unitLabels(units).length}` : "";
      return value
        ? { title: `${name}: ${value}`, lines: [`From the setup. Say a new ${name.toLowerCase()} to change it.`] }
        : { title: `No ${name.toLowerCase()} yet`, lines: [`Say one to set it.`] };
    }
    case "needs":
      return { title: "A material, a layup, a size and a load", lines: [
        "For example “IM7/8552, [45/0/-45/90]s, 250 x 25 mm, 56 mm tabs, pull 1 mm”.",
        nextStep(c.form, true) === "review" ? "Yours has them all: say “check”, then “run”." : "Give them in any order; I ask for whatever is still missing."] };
  }
}

/** The heading of a setup check (ADR-0121 amendment 2): asked whether it is ready ("is my setup ok?"), it opens with Yes or No. */
export function checkTitle(ready: boolean, toFix: number, asked: boolean): string {
  const fix = `${toFix} thing${toFix === 1 ? "" : "s"} to fix before running`;
  if (!asked) return ready ? "Ready to run" : fix;
  return ready ? "Yes, ready to run" : `No: ${fix}`;
}

/** What a question nothing could read is told: what can be asked here, with results on the page or not. */
export function unreadWords(results: boolean): { title: string; text: string } {
  return results
    ? { title: "Not a question I can read yet", text: "Ask for a quantity and a place: “stress in ply 3 at element 120”, “strain here” after clicking an element, or “where is the shear stress highest?”." }
    : { title: "Not a question I can answer yet", text: "Ask “is it ready to run?”, “what units?” or “what is a boundary condition?”, or say a change, for example “[0/90]2s” or “10 kN”." };
}
