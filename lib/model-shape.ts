/** The model's shape as a STEP file for a CAD program (ADR-0146): what the "Download model" menu offers beside the files for a solver,
 * and how the page states what the file cannot hold. Each part is one solid at its thickness, so the layup comes as a part table with
 * the file, and the page prints it. Every value is the fea package's; nothing here computes one. */
import { formatNumber } from "./number-format";
import type { ModelProgram } from "./studio-api";

/** What "Download model" saves: a file for the engineer's own solver (ADR-0129), or the shape for a CAD program. */
export type ModelDownload = ModelProgram | "step";
export const STEP_FILE = "step" as const;

/** One solid of the STEP file, as the API states it: lengths in `units.length` of the table, `plies` and `layup` null for a part of one
 * material, `in_model` false for a part the analysis does not carry as material (a bonded tab). */
export type ShapePart = {
  name: string; kind: string; layup: string | null; plies: number | null; ply_thickness: number | null; thickness: number;
  material: string | null; volume: number; in_model: boolean;
};
export type ShapeParts = { title: string; units: { length: string; volume: string; step: string }; parts: ShapePart[] };

/** The files the menu offers, in its order: the solver files this visitor is offered, then the shape, which is everyone's. */
export function modelDownloadsOffered(programs: ModelProgram[]): ModelDownload[] {
  return [...programs, STEP_FILE];
}

const text = (value: unknown): value is string => typeof value === "string" && value.trim() !== "";
const size = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && value > 0;
const isObject = (value: unknown): value is Record<string, unknown> => typeof value === "object" && value !== null && !Array.isArray(value);

/** The part table the API sends with a STEP file, read from its header's JSON. Null when there is none or it is not a table of parts
 * with a name and a thickness each: the file is saved either way, and the page then prints no part lines rather than half of them. */
export function readShapeParts(raw: string | null | undefined): ShapeParts | null {
  if (!raw) return null;
  let payload: unknown;
  try { payload = JSON.parse(raw); } catch { return null; }
  if (!isObject(payload) || !isObject(payload.units) || !Array.isArray(payload.parts) || !payload.parts.length) return null;
  const { length, volume, step } = payload.units;
  if (!text(length) || !text(step)) return null;
  const parts: ShapePart[] = [];
  for (const part of payload.parts) {
    if (!isObject(part) || !text(part.name) || !size(part.thickness)) return null;
    const plies = typeof part.plies === "number" && Number.isInteger(part.plies) && part.plies > 0 ? part.plies : null;
    parts.push({
      name: part.name, kind: text(part.kind) ? part.kind : "", layup: text(part.layup) ? part.layup : null, plies,
      ply_thickness: size(part.ply_thickness) ? part.ply_thickness : null, thickness: part.thickness,
      material: text(part.material) ? part.material : null, volume: size(part.volume) ? part.volume : 0, in_model: part.in_model !== false,
    });
  }
  return { title: text(payload.title) ? payload.title : "", units: { length, volume: text(volume) ? volume : `${length}³`, step }, parts };
}

/** Said under a STEP file once it is saved: what it holds and where the layup is, since the file holds none. */
export const STEP_FILE_NOTE = "Each part is one solid at its thickness, in millimetres. A STEP file holds no plies, so the layup is listed here and in the file's first lines.";
/** The same when the table did not come with the file: the file's own first lines still state the layup. */
export const STEP_FILE_NOTE_ALONE = "Each part is one solid at its thickness, in millimetres. A STEP file holds no plies; the layup is in the file's first lines.";

/** One line per solid, in the file's order: its name as the CAD program shows it, then its layup, ply count, thickness and material. A
 * layup is printed as the coupon writes it. */
export function shapePartLines(table: ShapeParts): string[] {
  const unit = table.units.length;
  const shown = (value: number) => `${formatNumber(value, { zeros: false })} ${unit}`;
  return table.parts.map((part) => {
    const material = part.material ?? "material not stated";
    const thick = `${shown(part.thickness)} thick`;
    if (!part.in_model) return `${part.name}: ${thick}, ${material}. Drawn as stated. The analysis grips this length and does not include the tab's material.`;
    if (part.plies === null || part.layup === null) return `${part.name}: one material, ${thick}, ${material}.`;
    const plies = `${part.plies} ${part.plies === 1 ? "ply" : "plies"}${part.ply_thickness === null ? "" : ` of ${shown(part.ply_thickness)}`}`;
    return `${part.name}: ${part.layup}, ${plies}, ${thick}, ${material}.`;
  });
}

/** What the page says once a file is saved: the file's kind, not its name (the name carries the coupon's). */
export function savedLine(file: ModelDownload, label: string): string {
  return file === STEP_FILE ? "Saved the STEP file." : `Saved the ${label}.`;
}
