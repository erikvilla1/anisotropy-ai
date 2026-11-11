/** Conditions (ADR-0087): physics a problem may carry beyond its base rows, offered when the engineer asks for it, by a word in the chat
 * or from the "Add a condition" menu on the panels, and never shown before. Each names the product it belongs to, the words that call it
 * up, and the panel that holds its rows. The page decides only what to show; every number is the engine's (ADR-0001). */

export type ConditionId = "temperature";
export type Condition = {
  id: ConditionId;
  title: string;
  /** what it adds, in the engineer's words, for the menu and the chat's offer */
  detail: string;
  product: "laminate" | "fea";
  /** the words that call it up in a message */
  words: RegExp;
  /** the id of the panel that holds its rows (`showPanel`) */
  panel: string;
};

export const CONDITIONS: Condition[] = [
  {
    id: "temperature", title: "Temperature change", product: "laminate", panel: "temperature",
    detail: "a uniform change of temperature, as after a cure: with loads it is held while they grow to failure, alone it grows itself",
    words: /\b(temperature|thermal(?:ly)?|cool(?:ed|s|ing|down)?|heat(?:ed|s|ing)?|warm(?:ed|s|ing)?|cure[ds]?|curing|residual stress(?:es)?|expansion|delta[\s_-]?t)\b|Δ\s*t|°\s*[CF]\b|\balpha\s*[12]\b|α\s*[12]/i,
  },
];

/** The conditions of a product that a message names, in the registry's order. */
export function conditionsNamed(text: string, product: Condition["product"]): Condition[] {
  return CONDITIONS.filter((c) => c.product === product && c.words.test(text));
}

export const conditionOf = (id: string): Condition | undefined => CONDITIONS.find((c) => c.id === id);
