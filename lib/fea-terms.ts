/** The words an engineer sets up a finite element analysis with, in whichever program they learnt it, each said in our own words with
 * what Anisotropy does with it (ADR-0110, amendment 1). One term holds every program's name for the same thing, so "encastre" and
 * "fixed support", "seed" and "edge sizing", "set" and "named selection" are one answer. The assistant answers "what is a partition?"
 * or "what does a frictionless support mean?" from here: fixed words, no model, with or without a result. A request to add one ("add a
 * boundary condition") on a model whose setup fixes it is answered here too, and changes nothing.
 *
 * Nothing here is taken from a manual: the meanings are ours, written for this product. */

export type FeaTerm = {
  id: string;
  /** The heading of the answer. */
  title: string;
  /** Every way an engineer may write it, lower case. The first is the plain one. */
  names: string[];
  /** What it is, in one sentence. */
  means: string;
  /** What Anisotropy does with it, in one sentence. */
  here: string;
  /** A name that means one thing of several, said on its own: "U2 is the move along y." */
  exact?: Record<string, string>;
};

export const FEA_TERMS: FeaTerm[] = [
  { id: "boundary-condition", title: "Boundary condition", names: ["boundary condition", "boundary conditions", "bc", "bcs", "support", "supports", "constraint", "constraints", "restraint", "restraints", "displacement boundary condition", "displacement/rotation", "remote displacement", "displacement constraint"],
    means: "Holds part of the model still, or moves it by a set amount, in the directions you choose.",
    here: "A coupon's are set by its test: the bottom grip is fixed and the top grip moves along the coupon. Each is drawn on the model and listed under it." },
  { id: "load", title: "Load", names: ["load", "loads", "loading", "applied load"],
    means: "What makes the model deform: a force, a pressure, or a set travel of a boundary condition.",
    here: "A coupon is loaded at its top grip, by a travel or a force. The load is drawn as arrows on the model and listed under it." },
  { id: "degree-of-freedom", title: "Degree of freedom", names: ["degree of freedom", "degrees of freedom", "dof", "dofs", "u1", "u2", "u3", "ur1", "ur2", "ur3", "ux", "uy", "uz", "rotx", "roty", "rotz"],
    means: "One of six ways a point moves: along x, y and z (U1 to U3, or UX to UZ) and turning about them (UR1 to UR3, or ROTX to ROTZ).",
    here: "We say x, y, z, tilt about x, tilt about y and turn about z. A cone on the model marks each held move, a double cone each held turn.",
    exact: { u1: "U1 is the move along x.", u2: "U2 is the move along y.", u3: "U3 is the move along z.", ur1: "UR1 is the turn about x.",
      ur2: "UR2 is the turn about y.", ur3: "UR3 is the turn about z.", ux: "UX is the move along x.", uy: "UY is the move along y.",
      uz: "UZ is the move along z.", rotx: "ROTX is the turn about x.", roty: "ROTY is the turn about y.", rotz: "ROTZ is the turn about z." } },
  { id: "encastre", title: "Encastre", names: ["encastre", "encastré", "fully fixed", "built-in", "built in", "fixed support", "fixed supports", "clamped", "clamped support"],
    means: "A boundary condition that holds all six directions: no move and no turn.",
    here: "The coupon's bottom grip is encastre. On a plate, say “fix” or “clamp” an edge." },
  { id: "pinned", title: "Pinned", names: ["pinned", "pin support", "pinned support"],
    means: "A boundary condition that holds the three moves and leaves the turns free.",
    here: "On a plate, “pin the left edge” holds it in x, y and z." },
  { id: "symmetry", title: "Symmetry boundary condition", names: ["symmetry", "symmetry boundary condition", "xsymm", "ysymm", "zsymm", "symmetry plane", "plane of symmetry", "symmetry region"],
    means: "Holds a cut face as a mirror: the move across it and the two turns that would tilt it. XSYMM, YSYMM and ZSYMM name the face by its axis.",
    here: "On a plate, “XSYMM on the left edge” is read with exactly those directions. Our coupons are modelled whole, with no symmetry cut.",
    exact: { xsymm: "XSYMM holds a face as a mirror across x: it holds x and the turns about y and z.",
      ysymm: "YSYMM holds a face as a mirror across y: it holds y and the turns about x and z.",
      zsymm: "ZSYMM holds a face as a mirror across z: it holds z and the tilts about x and y." } },
  { id: "roller", title: "Roller", names: ["roller", "roller support", "rollers", "frictionless support", "frictionless supports"],
    means: "A boundary condition that holds one direction and lets the model slide in the others.",
    here: "Say which way it is held, for example “hold the right edge in z”, since a roller alone does not say." },
  { id: "concentrated-force", title: "Concentrated force", names: ["concentrated force", "concentrated load", "point load", "point force", "cf", "cf1", "cf2", "cf3", "remote force", "nodal force", "nodal forces"],
    means: "A force at a point, given by its parts along x, y and z: CF1, CF2 and CF3.",
    here: "A force here is the total over a region, along x, y or z. On a plate, “CF2 = 500 N on the top edge” is read as 500 N along y.",
    exact: { cf1: "CF1 is a concentrated force along x.", cf2: "CF2 is a concentrated force along y.", cf3: "CF3 is a concentrated force along z." } },
  { id: "pressure", title: "Pressure", names: ["pressure", "pressure load", "distributed load", "surface load"],
    means: "A force per area on a face, pressing into it when positive.",
    here: "On a plate, a pressure acts on the face and is drawn as arrows spread over it." },
  { id: "shell-edge-load", title: "Shell edge load", names: ["shell edge load", "edge load", "line load", "edge traction", "line pressure"],
    means: "A force per length along the edge of a shell.",
    here: "Read from an imported file. On a plate, give the total force on the edge instead." },
  { id: "partition", title: "Partition", names: ["partition", "partitions", "partitioning", "partition lines"],
    means: "A cut that splits a part into regions, so a load, a boundary condition, a material or a mesh setting can sit on just one of them.",
    here: "Our models come split already: a coupon into its grips and gauge section, a plate into its edges, face and hole. Name a region or click it." },
  { id: "set", title: "Set and surface", names: ["set", "sets", "node set", "element set", "surface", "surfaces", "region", "regions", "named selection", "named selections", "component", "components"],
    means: "A named group of nodes, elements or faces that a load or boundary condition is put on.",
    here: "We call them regions. An imported file's own sets and surfaces are read as they are." },
  { id: "section", title: "Section and layup", names: ["section", "sections", "shell section", "composite section", "composite layup", "layup", "lay-up", "stacking sequence", "modeling ply", "modeling plies", "ply group", "stackup"],
    means: "What a region is made of: for a composite shell, each ply's material, thickness and angle, listed from the bottom.",
    here: "The coupon's layup, such as [45/0/-45/90]s, with plies from the bottom face up." },
  { id: "section-point", title: "Section point", names: ["section point", "section points", "integration point", "integration points"],
    means: "A point through the thickness of a shell where stresses and strains are worked out.",
    here: "We give each ply's stresses and strains, in its fibre axes, at each element's centre." },
  { id: "material-orientation", title: "Material orientation", names: ["material orientation", "orientation", "material direction", "material directions", "fibre direction", "fiber direction", "local axes", "rosette", "rosettes", "oriented selection set", "element orientation"],
    means: "Which way the fibres run in each element; each ply's angle is measured from it.",
    here: "Angles are measured from the coupon's length, the way it is pulled, so a 0° ply runs along the load." },
  { id: "assembly", title: "Assembly and instance", names: ["assembly", "instance", "instances", "part instance", "part", "parts", "body", "bodies"],
    means: "A part is one shape; an instance is a placed copy of it, and the assembly holds every instance in one frame.",
    here: "Our coupons and plates are one part. Shapes and sizes of new parts belong to the CAD section, which is coming." },
  { id: "step", title: "Step", names: ["step", "steps", "analysis step", "initial step", "static step", "static, general", "linear perturbation", "static structural", "analysis settings", "load step", "load steps"],
    means: "A stage of the analysis in which boundary conditions and loads are switched on. The initial step holds only the fixed ones.",
    here: "One linear static step: every boundary condition and load is on at once. A second step is not offered yet." },
  { id: "interaction", title: "Interaction", names: ["interaction", "interactions", "contact", "tie", "tie constraint", "tied", "coupling", "coupling constraint", "kinematic coupling", "connection", "connections", "bonded contact", "joint", "joints"],
    means: "How two regions touch or are joined: contact, a tie that glues them, or a coupling to a reference point.",
    here: "Not offered yet: our models are one part, so nothing touches or is tied. An imported file's couplings are read." },
  { id: "seed", title: "Seed", names: ["seed", "seeds", "global seed", "global seeds", "mesh seed", "seeding", "global size", "approximate global size", "sizing", "mesh sizing", "body sizing", "face sizing", "edge sizing", "element sizing"],
    means: "Marks along the edges that set how fine the mesh is.",
    here: "Say the element size, for example “seed 2 mm”. Every run also checks the answer on a finer mesh." },
  { id: "element-type", title: "Element type", names: ["element type", "element types", "s4r", "s4", "s8r", "shell element", "shell elements", "shell181", "shell281"],
    means: "The kind of piece the mesh is made of, for example S4R, a four-node shell read at one point.",
    here: "We use our own four-node shell element, and every run checks the answer on a finer mesh." },
  { id: "job", title: "Job and data check", names: ["job", "jobs", "data check", "datacheck", "submit job", "job monitor", "solution", "solve"],
    means: "A job is one run of the model. A data check reads the model for mistakes without solving it.",
    here: "Check setup is our data check; Run solves it and checks the result with a second solver." },
  { id: "reaction-force", title: "Reaction force", names: ["reaction force", "reaction forces", "reaction", "reactions", "rf", "rf1", "rf2", "rf3", "force reaction", "force reactions"],
    means: "The force a boundary condition must take to hold the model as it is told.",
    here: "Shown with the results, at the grip that is held.",
    exact: { rf1: "RF1 is the reaction force along x.", rf2: "RF2 is the reaction force along y.", rf3: "RF3 is the reaction force along z." } },
];

