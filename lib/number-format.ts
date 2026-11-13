/**
 * One rule for every number the site prints (ADR-0091 amendment 1): four significant figures, plain digits from 0.001 up to a
 * million, "× 10ⁿ" outside that range, and a true minus sign (U+2212). The API's sentences follow the same rule in plain ASCII
 * (`_words` in api/src/anisotropy_api/laminate_problems.py, `number` in fea/src/anisotropy_fea/explain.py) so the number guard can
 * read them; `inProse` turns their exponents and signs into this form on the page. Formatting changes precision for display only;
 * the engine supplies every value (ADR-0001).
 */

/** The minus sign the page prints (U+2212), never the hyphen. */
export const MINUS = "−";
const SUPERSCRIPT: Record<string, string> = { "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻" };

/** An integer exponent as superscript digits: -5 is ⁻⁵. */
export const superscript = (exponent: number): string => String(exponent).split("").map((c) => SUPERSCRIPT[c] ?? "").join("");

/** Plain digits from here up to `PLAIN_BELOW`; exponents outside. */
export const PLAIN_FROM = 1e-3;
export const PLAIN_BELOW = 1e6;

export type NumberStyle = {
  /** Significant figures, four by default. */
  figures?: number;
  /** Keep the zeros the figures call for ("3.220"), as a table column does; off for a value in a sentence ("3.22"). */
  zeros?: boolean;
};

/** A number as the page prints it: `formatNumber(3.22)` is "3.220", `formatNumber(-347449.9)` is "−347400",
 * `formatNumber(1.234e-5)` is "1.234 × 10⁻⁵"; zero is "0". A value that is not finite is "–". */
export function formatNumber(value: number, { figures = 4, zeros = true }: NumberStyle = {}): string {
  if (!Number.isFinite(value)) return "–";
  if (value === 0) return "0";
  const size = Math.abs(value);
  const rounded = Number(size.toPrecision(figures));
  let text: string;
  if (rounded >= PLAIN_FROM && rounded < PLAIN_BELOW) {
    const precise = size.toPrecision(figures);
    // toPrecision writes an exponent once the integer part has more digits than the figures (347400 is "3.474e+5"): print it plainly
    text = zeros && !precise.includes("e") ? precise : String(rounded);
  } else {
    const [mantissa, exponent] = size.toExponential(figures - 1).split("e");
    text = `${zeros ? mantissa : String(Number(mantissa))} × 10${superscript(Number(exponent))}`;
  }
  return value < 0 ? `${MINUS}${text}` : text;
}

/** The numbers of a sentence the API wrote, as the page prints them: a number written with an exponent is printed by the rule, so one
 * below a million reads in plain digits ("1.622e+04" from a job solved before the rule is "16220", as its Summary says) and one from a
 * million up in superscript ("1.5e+06" is "1.5 × 10⁶"); a sign before a number becomes the minus sign. The significant digits are kept
 * as written, so the sentence still quotes its facts; a name such as "Coupon-1" or the angles of a layup in brackets ("[0/45/-45/90]")
 * are left alone. */
export function inProse(text: string): string {
  return text
    .replace(/(?<![\w.])([-+−]?)(\d+(?:\.\d+)?)e([-+]?\d+)(?![\w.])/gi, (_, sign: string, mantissa: string, exponent: string) => {
      const figures = Math.max(1, mantissa.replace(".", "").replace(/^0+/, "").length); // as many as the sentence wrote: none dropped, none added
      return formatNumber(Number(`${sign === "-" || sign === MINUS ? "-" : ""}${mantissa}e${exponent}`), { figures, zeros: false });
    })
    .replace(/(^|[\s(=:,])-(?=\d)/g, `$1${MINUS}`);
}
