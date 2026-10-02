"use client";
import { useState } from "react";
import type { Material } from "@/lib/materials";
import type { MaterialFeed } from "@/lib/material-evidence";
import { AnalysisProperties } from "./analysis-properties";
import { ManufacturerProperties, referenceRelease } from "./material-provenance";

export function MaterialProperties({ material, feed }: { material: Material; feed: MaterialFeed | null }) {
  const release = referenceRelease(material.id, feed);
  const [selection, setSelection] = useState<"manufacturer" | "appendix" | null>(null);
  const selected = selection || (release ? "manufacturer" : "appendix");
  return <div className="material-properties">
    {release && <label className="dataset-picker">Reference<select aria-label="Property reference" value={selected} onChange={e => setSelection(e.target.value as "manufacturer" | "appendix")}><option value="manufacturer">Manufacturer datasheet</option><option value="appendix">Appendix F · material properties</option></select></label>}
    {selected === "manufacturer" && release ? <ManufacturerProperties id={material.id} feed={feed}/> : <AnalysisProperties material={material}/>}
  </div>;
}
