// Number helpers the property pages share. Kept apart from lib/material-analysis.ts, which holds the course-appendix audit
// that no page may load (ADR-0042): the pages import these from here.

// Factors derive from exact SI definitions: inch=0.0254 m; lb=0.45359237 kg;
// standard gravity=9.80665 m/s². Original numbers/signs are never overwritten.
export const PSI_MPA = 0.45359237 * 9.80665 / (0.0254 ** 2) / 1e6;

export function parseProperty(value: string): number | null {
  const cleaned = value.trim().replace(/,/g, "");
  return /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(cleaned) && Number.isFinite(Number(cleaned)) ? Number(cleaned) : null;
}

export function formatNumber(value: number) { return Number(value.toPrecision(6)).toLocaleString("en-US", { maximumSignificantDigits: 6 }); }
