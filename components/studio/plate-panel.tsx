"use client";

import { DOF_WORDS, plateWords, regionOptions, type PlateLists, type PlateLoad, type PlateRegion, type PlateSupport } from "@/lib/studio-plate";
import type { StudioForm } from "@/lib/studio-form";

type Props = { form: StudioForm; lists: PlateLists; errors: Record<string, string>; disabled: boolean; onChange: (lists: PlateLists) => void };

const DOFS = [1, 2, 3, 4, 5, 6];

/** The supports, loads and regions of a plate (ADR-0054): one row per entry, each region picked from what the plate offers; a click on
 * the model adds a row too (the studio page wires it). The API's check judges the rows and names the list that is wrong. */
export function PlatePanel({ form, lists, errors, disabled, onChange }: Props) {
  const options = regionOptions(form, lists);
  const regionSelect = (value: string, onPick: (region: string) => void, label: string) => (
    <select value={value} disabled={disabled} aria-label={label} onChange={(e) => onPick(e.target.value)}>
      {options.map((o) => <option key={o.name} value={o.name}>{o.name} ({o.kind})</option>)}
    </select>
  );
  const setSupport = (i: number, support: PlateSupport) => onChange({ ...lists, supports: lists.supports.map((s, k) => (k === i ? support : s)) });
  const setLoad = (i: number, load: PlateLoad) => onChange({ ...lists, loads: lists.loads.map((l, k) => (k === i ? load : l)) });
  const setRegion = (i: number, region: PlateRegion) => onChange({ ...lists, regions: lists.regions.map((r, k) => (k === i ? region : r)) });
  const first = options[0]?.name ?? "Face";
  return (
    <fieldset className="studio-plate" data-testid="plate-panel" disabled={disabled}>
      <legend>Supports and loads over the plate&apos;s regions</legend>
      <p className="studio-hint">Click a region on the model to hold or load it, or add a row here. Regions: the four edges, the face, the tabs when
        there are tabs, the hole&apos;s ring when there is a hole, and the boxes you draw below.</p>
      <h4>Supports {errors.Supports ? <span className="studio-field-error">{errors.Supports}</span> : null}</h4>
      {lists.supports.map((s, i) => (
        <div className="studio-plate-row" key={`s${i}`} data-testid="support-row">
          {regionSelect(s.region, (region) => setSupport(i, { ...s, region }), `Support ${i + 1} region`)}
          <span className="studio-plate-dofs" role="group" aria-label={`Support ${i + 1} directions`}>
            {DOFS.map((d) => (
              <label key={d} title={DOF_WORDS[d]}><input type="checkbox" checked={s.dofs.includes(d)} aria-label={`Support ${i + 1} holds ${DOF_WORDS[d] ?? d}`}
                onChange={(e) => setSupport(i, { ...s, dofs: e.target.checked ? [...s.dofs, d].sort((a, b) => a - b) : s.dofs.filter((x) => x !== d) })} />{d}</label>
            ))}
          </span>
          <input type="text" inputMode="decimal" value={s.value} placeholder="travel (mm, rad)" aria-label={`Support ${i + 1} travel`} className="studio-plate-value"
            onChange={(e) => setSupport(i, { ...s, value: e.target.value })} />
          <button type="button" className="studio-text-button" onClick={() => onChange({ ...lists, supports: lists.supports.filter((_, k) => k !== i) })}>remove</button>
        </div>
      ))}
      <button type="button" className="studio-text-button" data-testid="add-support" onClick={() => onChange({ ...lists, supports: [...lists.supports, { region: first, dofs: [1, 2, 3], value: "" }] })}>+ support</button>
      <h4>Loads {errors.Loads ? <span className="studio-field-error">{errors.Loads}</span> : null}</h4>
      {lists.loads.map((l, i) => (
        <div className="studio-plate-row" key={`l${i}`} data-testid="load-row">
          {regionSelect(l.region, (region) => setLoad(i, { ...l, region }), `Load ${i + 1} region`)}
          <select value={l.kind} aria-label={`Load ${i + 1} kind`} onChange={(e) => setLoad(i, e.target.value === "pressure"
            ? { region: l.region, kind: "pressure", pressure: "" } : { region: l.region, kind: "force", dof: 3, total: "" })}>
            <option value="force">force (N) along</option>
            <option value="pressure">pressure (MPa)</option>
          </select>
          {l.kind === "force" ? (
            <>
              <select value={l.dof} aria-label={`Load ${i + 1} direction`} onChange={(e) => setLoad(i, { ...l, dof: Number(e.target.value) })}>
                {[1, 2, 3].map((d) => <option key={d} value={d}>{DOF_WORDS[d] ?? d}</option>)}
              </select>
              <input type="text" inputMode="decimal" value={l.total} placeholder="total N" aria-label={`Load ${i + 1} total`} className="studio-plate-value"
                onChange={(e) => setLoad(i, { ...l, total: e.target.value })} />
            </>
          ) : (
            <input type="text" inputMode="decimal" value={l.pressure} placeholder="MPa, + against the normal" aria-label={`Load ${i + 1} pressure`} className="studio-plate-value"
              onChange={(e) => setLoad(i, { ...l, pressure: e.target.value })} />
          )}
          <button type="button" className="studio-text-button" onClick={() => onChange({ ...lists, loads: lists.loads.filter((_, k) => k !== i) })}>remove</button>
        </div>
      ))}
      <button type="button" className="studio-text-button" data-testid="add-load" onClick={() => onChange({ ...lists, loads: [...lists.loads, { region: "Face", kind: "pressure", pressure: "" }] })}>+ load</button>
      <h4>Boxes you draw {errors.Regions ? <span className="studio-field-error">{errors.Regions}</span> : null}</h4>
      {lists.regions.map((r, i) => (
        <div className="studio-plate-row" key={`r${i}`} data-testid="region-row">
          <input type="text" value={r.name} placeholder="name" aria-label={`Box ${i + 1} name`} onChange={(e) => setRegion(i, { ...r, name: e.target.value })} />
          {(["x0", "x1", "y0", "y1"] as const).map((key) => (
            <input key={key} type="text" inputMode="decimal" value={r[key]} placeholder={key} aria-label={`Box ${i + 1} ${key}`} className="studio-plate-value"
              onChange={(e) => setRegion(i, { ...r, [key]: e.target.value })} />
          ))}
          <button type="button" className="studio-text-button" onClick={() => onChange({ ...lists, regions: lists.regions.filter((_, k) => k !== i) })}>remove</button>
        </div>
      ))}
      <button type="button" className="studio-text-button" data-testid="add-region" onClick={() => onChange({ ...lists, regions: [...lists.regions, { name: `Box-${lists.regions.length + 1}`, x0: "", x1: "", y0: "", y1: "" }] })}>+ box (x0, x1, y0, y1 in mm)</button>
      {lists.supports.length || lists.loads.length ? (
        <ul className="studio-plate-words" data-testid="plate-words">{plateWords(lists).map((w, i) => <li key={i}>{w}</li>)}</ul>
      ) : <p className="studio-muted">No supports yet: a plate needs at least one, and a load or a support that moves.</p>}
    </fieldset>
  );
}
