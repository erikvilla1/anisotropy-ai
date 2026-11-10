"use client";

import { useEffect, useState, type ReactNode } from "react";
import { libraryOptions } from "@/lib/studio-form";
import {
  CONSTANT_NAMES, libraryThicknessOf, LOAD_NAMES, loadsWithZeros, printedUnit, readLayupLine, systemUnit, unitsOf,
  type ConstantName, type Kind, type LaminateDraft, type LoadName, type OwnConstants, type Quantity, type ReportUnits,
} from "@/lib/laminate-chat";

/** The fields of the laminate workspace's panels (ADR-0062, part 5): each value with its own unit menu, the unit list the engine's table
 * gives for the kind (ADR-0060). Edits write the draft as they are typed; nothing here converts a unit or judges a value. */

export function QuantityField({ id, label, kind, quantity, system, onChange, disabled }: {
  id: string; label: ReactNode; kind: Kind; quantity: Quantity; system: ReportUnits; onChange: (q: Quantity) => void; disabled?: boolean;
}) {
  const unit = quantity.unit || systemUnit(system, kind);
  return (
    <label htmlFor={id} className="lam-field">
      <span>{label}</span>
      <span className="lam-field-row">
        <input id={id} type="text" inputMode="decimal" autoComplete="off" value={quantity.value} disabled={disabled} onChange={(e) => onChange({ value: e.target.value, unit })} />
        <select aria-label={`${typeof label === "string" ? label : id} unit`} value={unit} disabled={disabled} onChange={(e) => onChange({ value: quantity.value, unit: e.target.value })}>
          {unitsOf(kind).map((u) => <option key={u} value={u}>{printedUnit(u)}</option>)}
        </select>
      </span>
    </label>
  );
}

export const blankOwn = (): OwnConstants => ({
  name: "", source: "", E1: { value: "", unit: "" }, E2: { value: "", unit: "" }, G12: { value: "", unit: "" }, nu12: "",
  F1t: { value: "", unit: "" }, F1c: { value: "", unit: "" }, F2t: { value: "", unit: "" }, F2c: { value: "", unit: "" }, F6: { value: "", unit: "" },
});
const KIND_OF: Record<ConstantName, Kind | null> = { E1: "modulus", E2: "modulus", G12: "modulus", nu12: null, F1t: "stress", F1c: "stress", F2t: "stress", F2c: "stress", F6: "stress" };
const LABELS: Record<ConstantName, string> = { E1: "E₁", E2: "E₂", G12: "G₁₂", nu12: "ν₁₂", F1t: "F1t", F1c: "F1c", F2t: "F2t", F2c: "F2c", F6: "F6" };

