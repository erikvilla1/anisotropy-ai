"use client";

import { useState, type ReactNode } from "react";
import { Check, CircleAlert } from "lucide-react";
import { changedRows, fixEcho, fixRows } from "@/lib/check-fix";
import { labelFor, libraryOptions, shortHelp, wordsFor, type CheckItem, type FieldDefinition, type StudioForm } from "@/lib/studio-form";

/** The things to fix before running, each with the rows its check names to type in place when the card is the latest (ADR-0062
 * amendment 2): one Apply puts every row typed into the form, and the conversation checks again. A row left as it was is not sent. */
export function CheckIssues({ items, form, units, live, link, onApply }: {
  items: CheckItem[]; form: StudioForm; units: string;
  /** the latest check, with nothing checking: its rows take input */
  live: boolean;
  /** the item's link to its panel or its question */
  link: (item: CheckItem) => ReactNode;
  onApply: (rows: StudioForm, echo: string) => void;
}) {
  const offered = fixRows(items);
  const [typed, setTyped] = useState<StudioForm>({}); // only the rows typed here; the others show the form's value as it is now
  const rows = changedRows(form, typed);
  const any = live && offered.size > 0;
  const list = (
    <ul className="chat-issues">
      {items.map((item) => {
        const fields = live ? offered.get(item.id) : undefined;
        return (
          <li key={item.id} data-item={item.id} className={fields ? "chat-issue-fill" : undefined}>
            <CircleAlert size={14} /> <span><strong>{item.label}:</strong> {item.message}</span>
            {fields ? (
              <div className="chat-fix-rows">
                {fields.map((field) => <FixInput key={field.key} field={field} units={units} words={wordsFor(field, form)} value={typed[field.key] ?? form[field.key] ?? ""}
                  onChange={(value) => setTyped((t) => ({ ...t, [field.key]: value }))} />)}
              </div>
            ) : null}
            {live ? link(item) : null}
          </li>
        );
      })}
    </ul>
  );
  if (!any) return list;
  return (
    <form data-testid="chat-fix" onSubmit={(e) => {
      e.preventDefault();
      if (!Object.keys(rows).length) return;
      onApply(rows, fixEcho(rows, units));
      setTyped({});
    }}>
      {list}
      <div className="chat-actions">
        <button type="submit" className="chat-primary" disabled={!Object.keys(rows).length} data-testid="chat-fix-apply"><Check size={14} /> Apply and check again</button>
      </div>
    </form>
  );
}

/** One row in the chat: its label in the coupon's units, a list for a row of words, a text box otherwise, and the first sentence of its help.
 * Its id is the chat's own, apart from the same row's input on its panel. */
function FixInput({ field, units, words, value, onChange }: { field: FieldDefinition; units: string; words: string[]; value: string; onChange: (value: string) => void }) {
  const id = `chat-fix-${field.key}`;
  const hint = `${id}-hint`;
  const numeric = field.kind === "number" || field.kind === "whole" || field.kind === "angle";
  let control: ReactNode;
  if (field.key === "library") {
    control = (
      <select id={id} value={value} aria-describedby={hint} onChange={(e) => onChange(e.target.value)}>
        <option value="">own constants</option>
        {libraryOptions.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
      </select>
    );
  } else if (field.kind === "list" && words.length) {
    control = (
      <select id={id} value={value} aria-describedby={hint} onChange={(e) => onChange(e.target.value)}>
        {field.key !== "standard" ? <option value="">{field.required ? "choose one" : "(blank)"}</option> : null}
        {words.map((word) => <option key={word} value={word}>{word}</option>)}
      </select>
    );
  } else {
    control = <input id={id} type="text" inputMode={numeric ? "decimal" : undefined} value={value} aria-describedby={hint} onChange={(e) => onChange(e.target.value)}
      autoComplete="off" />;
  }
  return (
    <div className="chat-fix-row">
      <label htmlFor={id}>{labelFor(field, units)}</label>
      {control}
      <small id={hint}>{shortHelp(field).replace(/;$/, "")}</small>
    </div>
  );
}
