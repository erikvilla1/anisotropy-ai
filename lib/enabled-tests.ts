/**
 * One workflow first (ADR-0089): the studio offers the unnotched tension coupon, under ASTM D3039 or no standard, with a laminate of
 * plies, until its comparison with Abaqus is validated. The list comes from the form's definition, which the fea package writes
 * (`anisotropy_fea.enabled`); whether the development switch shows every test comes from the API (`allCouponTests`), and is false until
 * the API says otherwise. Every other test stays in the code, hidden: nothing here deletes a row, a word or a project.
 *
 * The shared helpers (`wordsFor`, `sectionsFor`, `readMessage`, `couponOffer`) are left as they are; the places that show or offer a test
 * filter through these functions, with `all` passed in.
 */
import {
  BENDING_KEYS, DOGBONE_KEYS, formDefinition, HOLE_KEYS, ISOTROPIC_KEYS, NO_STANDARD, type EnabledList, type StandardProfile, type StudioForm,
} from "./studio-form";

export const ENABLED: EnabledList = formDefinition.enabled;

/** The rows only the hidden tests and materials use: a hole, a bending span, a dog-bone, one isotropic material, and the rows that choose
 * them. With the list closed they are neither shown nor offered to a message. The Specimen row stays out too: D3039 names classes of
 * laminate, not specimens. */
export const HIDDEN_ROW_KEYS: readonly string[] = [...HOLE_KEYS, ...BENDING_KEYS, ...DOGBONE_KEYS, ...ISOTROPIC_KEYS, "material_kind", "specimen"];

/** Whether the Test row's word is offered. */
export const isTestEnabled = (test: string, all: boolean): boolean => all || ENABLED.tests.includes(test);
/** Whether the Standard row's word is offered: no standard always, a designation when it is on the list. */
export const isStandardEnabled = (designation: string, all: boolean): boolean =>
  all || !designation || designation === NO_STANDARD || ENABLED.standards.includes(designation);
/** Whether the Material kind row's word is offered; blank means a laminate of plies. */
export const isMaterialKindEnabled = (word: string, all: boolean): boolean => all || !word || ENABLED.material_kinds.includes(word);

/** The Test row's words the page offers. */
export const enabledTests = (words: readonly string[], all: boolean): string[] => words.filter((word) => isTestEnabled(word, all));
/** The standards the page offers for a test, out of those that cover it. */
export const enabledStandards = (profiles: readonly StandardProfile[], all: boolean): StandardProfile[] =>
  profiles.filter((profile) => isStandardEnabled(profile.designation, all));
/** A list row's words the page offers: the Test, Standard and Material kind rows filtered, every other row as it is. */
export function enabledWords(key: string, words: readonly string[], all: boolean): string[] {
  if (key === "test") return enabledTests(words, all);
  if (key === "standard") return words.filter((word) => isStandardEnabled(word, all));
  if (key === "material_kind") return words.filter((word) => isMaterialKindEnabled(word, all));
  return [...words];
}
/** Whether a row is shown and offered: every row with the switch on, none of the hidden tests' rows with it off. */
export const isRowEnabled = (key: string, all: boolean): boolean => all || !HIDDEN_ROW_KEYS.includes(key);

const capitalised = (text: string): string => text.charAt(0).toUpperCase() + text.slice(1);
/** The sentence for something hidden: "Open-hole tension is not available yet: the studio offers ...". */
export const notAvailable = (what: string): string => `${capitalised(what)} is ${ENABLED.not_available}.`;

/** Why a form cannot be set up here with the list closed, or null when it can: its test, its standard, its material kind, or a dog-bone. */
export function hiddenReason(form: StudioForm, all: boolean): string | null {
  if (all) return null;
  const test = (form.test ?? "").trim();
  if (test && !isTestEnabled(test, all)) return notAvailable(test);
  const standard = (form.standard ?? "").trim();
  if (!isStandardEnabled(standard, all)) return notAvailable(standard);
  if (!isMaterialKindEnabled((form.material_kind ?? "").trim(), all)) return notAvailable("one isotropic material");
  if (!ENABLED.dogbone && DOGBONE_KEYS.some((key) => (form[key] ?? "").trim())) return notAvailable("a dog-bone");
  return null;
}

/** Rows read from a message, or proposed by the model, without what the list keeps out: a hidden test, standard or material kind, and
 * the hidden tests' own rows. The notes say what was left out and why. */
export function withoutHidden(rows: StudioForm, all: boolean): { rows: StudioForm; notes: string[]; dropped: string[] } {
  if (all) return { rows, notes: [], dropped: [] };
  const kept: StudioForm = {};
  const notes: string[] = [];
  const dropped: string[] = [];
  for (const [key, value] of Object.entries(rows)) {
    const note = key === "test" && value && !isTestEnabled(value, all) ? notAvailable(value)
      : key === "standard" && !isStandardEnabled(value, all) ? notAvailable(value)
        : key === "material_kind" && !isMaterialKindEnabled(value, all) ? notAvailable("one isotropic material") : null;
    if (note) notes.push(note);
    if (note || !isRowEnabled(key, all)) { dropped.push(key); continue; }
    kept[key] = value;
  }
  return { rows: kept, notes: [...new Set(notes)], dropped };
}

/** The words the chat's reader says it understood (`readMessage`), less those of the rows the list kept out: "test: open-hole tension",
 * "hole 6 mm", "span 48 mm", the dog-bone's sizes. */
const UNDERSTOOD_OF: Record<string, string> = {
  test: "test: ", standard: "standard: ", hole_diameter: "hole ", span: "span ", narrow_width: "narrow width ", narrow_length: "narrow length ",
  radius: "fillet radius ", outer_radius: "outer radius ",
};
export const understoodWithout = (understood: readonly string[], dropped: readonly string[]): string[] =>
  understood.filter((line) => !dropped.some((key) => UNDERSTOOD_OF[key] && line.startsWith(UNDERSTOOD_OF[key])));
