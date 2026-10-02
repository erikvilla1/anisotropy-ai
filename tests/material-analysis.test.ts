import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { getDocument } from "pdfjs-dist/legacy/build/pdf.mjs";
import { materials, materialSource } from "../lib/materials";
import { analysisPacket, assessAnalysis, parseProperty, propertyIssue, schoolAudit, siProperty } from "../lib/material-analysis";

const material = (id: string) => materials.find(m => m.id === id)!;
const fullY1 = [531,518,504,490,476,462,448,434,420,405,391,376,363,349,335,321,307,293,279,265,251,237,222,208,193,179,164];
const fullY2 = [556,542,528,514,500,486,472,458,444,430,415,401,387,373,359,345,331,317,303,289,275,261,246,232,217,203,188];
// Cell bounds come from the source's page geometry, independently of library values.
const regions: [string[], number, number[], [number, number][]][] = [
  [["as4-3501", "agp370"], 1, fullY1, [[315,375],[400,475]]],
  [["eglass-3783","m10e-3783","7781-e765"], 2, fullY2, [[310,365],[380,435],[440,485]]],
  [["carbon-ud-nominal","carbon-ud-wet"], 3, [629,615,601,588,574,559,545,531,517,503,489,475], [[185,245],[270,330]]],
  [["carbon-weave-nominal","carbon-weave-wet","carbon-weave-vartm"], 3, [381,367,353,339,325,311,297,283,269,255,241,226], [[185,245],[270,330],[350,415]]],
  [["m55j"], 4, [656,642,628,614,600,586,572,558,544,530,516,502], [[185,245]]],
  [["cf0302"], 4, [421,407,393,380,366,351,337,323,309,295,281,267], [[185,245]]],
  [["glass-ud-nominal","glass-ud-wet"], 5, [642,628,614,600,586,572,558,544,530,516,502,488], [[185,245],[270,330]]],
  [["glass-weave-nominal","glass-weave-wet","glass-weave-vartm"], 5, [393,380,366,352,338,323,309,295,281,267,254,239], [[185,245],[270,330],[350,415]]],
  [["nomex-aramid","aluminum-core","divinycell-h45","divinycell-h250","baltek"], 6, [599,585,571,558,544,530,516,502,488,474], [[175,242],[260,332],[345,405],[415,473],[478,530]]],
];
function canonical(value: string) {
  const cleaned = value.trim().replace(/,/g, "").replace(/–/g, "-");
  if (["", "-", "—", "TBD"].includes(cleaned)) return "missing";
  const number = parseProperty(cleaned);
  return number === null ? cleaned : String(number);
}

test("every school property matches its actual PDF cell, including missing cells and flagged source errors", async () => {
  const bytes = readFileSync("public/assets/documents/material-properties-2026-v2.pdf");
  assert.equal(createHash("sha256").update(bytes).digest("hex"), schoolAudit.sha256, "Changed PDF requires a new source audit");
  assert.deepEqual(readFileSync(`public${materialSource}`), bytes, "The pinned source copy must match the audited document");
  const task = getDocument({ data: new Uint8Array(bytes), verbosity: 0 });
  const pdf = await task.promise;
  let count = 0;
  try {
    for (const [ids, pageNumber, ys, xs] of regions) {
      const content = await (await pdf.getPage(pageNumber)).getTextContent();
      ids.forEach((id, col) => {
        const m = material(id);
        assert.equal(m.properties.length, ys.length);
        m.properties.forEach((p, row) => {
          const cell = content.items.filter(i => "str" in i && i.transform[4] >= xs[col][0] && i.transform[4] < xs[col][1] && Math.abs(i.transform[5] - ys[row]) < 1.2).map(i => "str" in i ? i.str : "").join("").trim();
          const value = pageNumber === 6 ? cell.replace(/\s+(?:ksi|psi|lb\/ft|inch).*$/, "") : cell;
          assert.equal(canonical(p.value), canonical(value), `${id} ${p.symbol}, page ${pageNumber}`);
          count++;
        });
      });
    }
    assert.equal(count, materials.reduce((n, m) => n + m.properties.length, 0));
  } finally { await task.destroy(); }
});

test("SI conversion respects stress, density, thickness, temperature increments and signs", () => {
  const convert = (value: string, unit: string) => siProperty({ symbol: "fixture", label: "fixture", value, unit })!;
  assert.ok(Math.abs(convert("1", "Msi").value - 6.894757293168) < 1e-10);
  assert.ok(Math.abs(convert("1", "ksi").value - 6.894757293168) < 1e-10);
  assert.ok(Math.abs(convert("1", "lb/ft³").value - 16.01846337396) < 1e-9);
  assert.equal(convert("1", "in").value, 25.4);
  assert.equal(convert("-0.50", "10⁻⁶/°F").value, -.9);
  assert.equal(parseProperty("45–49"), null);
  assert.equal(parseProperty("10,500"), 10500);
  assert.equal(parseProperty("TBD"), null);
});

test("availability depends on the requested analysis, never blanket material approval", () => {
  assert.equal(assessAnalysis(material("cf0302"), "in-plane-elastic").inputsAvailable, true);
  assert.equal(assessAnalysis(material("cf0302"), "strength-screening").inputsAvailable, false);
  assert.equal(assessAnalysis(material("glass-ud-nominal"), "in-plane-elastic").inputsAvailable, true);
  assert.equal(assessAnalysis(material("glass-ud-nominal"), "mass").inputsAvailable, false);
  assert.equal(assessAnalysis(material("as4-3501"), "in-plane-elastic").inputsAvailable, true);
  assert.equal(assessAnalysis(material("as4-3501"), "laminate-elastic").inputsAvailable, false);
  assert.equal(assessAnalysis(material("glass-weave-vartm"), "strength-screening").inputsAvailable, false);
  assert.equal(assessAnalysis(material("nomex-aramid"), "in-plane-elastic").inputsAvailable, false);
  const unstable = structuredClone(material("as4-3501"));
  unstable.properties.find(p => p.symbol === "ν12")!.value = "10";
  assert.match(assessAnalysis(unstable, "in-plane-elastic").problems.join(" "), /positive-definite/);
});

test("analysis packets require acknowledgment, exclude flagged inputs and pin the source", () => {
  assert.throws(() => analysisPacket("as4-3501", "in-plane-elastic", false), /Acknowledge/);
  assert.throws(() => analysisPacket("cf0302", "strength-screening", true), /ksi/);
  assert.throws(() => analysisPacket("glass-ud-nominal", "mass", true), /0.700/);
  const packet = analysisPacket("carbon-ud-wet", "strength-screening", true);
  assert.equal(packet.designAllowables, false);
  assert.equal(packet.source.sha256, schoolAudit.sha256);
  assert.ok(packet.properties.find(p => p.symbol === "F1C")!.value > 0);
  assert.equal(packet.properties.find(p => p.symbol === "F1C")!.sourceValue, "-111");
  assert.equal(packet.properties.some(p => p.symbol === "ρ"), false);
  const as4 = material("as4-3501");
  assert.match(propertyIssue(as4, as4.properties.find(p => p.symbol === "β11")!)!, /repeat/);
});
