"use client";

import { checkText } from "@/lib/studio-copy";
import { enabledStandards } from "@/lib/enabled-tests";
import { standardOf, standardsFor, type Checklist, type StudioForm } from "@/lib/studio-form";
import { RequirementTable } from "./requirement-table";

/** The standard the coupon follows (ADR-0072): its subject, the copy we read and where the publisher sells it; before a check, what the check
 * will judge, clause by clause; after it, each requirement with this coupon's value and the verdict, and the check's own summary. The model
 * is checked against the standard's specimen, never said to conform: the procedure stays the laboratory's. */
export function StandardCard({ form, checklist, tow = false, allTests = false }: { form: StudioForm; checklist: Checklist | null; tow?: boolean; allTests?: boolean }) {
  // a fibre tow record (ADR-0074) is a test record judged as entered, not a modelled specimen
  const action = tow ? "Calculate" : "Check setup", subject = tow ? "This record" : "This coupon";
  const profile = standardOf(form);
  if (!profile) {
    const offered = form.test ? enabledStandards(standardsFor(form.test), allTests) : []; // the standards the studio offers (ADR-0089)
    return offered.length ? (
      <p className="studio-hint" data-testid="standard-card">
        {tow ? "No standard picked: the record is reduced by the tow equations and judged against no clause." : "No standard picked: the size is your own."}{" "}
        Pick {offered.map((p) => p.designation).join(" or ")} under Standard to have the {tow ? "record" : "specimen"} checked against its clauses.
      </p>
    ) : null;
  }
  const item = checklist?.items.find((i) => i.id === "standard");
  const judged = item?.requirements?.length ? item.requirements : null;
  return (
    <div className="ws-standard" data-testid="standard-card">
      <p className="ws-standard-head">
        <strong>{profile.designation}</strong> <span className="studio-muted">{profile.title}</span>
      </p>
      <p className="studio-hint">
        Each requirement below carries its clause, in our words; read the clause in your own copy (the standard is sold by {profile.organisation}:{" "}
        <a href={profile.catalog_url} target="_blank" rel="noreferrer">its page</a>). Edition: {profile.edition_note}. Values in {profile.systems}.
      </p>
      {judged && item ? (
        <>
          <p className={`ws-standard-summary ws-standard-${item.state}`} data-testid="standard-summary">{checkText(item)}</p>
          <details open>
            <summary>Each requirement, judged on this {tow ? "record" : "coupon"}</summary>
            <RequirementTable requirements={judged} judged subject={subject} />
          </details>
        </>
      ) : (
        <details>
          <summary>What {action} will judge ({profile.requirements.filter((r) => r.level !== "lab").length} requirements, {profile.requirements.filter((r) => r.level === "lab").length} laboratory clauses)</summary>
          <RequirementTable requirements={profile.requirements} judged={false} />
        </details>
      )}
      <p className="studio-hint">{tow
        ? "The record as entered is checked: a deviation is reported and the numbers still come; the procedure is the laboratory's, and nothing here witnesses the test. Not a certification."
        : "The specimen as modelled is checked, never the test: a deviation is reported and the run goes on; the procedure is the laboratory's. Not a certification."}</p>
    </div>
  );
}