/** The material: one from the library, or the engineer's own constants, each with its unit. */
export function MaterialFields({ draft, system, disabled, onChange }: {
  draft: LaminateDraft; system: ReportUnits; disabled?: boolean; onChange: (material: LaminateDraft["material"]) => void;
}) {
  const library = draft.material && "library" in draft.material ? draft.material.library : "";
  const own = draft.material && "own" in draft.material ? draft.material.own : null;
  return (
    <div className="lam-material" data-testid="laminate-material">
      <label htmlFor="lam-library" className="lam-field">
        <span>Library material</span>
        <select id="lam-library" value={library} disabled={disabled} onChange={(e) => onChange(e.target.value ? { library: e.target.value } : null)}>
          <option value="">{own ? "(my own constants, below)" : "Pick one…"}</option>
          {libraryOptions.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
      </label>
      <p className="studio-hint">With its cited constants and strengths; or <button type="button" className="studio-text-button" disabled={disabled || !!own} onClick={() => onChange({ own: blankOwn() })}>type your own constants</button>.</p>
      {own ? (
        <div className="lam-own">
          <div className="lam-grid3">
            {CONSTANT_NAMES.map((name) => {
              const kind = KIND_OF[name];
              const id = `lam-${name}`;
              if (kind === null) {
                return (
                  <label key={name} htmlFor={id} className="lam-field"><span>{LABELS[name]} <small>no unit</small></span>
                    <input id={id} type="text" inputMode="decimal" autoComplete="off" value={own.nu12 as string} disabled={disabled} onChange={(e) => onChange({ own: { ...own, nu12: e.target.value } })} /></label>
                );
              }
              return <QuantityField key={name} id={id} label={LABELS[name]} kind={kind} quantity={own[name] as Quantity} system={system} disabled={disabled}
                onChange={(q) => onChange({ own: { ...own, [name]: q } })} />;
            })}
          </div>
          <div className="chat-rows-grid">
            <label htmlFor="lam-name" className="lam-field"><span>Material name</span>
              <input id="lam-name" type="text" autoComplete="off" value={own.name} disabled={disabled} onChange={(e) => onChange({ own: { ...own, name: e.target.value } })} /></label>
            <label htmlFor="lam-source" className="lam-field"><span>Where the numbers come from <small>optional</small></span>
              <input id="lam-source" type="text" autoComplete="off" value={own.source} disabled={disabled} onChange={(e) => onChange({ own: { ...own, source: e.target.value } })} /></label>
          </div>
          <p className="studio-hint">Give all five strengths or none; without them no failure is predicted. Each value keeps the unit on its menu. Your numbers stay with this project and never enter the library.</p>
        </div>
      ) : null}
    </div>
  );
}

/** The layup in laminate notation, read by the assistant's own reader, and the ply thickness with its unit. */
export function LayupFields({ draft, system, disabled, onChange }: {
  draft: LaminateDraft; system: ReportUnits; disabled?: boolean; onChange: (layup: LaminateDraft["layup"], thickness: Quantity | null) => void;
}) {
  const notation = draft.layup?.notation ?? "";
  const [text, setText] = useState(notation);
  const [error, setError] = useState("");
  useEffect(() => { setText(notation); setError(""); }, [notation]); // the assistant may set it
  const recorded = draft.material && "library" in draft.material ? libraryThicknessOf(draft.material.library) : null;
  const thickness = draft.thickness ?? { value: "", unit: systemUnit(system, "length") };
  return (
    <div className="lam-layup-fields" data-testid="laminate-layup">
      <form className="chat-inline ws-layup-notation" onSubmit={(e) => {
        e.preventDefault();
        const line = readLayupLine(text.trim().startsWith("[") ? text : `[${text}]`, system);
        if (!line.layup) { setError(line.refused[0] ?? "Write it as [45/0/-45/90]s, [0/90]2s or [±45]2s."); return; }
        setError("");
        onChange(line.layup, draft.thickness);
      }}>
        <input id="lam-layup" type="text" aria-label="Layup notation" placeholder="[45/0/-45/90]s" value={text} disabled={disabled} autoComplete="off"
          onChange={(e) => { setText(e.target.value); setError(""); }} />
        <button type="submit" className="chat-primary" disabled={disabled}>Use layup</button>
        {error ? <span className="chat-error" role="alert">{error}</span> : null}
      </form>
      <p className="studio-hint">Bottom ply first. Here 0° runs along x, the direction of Nx, as in the textbooks.</p>
      <QuantityField id="lam-thickness" label={recorded === null ? "Ply thickness" : "Ply thickness (optional)"} kind="length" quantity={thickness} system={system} disabled={disabled}
        onChange={(q) => onChange(draft.layup, q)} />
      {recorded !== null && !thickness.value.trim() ? <p className="studio-hint">Ply thickness {Number(recorded.toPrecision(4))} mm from the library record; type one to use another.</p> : null}
    </div>
  );
}

/** The six force and moment resultants per unit width, each with its unit; blanks can be set to zero in one click, never assumed. */
export function LoadsFields({ loads, system, disabled, onChange }: {
  loads: Record<LoadName, Quantity> | null; system: ReportUnits; disabled?: boolean; onChange: (loads: Record<LoadName, Quantity>) => void;
}) {
  const blank = (name: LoadName): Quantity => ({ value: "", unit: systemUnit(system, name.startsWith("N") ? "N" : "M") });
  const current = loads ?? (Object.fromEntries(LOAD_NAMES.map((n) => [n, blank(n)])) as Record<LoadName, Quantity>);
  const blanks = LOAD_NAMES.filter((n) => !current[n].value.trim());
  return (
    <div className="lam-loads-fields" data-testid="laminate-loads">
      <div className="lam-grid3">
        {LOAD_NAMES.map((name) => (
          <QuantityField key={name} id={`lam-${name}`} label={<>{name[0]}<sub>{name.slice(1)}</sub></>} kind={name.startsWith("N") ? "N" : "M"} quantity={current[name]} system={system}
            disabled={disabled} onChange={(q) => onChange({ ...current, [name]: q })} />
        ))}
      </div>
      {blanks.length ? (
        <div className="studio-actions">
          <button type="button" className="studio-text-button" disabled={disabled}
            onClick={() => onChange(loadsWithZeros(Object.fromEntries(LOAD_NAMES.filter((n) => current[n].value.trim()).map((n) => [n, current[n]])), system))}>
            The rest are zero</button>
        </div>
      ) : null}
      <p className="studio-hint">N are forces per unit width, M moments per unit width; compression and reversed moments are negative. Every one of the six is stated; nothing is assumed.</p>
    </div>
  );
}

/** The temperature condition's rows (ADR-0087): the uniform change, and, for a typed material, both expansion coefficients; a library
 * dataset brings its own when it records them, and the solve says so when it does not. Each value keeps the unit it was typed in. */
export function TemperatureFields({ draft, system, disabled, onChange }: {
  draft: LaminateDraft; system: ReportUnits; disabled?: boolean;
  onChange: (patch: Pick<LaminateDraft, "delta_T" | "alphas">) => void;
}) {
  const delta = draft.delta_T ?? { value: "", unit: systemUnit(system, "delta_T") };
  const own = Boolean(draft.material && "own" in draft.material);
  const alphaUnit = systemUnit(system, "alpha").replace(/^1\//, "1e-6/");
  const alphas = draft.alphas ?? { alpha1: { value: "", unit: alphaUnit }, alpha2: { value: "", unit: alphaUnit } };
  return (
    <div className="lam-fields" data-testid="lam-temperature">
      <QuantityField id="lam-delta-t" label="Temperature change ΔT" kind="delta_T" quantity={delta} system={system} disabled={disabled}
        onChange={(q) => onChange({ delta_T: q, alphas: draft.alphas ?? null })} />
      <p className="studio-hint">Negative for cooling, as after a cure. With loads it is held at its value while they grow to failure; with none, the change itself grows to failure.</p>
      {own ? (
        <>
          <QuantityField id="lam-alpha1" label="α₁ along the fibres" kind="alpha" quantity={alphas.alpha1} system={system} disabled={disabled}
            onChange={(q) => onChange({ delta_T: draft.delta_T ?? null, alphas: { ...alphas, alpha1: q } })} />
          <QuantityField id="lam-alpha2" label="α₂ across the fibres" kind="alpha" quantity={alphas.alpha2} system={system} disabled={disabled}
            onChange={(q) => onChange({ delta_T: draft.delta_T ?? null, alphas: { ...alphas, alpha2: q } })} />
        </>
      ) : <p className="studio-hint">A library material uses its dataset&apos;s α₁ and α₂ when the dataset records them; when it does not, the solve says so, and your own constants with their expansion are the way to go.</p>}
    </div>
  );
}
