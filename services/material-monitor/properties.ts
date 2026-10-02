import { normalize, type PageText } from "./documents";
import type { PropertyValue, SourceStatus } from "../../lib/material-evidence";

const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
export function revisionMetadata(sourceId: string, pages: PageText[]): Pick<SourceStatus, "revision" | "revisionDate" | "datePrecision" | "dateMeaning"> {
  const text = pages.map(p => normalize(p.text)).join(" ");
  const unknown = { revision: null, revisionDate: null, datePrecision: null, dateMeaning: "No explicit revision date verified in source; copyright and URL dates are not revision dates." } as const;
  if (sourceId.startsWith("astm-")) {
    const meta = JSON.parse(pages[0].text);
    const stamp = meta.catalogUpdated ? Date.parse(meta.catalogUpdated + " UTC") : NaN;
    return { revision: meta.edition, revisionDate: Number.isFinite(stamp) ? new Date(stamp).toISOString().slice(0, 10) : null,
      datePrecision: Number.isFinite(stamp) ? "day" : null, dateMeaning: "Publisher catalog page last updated; this is not a material test or revision date." };
  }
  if (sourceId === "diab-divinycell-h-si") {
    const match = text.match(/Datasheet Diab Divinycell H rev\s+(\d+)\s+SI\s+([A-Za-z]+)\s+(20\d{2})/i);
    const month = match ? months.findIndex(m => m.toLowerCase() === match[2].toLowerCase()) : -1;
    if (match && month >= 0) return { revision: `Revision ${match[1]} · SI`, revisionDate: `${match[3]}-${String(month + 1).padStart(2, "0")}`, datePrecision: "month", dateMeaning: "Revision and month printed in manufacturer datasheet." };
  }
  if (sourceId === "toray-ex1515") {
    const match = text.match(/TORAY_EX1515_PDS_v([\d.]+)_(\d{4}-\d{2}-\d{2})/);
    if (match) return { revision: `Version ${match[1]}`, revisionDate: match[2], datePrecision: "day", dateMeaning: "Revision and date printed in manufacturer datasheet." };
  }
  if (sourceId === "baltek-sbc") {
    const match = text.match(/DATA SHEET\s+(0[1-9]|1[0-2])\.(20\d{2})/);
    if (match) return { revision: "Datasheet issue", revisionDate: `${match[2]}-${match[1]}`, datePrecision: "month", dateMeaning: "Issue month printed in manufacturer datasheet; no revision number stated." };
  }
  return unknown;
}

function numbers(row: string, count: number): number[] {
  const tokens = row.trim().split(/\s+/);
  if (tokens.length !== count || !tokens.every(t => /^\d+(?:\.\d+)?$/.test(t))) throw new Error("Unexpected table layout; property extraction requires review");
  const values = tokens.map(Number);
  if (values.some(n => !Number.isFinite(n) || n <= 0)) throw new Error("Invalid mechanical property");
  return values;
}

