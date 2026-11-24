/** Whether each number the chat shows came from the engine (ADR-0138, criterion 4 of the `chat-answer-quality` skill): a number in an
 * answer must be one the API sent the page, one printed on the page outside the chat, or one in the question, to the digits it is
 * printed with, in the units the engine works in or the ones the page converts to. Nothing here computes a result. */

/** A number as printed: its value, and the size of half a unit in its last printed digit, which is how far the true value may lie. */
export type Printed = { value: number; half: number; raw: string };

const SUPERSCRIPT: Record<string, string> = { "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-" };
/** A number, with thousands separators, a sign (a hyphen or the minus sign), a decimal part and an exponent written either way. */
const NUMBER = /(?<![\w.])([-−–]?)(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?:(?:e|E)([-+]?\d+)|\s?[×x]\s?10([⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+|\^[-−]?\d+))?(?![\w])/g;
/** A layup in brackets ("[45/0/-45/90]s"), a date or a time, read as words, not numbers. */
const SKIPPED = /\[[^\]]*\]\w*|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}\b/g;

/** Every number printed in a text, in order. */
export function numbersIn(text: string): Printed[] {
  const out: Printed[] = [];
  const plain = text.replace(SKIPPED, " ");
  for (const m of plain.matchAll(NUMBER)) {
    const [raw, sign, whole, fraction = "", exponent, power] = m;
    const decimals = fraction ? fraction.length - 1 : 0;
    let scale = 0;
    if (exponent !== undefined) scale = Number(exponent);
    else if (power !== undefined) scale = Number(power.startsWith("^") ? power.slice(1).replace("−", "-") : [...power].map((c) => SUPERSCRIPT[c]).join(""));
    const size = Number(`${whole.replace(/,/g, "")}${fraction}e${scale}`); // read in one go, so 3.5 × 10⁻⁴ is 0.00035 exactly as printed
    if (!Number.isFinite(size) || !Number.isFinite(scale)) continue;
    const value = (sign ? -1 : 1) * size;
    out.push({ value, half: 0.5 * 10 ** (scale - decimals), raw: raw.trim() });
  }
  return out;
}

/** A number the answer need not trace: zero, and a small whole number (a ply, an angle, a count, a step), which is never a result. */
export function untraceable(n: Printed): boolean {
  const size = Math.abs(n.value);
  return size === 0 || (Number.isInteger(n.value) && n.half >= 0.5 && size <= 100);
}

/** The factors between the engine's units and those a page prints: SI and its prefixes, percent, and the US units the page converts to
 * (inch, pound-force, psi, ksi, Msi, pound-force per inch). */
const FACTORS = (() => {
  const base = [1, 1e3, 1e6, 1e9, 1e-3, 1e-6, 1e-9, 100, 0.01];
  const us = [25.4, 1 / 25.4, 0.0254, 1 / 0.0254, 4.4482216152605, 1 / 4.4482216152605, 6894.757293168, 1 / 6894.757293168, 175.126835, 1 / 175.126835];
  const out = new Set<number>(base);
  for (const u of us) for (const b of base) out.add(u * b);
  return [...out];
})();

/** The numbers the engine sent and the page printed, sorted by size so each answer's number is looked up by halving. */
export class NumberPool {
  private sizes: number[] = [];
  private sorted = true;

  get size(): number { return this.sizes.length; }

  add(value: number): void {
    if (!Number.isFinite(value) || value === 0) return;
    this.sizes.push(Math.abs(value));
    this.sorted = false;
  }

  /** Every number in a JSON value the API answered with, numbers written as strings too ("376" for an element). */
  addJson(value: unknown): void {
    if (typeof value === "number") this.add(value);
    else if (typeof value === "string") { if (/^[-+]?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(value.trim())) this.add(Number(value)); else this.addText(value); }
    else if (Array.isArray(value)) for (const item of value) this.addJson(item);
    else if (value && typeof value === "object") for (const item of Object.values(value)) this.addJson(item);
  }

  /** Every number printed in a text: the page outside the chat, the question. */
  addText(text: string): void {
    for (const n of numbersIn(text)) this.add(n.value);
  }

  private ready(): number[] {
    if (!this.sorted) { this.sizes.sort((a, b) => a - b); this.sorted = true; }
    return this.sizes;
  }

  /** Whether a value lies in [low, high]. */
  private holds(low: number, high: number): boolean {
    const sizes = this.ready();
    let lo = 0, hi = sizes.length;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (sizes[mid] < low) lo = mid + 1; else hi = mid; }
    return lo < sizes.length && sizes[lo] <= high;
  }

  /** Whether a printed number is one of the pool's, rounded as printed, in any of the units the page may print it in. */
  traces(n: Printed): boolean {
    const size = Math.abs(n.value);
    const slack = Math.max(n.half, size * 1e-9);
    return FACTORS.some((factor) => this.holds((size - slack) / factor * (1 - 1e-12), (size + slack) / factor * (1 + 1e-12)));
  }
}

/** The numbers of a text that trace to nothing in the pool, or in any of the pools, as printed. */
export function untraced(text: string, pool: NumberPool | readonly NumberPool[]): string[] {
  const pools = Array.isArray(pool) ? pool : [pool as NumberPool];
  return numbersIn(text).filter((n) => !untraceable(n) && !pools.some((p) => p.traces(n))).map((n) => n.raw);
}
