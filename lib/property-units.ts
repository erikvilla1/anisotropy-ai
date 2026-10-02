import { formatNumber, parseProperty, PSI_MPA } from "./material-analysis";

// Convert only the reported numbers. A display conversion does not resolve
// an uncertain source value or make it eligible for an analysis export.
const units: Record<string, { english: [number, string]; si: [number, string] }> = {
  Msi: { english: [1, "Msi"], si: [PSI_MPA * 1000, "GPa"] },
  ksi: { english: [1, "ksi"], si: [PSI_MPA * 1000, "MPa"] },
  psi: { english: [1, "psi"], si: [PSI_MPA, "MPa"] },
  GPa: { english: [1 / (PSI_MPA * 1000), "Msi"], si: [1, "GPa"] },
  MPa: { english: [1 / PSI_MPA, "psi"], si: [1, "MPa"] },
  "g/cm³": { english: [0.0254 ** 3 * 1000 / 0.45359237, "lb/in³"], si: [1000, "kg/m³"] },
  "strain/unit c": { english: [1, "strain/unit c"], si: [1, "strain/unit c"] },
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

export function dualUnits(value: string | number, unit: string) {
  const input = String(value).trim();
  const qualifier = input.startsWith(">") ? "> " : "";
  const raw = qualifier ? input.slice(1).trim() : input;
  if (/^(?:\s*|—|-|TBD)$/i.test(raw)) return { english: "Not provided", si: "Not provided" };
  const scalar = parseProperty(raw);
  const range = raw.match(/^([+-]?[\d,.]+)\s*[–—]\s*([+-]?[\d,.]+)$/);
  const numbers = scalar !== null ? [scalar] : range ? [parseProperty(range[1]), parseProperty(range[2])] : [];
  if ((unit === "°F" || unit === "°C") && numbers.length && numbers.every(n => n !== null)) {
    const renderTemperature = (target: "°F" | "°C") => `${numbers.map(n => formatNumber(unit === target ? n! : target === "°C" ? (n! - 32) * 5 / 9 : n! * 9 / 5 + 32)).join("–")} ${target}`;
    return { english: renderTemperature("°F"), si: renderTemperature("°C") };
  }
  const conversion = units[unit];
  if (!conversion || !numbers.length || numbers.some(n => n === null)) return { english: "Conversion unavailable", si: "Conversion unavailable" };
  const render = ([factor, suffix]: [number, string]) => `${qualifier}${numbers.map(n => formatNumber(n! * factor)).join("–")}${suffix ? ` ${suffix}` : ""}`;
  return { english: render(conversion.english), si: render(conversion.si) };
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

export function propertyDisplayValue(p: { value: number; valueEnd?: number; valueQualifier?: ">" }): string | number {
  if (p.valueQualifier) return `${p.valueQualifier}${p.value}`;
  return p.valueEnd === undefined ? p.value : `${p.value}–${p.valueEnd}`;
}
