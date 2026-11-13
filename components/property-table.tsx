"use client";
import { useState } from "react";
import Link from "next/link";
import { dualUnits, englishStressUnit, printedColumn, printedElsewhere, propertyGroup, propertyGroups, propertyName } from "@/lib/property-units";

export type DisplayProperty = { key: string; label: string; value: string | number; unit: string; symbol?: string; context?: string; note?: string; referenceUrl?: string };

/** The header tags the column most rows were printed in "as printed" and the other "converted"; a row printed in the other
 * column says so on its context line. One English stress unit serves every MPa row of the table. */
export function PropertyTable({ properties, caption }: { properties: DisplayProperty[]; caption: string }) {
  const [filter, setFilter] = useState("All properties");
  const groups = propertyGroups.filter(group => properties.some(p => propertyGroup(p.label) === group));
  const column = printedColumn(properties.map(p => p.unit));
  const tags = column === "english" ? { english: "as printed", si: "converted" } : column === "si" ? { english: "converted", si: "as printed" } : { english: "", si: "" };
  const stressUnit = englishStressUnit(properties);
  return <>
    <div className="property-filters" role="group" aria-label="Filter properties">{["All properties", ...groups].map(group => <button type="button" key={group} aria-pressed={filter === group} onClick={() => setFilter(group)}>{group}</button>)}</div>
    <div className="table-scroll simple-property-table"><table>
      <caption className="sr-only">{caption}</caption>
      <thead><tr><th scope="col">Property</th>
        <th scope="col">English / imperial{tags.english && <> <span className="column-tag">{tags.english}</span></>}</th>
        <th scope="col">SI / metric{tags.si && <> <span className="column-tag">{tags.si}</span></>}</th></tr></thead>
      {groups.filter(group => filter === "All properties" || group === filter).map(group => <tbody key={group}>
        <tr className="property-group"><th colSpan={3} scope="rowgroup">{group}</th></tr>
        {properties.filter(p => propertyGroup(p.label) === group).map(p => { const values = dualUnits(p.value, p.unit, { stressUnit }); const context = [p.symbol, p.context, printedElsewhere(p.unit, column)].filter(Boolean).join(" · "); return <tr key={p.key} data-property={p.key} className={p.note ? "flagged-property" : ""}>
          <th scope="row"><span className="property-name">{p.referenceUrl ? p.referenceUrl.startsWith("/") ? <Link href={p.referenceUrl} aria-label={`${propertyName(p.label)} — view reference`}>{propertyName(p.label)}</Link> : <a href={p.referenceUrl} target="_blank" rel="noreferrer" aria-label={`${propertyName(p.label)} — view reference (opens in a new tab)`}>{propertyName(p.label)} ↗</a> : propertyName(p.label)}</span>{context && <small>{context}</small>}{p.note && <details className="value-note"><summary>Value needs clarification</summary><p>{p.note} Both columns convert the printed value without correcting it.</p></details>}</th>
          <td>{values.english}</td><td>{values.si}</td>
        </tr>; })}
      </tbody>)}
    </table></div>
    <p className="units-note">Converted values are calculated from the printed values and may differ from the source&apos;s own rounding.</p>
  </>;
}
