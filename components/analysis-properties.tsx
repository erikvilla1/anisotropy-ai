"use client";
import { useState } from "react";
import { ArrowDownToLine, ArrowUpRight } from "lucide-react";
import type { Material } from "@/lib/materials";
import { downloadFile } from "@/lib/demo";
import { assessAnalysis, analysisPacket, analysisPurposes, propertyIssue, schoolCitation, type AnalysisPurpose } from "@/lib/material-analysis";
import { PropertyTable } from "./property-table";

export function AnalysisProperties({ material }: { material: Material }) {
  const [purpose, setPurpose] = useState<AnalysisPurpose>(material.family === "Sandwich cores" ? "core-elastic" : "in-plane-elastic");
  const [acknowledged, setAcknowledged] = useState(false);
  const [error, setError] = useState("");
  const citation = schoolCitation(material), assessment = assessAnalysis(material, purpose);
  const purposes = material.family === "Sandwich cores" ? ["core-elastic", "mass"] as const : ["in-plane-elastic", "laminate-elastic", "strength-screening", "mass"] as const;
  return <section className="school-properties" aria-label="Appendix properties">
    <div className="property-reference"><span>Reference</span><a href={citation.url} target="_blank" rel="noreferrer">Appendix F: Material Properties · v2 · PDF page {material.page} <ArrowUpRight size={14}/></a><small>Published 1 Feb 2026{material.basis.startsWith("Updated ") ? ` · Material record: ${material.basis.slice(8)}` : ""}</small></div>
    <p className="dataset-context">{material.process !== "Not specified" ? `${material.process}. ` : ""}Test conditions not specified in this reference.</p>
    <PropertyTable properties={material.properties.map(p => { const issue = propertyIssue(material, p); return { key: p.symbol, symbol: p.symbol, label: p.label, value: p.value, unit: p.unit, note: issue && issue !== "Not provided" && !issue.startsWith("Range or") ? issue : undefined }; })}/>
    <p className="units-note">Both columns describe the same property. Compressive strengths retain the reference's negative sign. “Not provided” means the reference has no value.</p>
    <details className="school-citation"><summary>Reference notes</summary><p>{citation.underlyingReference}</p><p>{citation.conditions}</p><p>{citation.method}</p><p>Preliminary analysis requires matching the material and conditions to your application. These values are not qualified design allowables.</p><p className="provenance-caption">Source fingerprint: {citation.sha256}</p></details>
    <details className="analysis-export"><summary>Export inputs for analysis</summary><div className="analysis-input-panel">
      <label>Check inputs for<select aria-label="Analysis input purpose" value={purpose} onChange={e => { setPurpose(e.target.value as AnalysisPurpose); setAcknowledged(false); setError(""); }}>{purposes.map(key => <option value={key} key={key}>{analysisPurposes[key]}</option>)}</select></label>
      <strong>{assessment.inputsAvailable ? "Required inputs available" : "Additional input or correction needed"}</strong>
      <p>{assessment.use}</p>
      {assessment.problems.length > 0 && <ul>{assessment.problems.map(problem => <li key={problem}>{problem}</li>)}</ul>}
      {assessment.inputsAvailable && <label className="analysis-ack"><input type="checkbox" checked={acknowledged} onChange={e => setAcknowledged(e.target.checked)}/> I will document the material match and source-condition assumptions for my preliminary analysis.</label>}
      <button className="button small" disabled={!assessment.inputsAvailable || !acknowledged} onClick={() => { try { downloadFile(`${material.id}-${purpose}-inputs.json`, JSON.stringify(analysisPacket(material.id, purpose, acknowledged), null, 2), "application/json"); } catch (e) { setError(e instanceof Error ? e.message : "Export failed"); } }}><ArrowDownToLine size={14}/> Export analysis inputs</button>
      {error && <p role="alert">{error}</p>}
    </div></details>
  </section>;
}
