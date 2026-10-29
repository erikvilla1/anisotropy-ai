"use client";

import { libraryOptions, PLY_KEYS, sectionsFor, shortHelp, type FieldDefinition, type StudioForm } from "@/lib/studio-form";

type Props = { form: StudioForm; errors: Record<string, string>; disabled: boolean; onChange: (key: string, value: string) => void };

function Field({ field, value, error, disabled, onChange }: { field: FieldDefinition; value: string; error?: string; disabled: boolean; onChange: (value: string) => void }) {
  const id = `studio-${field.key}`;
  const describedBy = error ? `${id}-error` : `${id}-hint`;
  const label = <span className="studio-label-row"><label htmlFor={id}>{field.label}</label>{field.required ? <span className="studio-required" aria-hidden="true">*</span> : null}</span>;
  let control;
  if (field.key === "library") {
    control = (
      <select id={id} value={value} disabled={disabled} aria-invalid={Boolean(error)} aria-describedby={describedBy} onChange={(e) => onChange(e.target.value)}>
        <option value="">own constants below</option>
        {libraryOptions.map((m) => <option key={m.id} value={m.id}>{m.id}: {m.name}</option>)}
      </select>
    );
  } else if (field.kind === "list" && field.words.length) {
    control = (
      <select id={id} value={value} disabled={disabled} aria-invalid={Boolean(error)} aria-describedby={describedBy} onChange={(e) => onChange(e.target.value)}>
        {field.required ? null : <option value="">(blank)</option>}
        {field.words.map((word) => <option key={word} value={word}>{word}</option>)}
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

export function CouponForm({ form, errors, disabled, onChange }: Props) {
  return (
    <div className="studio-form" data-testid="studio-form">
      {sectionsFor(form).map((section) => {
        const plies = section.fields.filter((f) => PLY_KEYS.includes(f.key));
        const others = section.fields.filter((f) => !PLY_KEYS.includes(f.key));
        return (
          <fieldset key={section.title} disabled={disabled}>
            <legend>{section.title}</legend>
            {plies.length ? (
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
            ) : null}
            {others.length ? (
              <div className="studio-field-grid">
                {others.map((field) => <Field key={field.key} field={field} value={form[field.key] ?? ""} error={errors[field.key]} disabled={disabled}
                  onChange={(value) => onChange(field.key, value)} />)}
              </div>
            ) : null}
          </fieldset>
        );
      })}
    </div>
  );
}
