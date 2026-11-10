"use client";

import { fieldByKey, NO_STANDARD, standardsFor, testDescription, type StudioForm } from "@/lib/studio-form";
import { TEST_CHOICES } from "@/lib/studio-chat";

const titleOf = (test: string) => TEST_CHOICES.find((c) => c.test === test)?.title ?? test.charAt(0).toUpperCase() + test.slice(1);

/** One question of the first step as a list of choices, each a card with its words under it (ADR-0062 amendment 1). */
function Choices({ name, question, hint, options, value, disabled, onPick }: {
  name: string; question: string; hint?: string; options: { value: string; title: string; detail: string }[]; value: string; disabled: boolean;
  onPick: (value: string) => void;
}) {
  return (
    <fieldset className="ws-question" data-testid={`question-${name}`} disabled={disabled}>
      <legend>{question}</legend>
      {hint ? <p className="studio-hint">{hint}</p> : null}
      <div className="ws-choices" role="radiogroup" aria-label={question}>
        {options.map((option) => {
          const id = `ws-${name}-${option.value.replace(/[^a-z0-9]+/gi, "-")}`;
          return (
            <label key={option.value} className="ws-choice" data-checked={value === option.value} data-value={option.value}>
              <input type="radio" name={`ws-${name}`} value={option.value} checked={value === option.value} aria-label={option.title}
                aria-describedby={`${id}-detail`} onChange={() => onPick(option.value)} />
              <span className="ws-choice-title">{option.title}</span>
              <span className="ws-choice-detail" id={`${id}-detail`}>{option.detail}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

/** The first step of the coupon setup (ADR-0062 amendment 1): what test the coupon is, then which of our standards it follows, or none. The
 * standards offered are those that cover the test picked (ADR-0072); a test our list holds no standard for says so instead of offering an
 * empty choice. Picking writes the Test and Standard rows, as the rows did before; the check still judges them (ADR-0051). */
export function TestStep({ form, disabled, onChange }: { form: StudioForm; disabled: boolean; onChange: (key: string, value: string) => void }) {
  const tests = (fieldByKey.test?.words ?? []).map((test) => ({ value: test, title: titleOf(test), detail: testDescription(test) }));
  const offered = form.test ? standardsFor(form.test) : [];
  return (
    <div className="ws-test-step" data-testid="test-step">
      <Choices name="test" question="What test are you setting up?" options={tests} value={form.test ?? ""} disabled={disabled}
        hint="The test decides what the next steps ask for: grips and tabs for a pulled strip, supports and a span for bending, regions for a plate."
        onPick={(test) => onChange("test", test)} />
      {!form.test ? null : offered.length ? (
        <Choices name="standard" question={`Which standard does the ${form.test} specimen follow?`} value={form.standard || NO_STANDARD} disabled={disabled}
          hint="With a standard, the steps below show what it asks of each of them, and Check setup judges the specimen against its clauses."
          options={[
            ...offered.map((p) => ({ value: p.designation, title: p.designation, detail: p.title })),
            { value: NO_STANDARD, title: "No standard", detail: "your own size or drawing: nothing is judged against a standard's clauses" },
          ]}
          onPick={(designation) => onChange("standard", designation)} />
      ) : (
        <p className="studio-hint" data-testid="no-standard-offered">
          Our list holds no test standard for {form.test} yet, so the size is your own: say where it comes from under Geometry. The check still judges
          every row.
        </p>
      )}
    </div>
  );
}
