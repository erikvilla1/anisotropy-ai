"use client";
import { useState } from "react";
import Link from "next/link";
import { dualUnits, propertyGroup, propertyGroups, propertyName } from "@/lib/property-units";

export type DisplayProperty = { key: string; label: string; value: string | number; unit: string; symbol?: string; context?: string; note?: string; referenceUrl?: string };

export function PropertyTable({ properties }: { properties: DisplayProperty[] }) {
  const [filter, setFilter] = useState("All properties");
  const groups = propertyGroups.filter(group => properties.some(p => propertyGroup(p.label) === group));
  return <>
    <div className="property-filters" aria-label="Filter properties">{["All properties", ...groups].map(group => <button type="button" key={group} aria-pressed={filter === group} onClick={() => setFilter(group)}>{group}</button>)}</div>
    <div className="table-scroll simple-property-table"><table>
      <thead><tr><th scope="col">Property</th><th scope="col">English / imperial</th><th scope="col">SI / metric</th></tr></thead>
      {groups.filter(group => filter === "All properties" || group === filter).map(group => <tbody key={group}>
        <tr className="property-group"><th colSpan={3} scope="rowgroup">{group}</th></tr>
        {properties.filter(p => propertyGroup(p.label) === group).map(p => { const values = dualUnits(p.value, p.unit); return <tr key={p.key} data-property={p.key} className={p.note ? "flagged-property" : ""}>
          <th scope="row"><span className="property-name">{p.referenceUrl ? p.referenceUrl.startsWith("/") ? <Link href={p.referenceUrl} aria-label={`${propertyName(p.label)} — view reference`}>{propertyName(p.label)} ↗</Link> : <a href={p.referenceUrl} target="_blank" rel="noreferrer" aria-label={`${propertyName(p.label)} — view reference`}>{propertyName(p.label)} ↗</a> : propertyName(p.label)}</span>{(p.symbol || p.context) && <small>{[p.symbol, p.context].filter(Boolean).join(" · ")}</small>}{p.note && <details className="value-note"><summary>Value needs clarification</summary><p>{p.note} Both columns convert the printed value without correcting it.</p></details>}</th>
          <td>{values.english}</td><td>{values.si}</td>
        </tr>; })}
      </tbody>)}
    </table></div>
  </>;
}
