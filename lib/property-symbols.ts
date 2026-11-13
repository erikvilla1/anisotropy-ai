// The symbol a property row shows beside its name, from the record's key: E1t -> E₁ₜ, nu12 -> ν₁₂, epsilon1t -> ε₁ₜᵘ,
// F12-offset -> F₁₂, density-LT -> ρ. The physics cards and the workspace write the same symbols. A key with no
// engineering symbol (a core grade, a short-beam strength, a resin content) shows none rather than its record key.
const SUBSCRIPT: Record<string, string> = { 0: "₀", 1: "₁", 2: "₂", 3: "₃", 4: "₄", 5: "₅", 6: "₆", 7: "₇", 8: "₈", 9: "₉" };
const GREEK: Record<string, string> = { nu: "ν", alpha: "α", beta: "β", epsilon: "ε", gamma: "γ" };
const NAMED: Record<string, string> = { density: "ρ", Vf: "Vf", void: "Vv", tply: "t", Tg: "Tg", shear: "γ" };

/** A supplier's own wording in the site's style: a space before °C and °F, and "fibre" (docs/copy-style-guide.md rule 6). */
export function houseStyle(text: string): string {
  return text.replace(/(\d)\s?°([FC])/g, "$1 °$2").replace(/\bfiber\b/g, "fibre").replace(/\bFiber\b/g, "Fibre");
}

export function propertySymbol(key: string): string | undefined {
  const base = key.split("-")[0];
  if (base in NAMED) return NAMED[base];
  const match = base.match(/^(E|G|F|nu|alpha|beta|epsilon|gamma)(\d{1,2})([tc]?)$/);
  if (!match) return undefined;
  const [, name, digits, mode] = match;
  const ultimate = name === "epsilon" || name === "gamma" ? "ᵘ" : "";
  return `${GREEK[name] ?? name}${digits.replace(/\d/g, d => SUBSCRIPT[d])}${mode === "t" ? "ₜ" : mode}${ultimate}`;
}
