import { formatNumber, parseProperty, PSI_MPA } from "./property-numbers";

// Convert only the reported numbers. A display conversion does not resolve
// an uncertain source value or make it eligible for an analysis export.
const units: Record<string, { english: [number, string]; si: [number, string] }> = {
  Msi: { english: [1, "Msi"], si: [PSI_MPA * 1000, "GPa"] },
  ksi: { english: [1, "ksi"], si: [PSI_MPA * 1000, "MPa"] },
  psi: { english: [1, "psi"], si: [PSI_MPA, "MPa"] },
  GPa: { english: [1 / (PSI_MPA * 1000), "Msi"], si: [1, "GPa"] },
  MPa: { english: [1 / PSI_MPA, "psi"], si: [1, "MPa"] },
  // A density printed in g/cm³ stays in g/cm³ in the SI / metric column, so that column shows the printed figure.
  "g/cm³": { english: [0.0254 ** 3 * 1000 / 0.45359237, "lb/in³"], si: [1, "g/cm³"] },
  "lb/in³": { english: [1, "lb/in³"], si: [0.45359237 / 0.0254 ** 3, "kg/m³"] },
  "lb/ft³": { english: [1, "lb/ft³"], si: [0.45359237 / 0.3048 ** 3, "kg/m³"] },
  in: { english: [1, "in"], si: [25.4, "mm"] },
  mm: { english: [1 / 25.4, "in"], si: [1, "mm"] },
  "kg/m³": { english: [0.3048 ** 3 / 0.45359237, "lb/ft³"], si: [1, "kg/m³"] },
  "10⁻⁶/K": { english: [1 / 1.8, "10⁻⁶/°F"], si: [1, "10⁻⁶/K"] },
  "10⁻⁶/°F": { english: [1, "10⁻⁶/°F"], si: [1.8, "10⁻⁶/K"] },
  "10⁻⁶/%": { english: [1, "10⁻⁶/%"], si: [1, "10⁻⁶/%"] },
  "%": { english: [1, "%"], si: [1, "%"] },
  "—": { english: [1, ""], si: [1, ""] },
};
// A stress printed in MPa reads in ksi, or in psi when it is below 1 ksi (a core's strength). A table chooses once for all
// its MPa rows (`englishStressUnit`), so a nominal and a minimum value of one property never read in different units.
const KSI: [number, string] = [1 / (PSI_MPA * 1000), "ksi"];
export type StressUnit = "psi" | "ksi";

/** Which column of the table holds the value as the source prints it; null when both read the same (%, a pure number). */
export function recordedSystem(unit: string): "english" | "si" | null {
  if (unit === "°F") return "english";
  if (unit === "°C") return "si";
  const conversion = units[unit];
  if (!conversion || conversion.english[0] === conversion.si[0]) return null;
  return conversion.english[0] === 1 && conversion.english[1] === unit ? "english" : "si";
}

/** The column a table tags "as printed": the system most of its rows were printed in; null when no row has one (only
 * percentages and pure numbers). A row printed in the other system says so on its own line (`printedElsewhere`). */
export function printedColumn(units: string[]): "english" | "si" | null {
  const count = { english: 0, si: 0 };
  for (const unit of units) { const system = recordedSystem(unit); if (system) count[system] += 1; }
  if (!count.english && !count.si) return null;
  return count.english >= count.si ? "english" : "si";
}

/** The note for a row printed in the column the table does not tag, e.g. a density in g/cm³ in a table printed in US units. */
export function printedElsewhere(unit: string, column: "english" | "si" | null): string {
  const system = recordedSystem(unit);
  if (!system || !column || system === column) return "";
  return system === "si" ? "printed in metric units" : "printed in English units"; // the column is "SI / metric": g/cm³ is metric, not SI
}

/** Significant figures of a number as printed; trailing zeros of a whole number are not counted. */
function significantFigures(raw: string): number {
  const digits = raw.replace(/^[+\-−]/, "").replace(/,/g, "");
  if (!/^\d*\.?\d*$/.test(digits)) return 6;
  if (digits.includes(".")) return digits.replace(".", "").replace(/^0+/, "").length || 1;
  return digits.replace(/^0+/, "").replace(/0+$/, "").length || 1;
}

// The minus sign (U+2212) for a negative number, also at the second end of a range; "× 10⁻⁶/K" for a power-of-ten unit.
const minus = (text: string) => text.replace(/(^|[–—\s])-(?=[\d.])/g, "$1−");
const scaled = (suffix: string) => suffix.startsWith("10⁻") ? `× ${suffix}` : suffix;

/** A printed value: no qualifier, one number, or a range "a–b". */
function readValue(value: string | number) {
  const input = String(value).trim();
  const qualifier = input.startsWith(">") ? "> " : "";
  const raw = qualifier ? input.slice(1).trim() : input;
  const missing = /^(?:\s*|—|-|TBD)$/i.test(raw);
  const range = raw.match(/^([+-]?[\d,.]+)\s*[–—]\s*([+-]?[\d,.]+)$/);
  const printed = parseProperty(raw) !== null ? [raw] : range ? [range[1], range[2]] : [];
  return { qualifier, missing, printed, numbers: printed.map(parseProperty) };
}