const plain = (text: string) => text.toLowerCase().normalize("NFC").replace(/[’']/g, "'").replace(/\s+/g, " ").trim();
const BY_NAME = new Map(FEA_TERMS.flatMap((term) => term.names.map((name) => [plain(name), term] as const)));

/** A program named after the word ("encastre in Abaqus", "named selection in Ansys") is read off it: the word means the same here. */
const IN_PROGRAM = /\s+in (?:abaqus(?:\/cae)?|cae|ansys(?: mechanical| workbench)?|mechanical|workbench|calculix|nastran|femap|hypermesh)$/;

/** The term a whole phrase names, as written: "a boundary condition", "the BCs", "encastre in Abaqus". */
export function termNamed(phrase: string): FeaTerm | null {
  const t = plain(phrase).replace(/^(?:an?|the)\s+/, "").replace(IN_PROGRAM, "").replace(/[\s?.!]+$/, "");
  return BY_NAME.get(t) ?? null;
}

/** A term asked about: what it is, and whether the message asks about this model's own ("what are the boundary conditions?") rather
 * than the word ("what is a boundary condition?"). `name` is the name as written, for a term with an exact meaning of it. */
export type TermQuestion = { term: FeaTerm; name: string; ofModel: boolean };

const OWN = /^(?:the|this|my|our|its|these|those)\s+|\s+(?:here|on (?:this|the) (?:model|coupon|plate)|applied|used|on it)$/;
const ASKS: { pattern: RegExp; meaning: boolean }[] = [
  { pattern: /^\s*what does\s+(.+?)\s+mean\b.*$/i, meaning: true },
  { pattern: /^\s*(?:what is meant by|define|definition of|meaning of)\s+(.+?)\s*\??\s*$/i, meaning: true },
  { pattern: /^\s*(?:what(?:'s|’s| is| are)|explain|show(?: me)?|list)\s+(.+?)\s*\??\s*$/i, meaning: false },
  { pattern: /^\s*(.+?)\s*\?\s*$/, meaning: true }, // the word alone, asked: "encastre?"
];

/** The term a message asks about, or null. Only a whole phrase that is a term is read, so "what does the failure index mean?" stays a
 * question of why (ADR-0102) and "what is the stress at element 12?" stays a lookup (ADR-0099). "What is the reaction force?" asks for
 * this model's value, so it is left to the lookup too: of this model's own, only its boundary conditions and loads are answered here. */
export function termAsked(text: string): TermQuestion | null {
  for (const { pattern, meaning } of ASKS) {
    const found = pattern.exec(text);
    if (!found) continue;
    const phrase = plain(found[1]).replace(IN_PROGRAM, "");
    const ofModel = !meaning && OWN.test(phrase);
    const term = termNamed(phrase.replace(OWN, "").replace(OWN, ""));
    if (!term) continue;
    if (ofModel && !["boundary-condition", "load"].includes(term.id)) return null;
    if (!meaning && !ofModel && /^(?:show|list)\b/i.test(text)) return null; // "show load" asks for nothing we can show
    return { term, name: plain(phrase.replace(OWN, "").replace(OWN, "")).replace(/^(?:an?|the)\s+/, ""), ofModel };
  }
  return null;
}

/** What the answer to a question of a term says: its heading, what it is, and what Anisotropy does with it. */
export function termLines(question: TermQuestion): { title: string; means: string; here: string } {
  const exact = question.term.exact?.[question.name];
  return { title: exact ? question.name.toUpperCase() : question.term.title, means: exact ?? question.term.means, here: question.term.here };
}

/** The setup words a request to add one may open with, by the term they name. */
const ADDS = /^\s*(?:please\s+|can you\s+|could you\s+|i want to\s+|let'?s\s+)?(?:add|apply|create|put|place|define|insert|assign|set up|make)\s+(?:an?\s+|the\s+|some\s+|another\s+|new\s+|my\s+)?(.+?)\s*[.?!]*$/i;
const PARTITIONS = /^\s*(?:please\s+|can you\s+|could you\s+)?partition(?:s|ing)?\b/i;
const SETUP_TERMS = new Set(["boundary-condition", "load", "encastre", "pinned", "symmetry", "roller", "concentrated-force", "pressure", "shell-edge-load", "partition", "step", "interaction"]);

/** The term a request to add something to the setup names first ("add a boundary condition on the left edge", "apply a pressure",
 * "partition the plate", "create a step"), or null. The rest of the message (where, how much) is not read here. */
export function setupAsked(text: string): FeaTerm | null {
  if (PARTITIONS.test(text)) return FEA_TERMS.find((t) => t.id === "partition") ?? null;
  const found = ADDS.exec(text);
  if (!found) return null;
  const words = plain(found[1]).split(" ");
  for (let n = Math.min(words.length, 4); n >= 1; n -= 1) { // the longest name the request opens with: "boundary condition" before "boundary"
    const term = termNamed(words.slice(0, n).join(" "));
    if (term) return SETUP_TERMS.has(term.id) ? term : null;
  }
  return null;
}

/** A term that is a boundary condition or a load: on a plate these are read into its lists (ADR-0101), not explained. */
export const isConditionOrLoad = (term: FeaTerm): boolean =>
  ["boundary-condition", "load", "encastre", "pinned", "symmetry", "roller", "concentrated-force", "pressure", "shell-edge-load"].includes(term.id);
