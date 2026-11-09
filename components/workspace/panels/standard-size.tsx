"use client";

import { presetRows, presetsOf, standardOf, unitLabels, unitsOf, type StudioForm } from "@/lib/studio-form";

/** The sizes the picked standard names (ADR-0072), as buttons that copy them into the rows: C1869's Specimens A and B, D3039's Table 2 classes.
 * The numbers are the engine's, in the coupon's units (the page converts nothing); the rows stay editable, and the check judges what is typed. */
export function StandardSize({ form, disabled, onRows }: { form: StudioForm; disabled: boolean; onRows: (rows: StudioForm) => void }) {
  const profile = standardOf(form);
  if (!profile) return null;
  const presets = presetsOf(profile);
  if (!presets.length) return null;
  const units = unitsOf(form);
  const mm = unitLabels(units).length;
  const words = (values: Record<string, number>) => [
    values.width !== undefined && values.length !== undefined ? `${values.width} × ${values.length} ${mm}` : null,
    values.hole_diameter !== undefined ? `a ${values.hole_diameter} ${mm} hole` : null,
    values.tab_length !== undefined ? `${values.tab_length} ${mm} grips` : null,
    values.tab_thickness !== undefined ? `${values.tab_thickness} ${mm} tabs at ${values.tab_bevel}°` : null,
  ].filter(Boolean).join(", ");
  return (
    <div className="ws-sizes" data-testid="standard-sizes">
      <p className="studio-hint">The sizes {profile.designation} names{profile.classes.length ? "; its class follows from your layup, which the check reads" : ""}:</p>
      {presets.map((preset) => {
        const values = preset.values[units] ?? {};
        const thickness = preset.thickness[units];
        return (
          <div className="ws-size" key={preset.key}>
            <button type="button" className="studio-text-button" disabled={disabled} onClick={() => onRows(presetRows(form, profile, preset))}
              data-preset={preset.key}>
              Use {preset.label}
            </button>
            <span className="studio-hint">
              {preset.clause}: {words(values)}{thickness !== null && thickness !== undefined ? `; a ${thickness} ${mm} laminate suggested` : ""}
              {preset.note ? `; ${preset.note}` : ""}.
            </span>
          </div>
        );
      })}
    </div>
  );
}