// Deliberately narrow, fail-closed adapters. Other PDFs still receive source monitoring.
export function extractProperties(sourceId: string, pages: PageText[]): { materialId: string; properties: PropertyValue[] }[] {
  if (sourceId === "diab-divinycell-h-si") {
    const page = pages.find(p => /Property\s+Test Procedure/.test(normalize(p.text)));
    if (!page) throw new Error("Mechanical-property table not found");
    const text = normalize(page.text);
    if (!/Unit H45 H60 H80 H100 H130 H160 H200 H250 Compressive Strength/.test(text) || !/All values measured at \+23°C/.test(text) || !/Properties measured perpendicular to the plane/.test(text)) throw new Error("Grade order or conditions changed; review required");
    const definitions = [
      ["compression-strength", "Compressive Strength", "ASTM D 1621"],
      ["compression-modulus", "Compressive Modulus", "ASTM D1621-B-73"],
      ["tensile-strength", "Tensile Strength", "ASTM D 1623"],
      ["tensile-modulus", "Tensile Modulus", "ASTM D 1623"],
      ["shear-strength", "Shear Strength", "ASTM C 273"],
      ["shear-modulus", "Shear Modulus", "ASTM C 273"],
    ];
    const result = [{ materialId: "divinycell-h45", properties: [] as PropertyValue[] }, { materialId: "divinycell-h250", properties: [] as PropertyValue[] }];
    definitions.forEach(([key, label, method], index) => {
      const next = index < definitions.length - 1 ? definitions[index + 1][1] : "Shear Strain";
      const matches = [...text.matchAll(new RegExp(`${label}(?: 1)? (${method}) MPa Nominal ([\\d. ]+) Minimum ([\\d. ]+) ${next}`, "g"))];
      if (matches.length !== 1) throw new Error(`Cannot unambiguously extract ${label}`);
      const nominal = numbers(matches[0][2], 8), minimum = numbers(matches[0][3], 8);
      if (minimum.some((v, i) => v > nominal[i])) throw new Error("Minimum exceeds nominal; review required");
      result.forEach((record, i) => {
        for (const basis of ["nominal", "minimum"] as const) record.properties.push({ key: `${key}-${basis}`, label, value: (basis === "nominal" ? nominal : minimum)[i === 0 ? 0 : 7], unit: "MPa", basis, method: matches[0][1], conditions: "+23°C; moisture conditioning not specified", direction: index < 4 ? "Perpendicular to sheet plane" : "Direction not specified in this table", sourcePage: page.page, evidence: `${label}; ${i === 0 ? "H45" : "H250"} column; ${basis} row` });
      });
    });
    return result;
  }
  if (sourceId === "hexcel-hrh10-us") {
    if (!pages.some(p => /tested per AMS-STD-401/.test(normalize(p.text)))) throw new Error("Reported test method changed; review required");
    const page = pages.find(p => /HRH-10\s*-\s*1\/8\s*-\s*1\.8/.test(p.text));
    if (!page || !/Room Temperature/i.test(page.text) || !/0\.500 inch thickness/.test(page.text)) throw new Error("HRH-10 grade or conditions not verified");
    const text = normalize(page.text);
    const rows = [...text.matchAll(/HRH-10 - 1\/8 - 1\.8 ([\d. ]+) HRH-10 - 1\/8 - 3\.0/g)];
    if (rows.length !== 1) throw new Error("HRH-10 exact grade row not unique");
    if (!/Compressive Plate Shear Bare Stabilized L Direction W Direction/.test(text)) throw new Error("HRH-10 table headers changed");
    if (!/Strength psi Strength psi Modulus ksi Strength psi Modulus ksi Strength psi Modulus ksi/.test(text)) throw new Error("HRH-10 source units changed");
    const values = numbers(rows[0][1], 11);
    if ([0, 2, 5, 8].some(i => values[i + 1] > values[i])) throw new Error("Minimum exceeds typical; review required");
    const definitions: [string, string, "nominal" | "minimum", string][] = [
      ["Bare compression strength", "psi", "nominal", "Through thickness"], ["Bare compression strength", "psi", "minimum", "Through thickness"],
      ["Stabilized compression strength", "psi", "nominal", "Through thickness"], ["Stabilized compression strength", "psi", "minimum", "Through thickness"],
      ["Compression modulus", "ksi", "nominal", "Through thickness"],
      ["Plate shear strength", "psi", "nominal", "L"], ["Plate shear strength", "psi", "minimum", "L"], ["Plate shear modulus", "ksi", "nominal", "L"],
      ["Plate shear strength", "psi", "nominal", "W"], ["Plate shear strength", "psi", "minimum", "W"], ["Plate shear modulus", "ksi", "nominal", "W"],
    ];
    return [{ materialId: "nomex-aramid", properties: definitions.map(([label, unit, basis, direction], i) => ({ key: `hrh10-${i}`, label, value: values[i], unit, basis, direction, method: "AMS-STD-401; edition not stated", conditions: "Room temperature; 0.500 inch core thickness; typical values stored as nominal", sourcePage: page.page, evidence: `HRH-10 - 1/8 - 1.8; ${label}; ${direction}; ${basis}` })) }];
  }
  if (sourceId === "toray-ex1515") {
    const page = pages.find(p => p.page === 3);
    const text = page ? normalize(page.text) : "";
    const table = text.match(/LAMINATE DATA - TORAY M55J \(78 Msi\/538 GPa\) PAN GRAPHITE\/EX-1515 (.*?) Standard 121°C \(250°F\) Autoclave cure 85 psi, normalized to 60% fiber volume\./)?.[1];
    if (!page || !table) throw new Error("M55J table or process conditions changed; review required");
    const definitions = [["Tensile Strength 0°", "3039", "MPa", "ksi"], ["Tensile Modulus 0°", "3039", "GPa", "Msi"],
      ["Compressive Strength 0°", "6641", "MPa", "ksi"], ["Compressive Modulus 0°", "6641", "GPa", "Msi"],
      ["Flexural Strength 0°", "7264", "MPa", "ksi"], ["Flexural Modulus 0°", "7264", "GPa", "Msi"], ["Interlaminar Shear Strength", "2344", "MPa", "ksi"]];
    const properties = definitions.map(([label, method, unit, usUnit], i): PropertyValue => {
      const rows = [...table.matchAll(new RegExp(`${label} RTD ASTM D ${method} ([\\d.]+) ${unit} ([\\d.]+) ${usUnit}`, "g"))];
      if (rows.length !== 1) throw new Error("M55J row, units, direction or test method changed");
      const value = Number(rows[0][1]), us = Number(rows[0][2]);
      if (!(value > 0 && us > 0)) throw new Error("Invalid source property");
      const discrepancy = Math.abs(value - us * 6.894757293168) / value;
      return { key: `m55j-${i}`, label, value, unit, basis: "nominal", method: `ASTM D ${method}; edition not stated`,
        direction: i === 6 ? "Interlaminar short-beam response; not in-plane shear" : "0°", sourcePage: 3,
        conditions: "RTD as reported; 121°C autoclave cure at 85 psi; normalized to 60% fiber volume",
        evidence: `M55J/EX-1515 table; source also prints ${us} ${usUnit}`,
        ...(discrepancy > .01 ? { review: "Source SI and US values disagree by more than 1%. Retained as printed; exclude from calculation pending supplier clarification." } : {}),
      };
    });
    return [{ materialId: "m55j", properties }];
  }
  return [];
}
