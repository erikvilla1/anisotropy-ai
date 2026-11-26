import type { Basis, ExtremeSet, Fields, FirstPlyFailure, OutsideEarlier, PlyExtreme } from "./studio-api";

/** The answer a coupon's result gives (ADR-0085), as the package wrote it: per criterion, whether a ply fails at the applied loading, the
 * loading at first-ply failure, which ply, by which mode and where, read in the gauge section when the coupon has one, and on a plate away
 * from its held corners (ADR-0108 amendment 2). The page computes
 * nothing (ADR-0051): every number here is the package's, picked and labelled. Null for a job solved before the package wrote it. */

export const CRITERION_NAMES: Record<string, string> = { max_stress: "Maximum stress", max_strain: "Maximum strain", tsai_hill: "Tsai-Hill", tsai_wu: "Tsai-Wu" };
export const BASIS_WORDS: Record<Basis, string> = { gauge: "the gauge section", away: "the plate away from its held corners", whole: "the whole model" };
/** The summary's table each basis is read from, as the package names them (fea/src/anisotropy_fea/fields.py BASIS_TABLES). */
const BASIS_TABLES: Record<Basis, "fpf_gauge" | "fpf_away" | "fpf"> = { gauge: "fpf_gauge", away: "fpf_away", whole: "fpf" };
/** Where an earlier failure outside the basis is, first word capitalised, and whether its value grows with a finer mesh (ADR-0108). */
export function outsideWhere(o: OutsideEarlier, basisWords: string): { where: string; singular: boolean } {
  if (o.touches_grip) return { where: "At a grip edge", singular: true };
  if (o.near_tab) return { where: "Beside a tab line", singular: true };
  if (o.near_corner) return { where: "Beside a held corner", singular: true };
  return { where: `Outside ${basisWords}`, singular: false };
}
/** The engine's governing modes in short words, as the explanation says them (fea/src/anisotropy_fea/explain.py MODE_WORDS). */
export const MODE_SHORT: Record<string, string> = {
  "longitudinal tension": "tension along the fibres", "longitudinal compression": "compression along the fibres",
  "transverse tension": "tension across the fibres", "transverse compression": "compression across the fibres", "in-plane shear": "in-plane shear",
  interactive: "the combined stresses", none: "no stress",
};
export const modeWords = (mode: string) => MODE_SHORT[mode] ?? mode;

export type AnswerRow = {
  criterion: string; name: string; fails: boolean; factor: number; index: number; ply: number; angle: number; face: string | null; tied: number[];
  mode: string; element: number; label: string; xy: number[]; place: string; applied: number | null; reaction: number | null; earliest: boolean;
};
export type Answer = {
  basis: Basis; basisWords: string; rows: AnswerRow[]; earliest: AnswerRow; outside: (OutsideEarlier & { name: string }) | null;
  control: string; appliedUnit: string; forceUnit: string; reactionSet: string; everyLoad: boolean;
  /** The loading as it is applied, beside the loading at first-ply failure: the applied quantity and the reaction with it, as the package
   * wrote them. Null where several loads are scaled together, since no one number is "the applied load" then. */
  appliedNow: { applied: number; reaction: number } | null;
};

function rowOf(criterion: string, f: FirstPlyFailure, earliest: string): AnswerRow | null {
  if (f.fails === undefined || f.at_failure === undefined) return null;
  return {
    criterion, name: CRITERION_NAMES[criterion] ?? criterion, fails: f.fails, factor: f.factor, index: f.index, ply: f.ply, angle: f.angle,
    face: f.face ?? null, tied: f.tied_plies.filter((p) => p !== f.ply), mode: f.mode, element: f.element, label: f.label, xy: f.xy, place: f.place,
    applied: f.at_failure ? f.at_failure.applied : null, reaction: f.at_failure ? f.at_failure.reaction : null, earliest: criterion === earliest,
  };
}

export function answerOf(fields: Fields): Answer | null {
  const s = fields.summary;
  const verdict = s.verdict;
  if (!verdict) return null;
  const table = (verdict.basis === "whole" ? s.fpf : s[BASIS_TABLES[verdict.basis]]) ?? {};
  const rows = Object.entries(table).map(([c, f]) => rowOf(c, f, verdict.earliest)).filter((r): r is AnswerRow => r !== null)
    .sort((a, b) => a.factor - b.factor);
  const earliest = rows.find((r) => r.earliest);
  if (!earliest) return null;
  const first = Object.values(table)[0]?.at_failure;
  const outside = verdict.outside_earlier ? { ...verdict.outside_earlier, name: CRITERION_NAMES[verdict.outside_earlier.criterion] ?? verdict.outside_earlier.criterion } : null;
  return {
    basis: verdict.basis, basisWords: BASIS_WORDS[verdict.basis], rows, earliest, outside, control: s.applied.control,
    appliedUnit: first?.unit ?? s.applied.unit, forceUnit: first?.reaction_unit ?? fields.labels.force ?? "", reactionSet: s.reaction.set,
    everyLoad: Boolean(first?.every_load),
    appliedNow: first?.every_load ? null : { applied: s.applied.value, reaction: s.reaction.value },
  };
}

/** The first-ply stat of the chat's Results card: the answer the page and the list of past analyses lead with (ADR-0085), read where the
 * package read it, and the earlier failure outside it in one short line. Null for a result without the package's answer. */
export type AnswerStat = { fails: boolean; verdict: "Holds" | "Fails"; factor: string; facts: string; outside: string | null };

export function answerStat(fields: Fields, print: (value: number) => string): AnswerStat | null {
  const a = answerOf(fields);
  if (!a) return null;
  const e = a.earliest, o = a.outside;
  const at = o ? outsideWhere(o, a.basisWords) : null;
  return {
    fails: e.fails, verdict: e.fails ? "Fails" : "Holds", factor: print(e.factor), facts: `${e.name}, ply ${e.ply} · ${e.angle}°, ${a.basisWords}`,
    outside: o && at ? `${at.where} R = ${print(o.factor)}${at.singular ? ", reported apart: stress there grows with a finer mesh." : ", reported apart."}` : null,
  };
}

/** The largest ply stresses on the answer's basis, one row per component and sign, in the order an engineer reads them; a sign never reached
 * is left out. Each row names its ply, as the package found it over every ply. */
export type ExtremeRow = { key: string; words: string; extreme: NonNullable<PlyExtreme> };
const EXTREME_ROWS: [keyof ExtremeSet, "tension" | "compression" | "largest", string][] = [
  ["S11", "tension", "σ₁ tension along the fibres"], ["S11", "compression", "σ₁ compression along the fibres"],
  ["S22", "tension", "σ₂ tension across the fibres"], ["S22", "compression", "σ₂ compression across the fibres"],
  ["S12", "largest", "τ₁₂ in-plane shear, largest"],
];

export function extremeRows(set: ExtremeSet): ExtremeRow[] {
  const out: ExtremeRow[] = [];
  for (const [name, pick, words] of EXTREME_ROWS) {
    const extreme = (set[name] as Record<string, PlyExtreme>)[pick];
    if (extreme) out.push({ key: `${name}-${pick}`, words, extreme });
  }
  return out;
}
