"use client";

import type { JudgedRequirement, StandardRequirement } from "@/lib/studio-form";

/** How each judgement reads (ADR-0072): a deviation is reported, never refused; a laboratory clause is listed for the test report. */
export const VERDICT_WORDS: Record<JudgedRequirement["state"], string> = {
  met: "met", deviation: "deviation", advisory: "not followed", note: "note", lab: "laboratory's", na: "does not apply",
};
const LEVEL_ORDER = ["scope", "mandatory", "recommended", "note", "lab"];
const LEVEL_WORDS: Record<string, string> = {
  scope: "What the standard covers", mandatory: "What it requires of the specimen", recommended: "What it suggests", note: "Cautions",
  lab: "The procedure: the laboratory's",
};

/** The requirements of a standard, grouped by level, each with its clause; judged (the verdict, this coupon's value and what the clause asks)
 * after a check, or as the list of what the check will judge before one. A list, not a table, so it reads in the narrow rail. Every word
 * comes from the package: the page judges nothing. */
export function RequirementTable({ requirements, judged }: { requirements: (StandardRequirement | JudgedRequirement)[]; judged: boolean }) {
  const groups = LEVEL_ORDER.map((level) => [level, requirements.filter((r) => r.level === level)] as const).filter(([, rows]) => rows.length);
  return (
    <div className="ws-requirements" data-testid="requirement-table">
      {groups.map(([level, rows]) => (
        <section key={level}>
          <h5>{LEVEL_WORDS[level] ?? level}</h5>
          <ul>
            {rows.map((r) => {
              const j = r as JudgedRequirement;
              return (
                <li key={r.id} data-requirement={r.id} data-state={judged ? j.state : undefined}>
                  <span className="ws-requirement-head">
                    <span className="ws-clause">{r.clause}</span>
                    {judged ? <span className={`ws-verdict ws-verdict-${j.state}`}>{VERDICT_WORDS[j.state]}</span> : null}
                  </span>
                  <span>{r.text}</span>
                  {judged && (j.value || j.limit) ? (
                    <span className="studio-hint">{j.value ? <>This coupon: {j.value}</> : null}{j.value && j.limit ? "; " : null}{j.limit ? <>the clause asks: {j.limit}</> : null}</span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