/** A value exactly as the source prints it, in the page's typography: "−0.9 × 10⁻⁶/°C". */
export function printedValue(value: string | number, unit: string | undefined): string {
  return `${minus(String(value).trim())}${unit && unit !== "—" ? ` ${scaled(unit)}` : ""}`;
}

/** The English unit for every MPa row of one table: psi when any of them is below 1 ksi, otherwise ksi. */
export function englishStressUnit(properties: { value: string | number; unit: string }[]): StressUnit {
  const stresses = properties.filter(p => p.unit === "MPa").flatMap(p => readValue(p.value).numbers);
  return stresses.some(n => n !== null && Math.abs(n * KSI[0]) < 1) ? "psi" : "ksi";
}

/** A converted number at the printed number's significant figures, trailing zeros kept: 76 MPa is "11.0 ksi". */
function displayFigures(n: number, figures: number): string {
  return n === 0 ? "0" : n.toLocaleString("en-US", { minimumSignificantDigits: figures, maximumSignificantDigits: figures });
}

/** The recorded number as printed: the trailing zeros a printed figure keeps ("80.0", "5.10") are kept too. */
function recordedFigures(n: number, raw: string): string {
  const text = formatNumber(n);
  const printedDecimals = raw.match(/\.(\d*0)$/)?.[1].length ?? 0;
  const decimals = text.split(".")[1]?.length ?? 0;
  if (printedDecimals <= decimals || Number(text.replace(/,/g, "")) !== n) return text;
  return `${text}${decimals ? "" : "."}${"0".repeat(printedDecimals - decimals)}`;
}

/** A value in English and SI units. The column that holds the recorded unit shows the number as printed, trailing zeros
 * of a printed string included; the other is a conversion, rounded for display to the printed number's significant
 * figures (at least three). `precision: "full"` keeps six figures, for exports. `stressUnit` fixes psi or ksi for an MPa
 * value; a table passes one for all its rows. Negative numbers use the minus sign, and a power-of-ten unit reads
 * "× 10⁻⁶/K". */
export function dualUnits(value: string | number, unit: string, options: { precision?: "display" | "full"; stressUnit?: StressUnit } = {}) {
  const { qualifier, missing, printed, numbers } = readValue(value);
  if (missing) return { english: "Not provided", si: "Not provided" };
  const figures = printed.map(p => Math.min(6, Math.max(3, significantFigures(p))));
  const round = (n: number, i: number, converted: boolean) => minus(!converted
    ? recordedFigures(n, printed[i])
    : options.precision !== "full" ? displayFigures(n, figures[i]) : formatNumber(n));
  if ((unit === "°F" || unit === "°C") && numbers.length && numbers.every(n => n !== null)) {
    const renderTemperature = (target: "°F" | "°C") => `${numbers.map((n, i) => round(unit === target ? n! : target === "°C" ? (n! - 32) * 5 / 9 : n! * 9 / 5 + 32, i, unit !== target)).join("–")} ${target}`;
    return { english: renderTemperature("°F"), si: renderTemperature("°C") };
  }
  const conversion = units[unit];
  if (!conversion || !numbers.length || numbers.some(n => n === null)) return { english: "Conversion unavailable", si: "Conversion unavailable" };
  const stressUnit = options.stressUnit ?? englishStressUnit([{ value, unit }]);
  const english = unit === "MPa" && stressUnit === "ksi" ? KSI : conversion.english;
  const recorded = recordedSystem(unit);
  const render = ([factor, suffix]: [number, string], converted: boolean) =>
    `${qualifier}${numbers.map((n, i) => round(n! * factor, i, converted)).join("–")}${suffix ? ` ${scaled(suffix)}` : ""}`;
  return { english: render(english, recorded === "si"), si: render(conversion.si, recorded === "english") };
}

export const propertyGroups = ["Stiffness", "Strength", "Physical properties", "Thermal & moisture"] as const;
export type PropertyGroup = typeof propertyGroups[number];
export function propertyGroup(label: string): PropertyGroup {
  if (/modulus|poisson/i.test(label)) return "Stiffness";
  if (/strength|ultimate.*strain|shear strain/i.test(label)) return "Strength";
  if (/expansion|transition temperature/i.test(label)) return "Thermal & moisture";
  return "Physical properties";
}

export function propertyName(label: string) {
  const elastic: Record<string, string> = {
    "Longitudinal modulus": "Elastic modulus · longitudinal",
    "Transverse modulus": "Elastic modulus · transverse",
    "Transverse in-plane modulus": "Elastic modulus · transverse in-plane",
    "Transverse out-of-plane modulus": "Elastic modulus · out-of-plane",
  };
  return elastic[label] || label;
}

/** The value a table shows: the printed figures when the record keeps them ("80.0"), a bound or a range, or the number. */
export function propertyDisplayValue(p: { value: number; valueEnd?: number; valueQualifier?: ">"; printedFigures?: string }): string | number {
  if (p.valueQualifier) return `${p.valueQualifier}${p.value}`;
  if (p.valueEnd !== undefined) return `${p.value}–${p.valueEnd}`;
  return p.printedFigures ?? p.value;
}
