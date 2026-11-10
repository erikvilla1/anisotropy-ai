"use client";

import { fieldByKey, labelFor, libraryOptions, PLY_KEYS, sectionsFor, shortHelp, unitsOf, wordsFor, type FieldDefinition, type StudioForm } from "@/lib/studio-form";

type Props = { form: StudioForm; errors: Record<string, string>; disabled: boolean; onChange: (key: string, value: string) => void };

/** One row: its label (in the coupon's units), its input or list, and its error or the first sentence of its help. The tow's rows use it too. */
export function Field({ field, value, units, error, disabled, onChange, words = field.words }: {
  field: FieldDefinition; value: string; units: string; error?: string; disabled: boolean; onChange: (value: string) => void; words?: string[];
}) {
  const id = `studio-${field.key}`;
  const describedBy = error ? `${id}-error` : `${id}-hint`;
  const label = <span className="studio-label-row"><label htmlFor={id}>{labelFor(field, units)}</label>{field.required ? <span className="studio-required" aria-hidden="true">*</span> : null}</span>;
  let control;
  if (field.key === "library") {
    control = (
      <select id={id} value={value} disabled={disabled} aria-invalid={Boolean(error)} aria-describedby={describedBy} onChange={(e) => onChange(e.target.value)}>
        <option value="">own constants below</option>
        {libraryOptions.map((m) => <option key={m.id} value={m.id}>{m.id}: {m.name}</option>)}
      </select>
    );
  } else if (field.kind === "list" && words.length) {
    const blank = field.key !== "standard"; // the Standard row's "none" is its blank (ADR-0072); every other list keeps its blank choice
    control = (
      <select id={id} value={value} disabled={disabled} aria-invalid={Boolean(error)} aria-describedby={describedBy} onChange={(e) => onChange(e.target.value)}>
        {blank ? <option value="">{field.required ? "choose one" : "(blank)"}</option> : null}
        {words.map((word) => <option key={word} value={word}>{word}</option>)}
      </select>
    );
  } else {
    const numeric = field.kind === "number" || field.kind === "whole" || field.kind === "angle";
    control = (
      <input id={id} name={field.key} type="text" inputMode={numeric ? "decimal" : undefined} value={value} disabled={disabled}
        aria-invalid={Boolean(error)} aria-describedby={describedBy} onChange={(e) => onChange(e.target.value)} autoComplete="off" />
    );
  }
  return (
    <div className="studio-field">
      {label}
      {control}
      {error ? <span className="studio-field-error" id={`${id}-error`}>{error}</span> : <span className="studio-hint" id={`${id}-hint`}>{shortHelp(field)}</span>}
    </div>
  );
}

/** The sixteen ply rows, bottom ply first, as one row of small inputs. */
export function PlyGrid({ form, errors, disabled, onChange }: Props) {
  const plies = PLY_KEYS.map((key) => fieldByKey[key]);
  return (
    <div className="studio-plies" role="group" aria-label="Ply angles, bottom ply first">
      {plies.map((field, i) => (
        <div className="studio-ply" key={field.key}>
          <label htmlFor={`studio-${field.key}`}>{i + 1}</label>
          <input id={`studio-${field.key}`} name={field.key} type="text" inputMode="decimal" value={form[field.key] ?? ""} disabled={disabled}
            aria-label={field.label} aria-invalid={Boolean(errors[field.key])} onChange={(e) => onChange(field.key, e.target.value)} autoComplete="off" />
        </div>
      ))}
      {plies.some((f) => errors[f.key]) ? <span className="studio-field-error">{plies.map((f) => errors[f.key]).find(Boolean)}</span>
        : <span className="studio-hint">{shortHelp(plies[0])}</span>}
    </div>
  );
}

/** Any subset of rows as a grid, in the given order, only those the test shows (a bending coupon has no tab length); nothing when none. */
export function FieldGrid({ form, keys, errors, disabled, onChange }: Props & { keys: string[] }) {
  const units = unitsOf(form); // the Units row relabels every row with a unit as it changes (ADR-0061)
  const visible = new Set(sectionsFor(form).flatMap((section) => section.fields.map((field) => field.key)));
  const shown = keys.filter((key) => visible.has(key) && fieldByKey[key]).map((key) => fieldByKey[key]);
  if (!shown.length) return null;
  return (
    <div className="studio-field-grid">
      {shown.map((field) => <Field key={field.key} field={field} value={form[field.key] ?? ""} units={units} error={errors[field.key]} disabled={disabled}
        words={wordsFor(field, form)} onChange={(value) => onChange(field.key, value)} />)}
    </div>
  );
}

/** Every row of the form, section by section: the full form as the Excel form lists it (ADR-0046). */
export function CouponForm({ form, errors, disabled, onChange }: Props) {
  const units = unitsOf(form); // the Units row relabels every row with a unit as it changes (ADR-0061)
  return (
    <div className="studio-form" data-testid="studio-form">
      {sectionsFor(form).map((section) => {
        const plies = section.fields.filter((f) => PLY_KEYS.includes(f.key));
        const others = section.fields.filter((f) => !PLY_KEYS.includes(f.key));
        return (
          <fieldset key={section.title} disabled={disabled}>
            <legend>{section.title}</legend>
            {plies.length ? <PlyGrid form={form} errors={errors} disabled={disabled} onChange={onChange} /> : null}
            {others.length ? (
              <div className="studio-field-grid">
                {others.map((field) => <Field key={field.key} field={field} value={form[field.key] ?? ""} units={units} error={errors[field.key]} disabled={disabled}
                  onChange={(value) => onChange(field.key, value)} />)}
              </div>
            ) : null}
          </fieldset>
        );
      })}
    </div>
  );
}
