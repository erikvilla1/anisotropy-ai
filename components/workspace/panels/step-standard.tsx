"use client";

import { standardOf, type Checklist, type JudgedRequirement, type StudioForm } from "@/lib/studio-form";
import { panel, setupLine, stepRequirements, type PanelId } from "@/lib/workspace-panels";
import { RequirementTable } from "@/components/studio/requirement-table";

/** What the coupon's standard asks of one step (ADR-0062 amendment 1): its requirements that name this step's rows, with the check's verdict
 * once a check has run. Folded, with a count in its line, so the step's own rows stay first; the whole standard is on the first step's card. */
export function StepStandard({ form, id, checklist }: { form: StudioForm; id: PanelId; checklist: Checklist | null }) {
  const profile = standardOf(form);
  const requirements = stepRequirements(form, id, checklist);
  if (!profile || !requirements.length) return null;
  const judged = requirements.every((r) => "state" in r);
  const counts = judged ? (requirements as JudgedRequirement[]).reduce<Record<string, number>>((n, r) => ({ ...n, [r.state]: (n[r.state] ?? 0) + 1 }), {}) : {};
  const flagged = (counts.deviation ?? 0) + (counts.advisory ?? 0);
  const tally = judged
    ? [counts.met ? `${counts.met} met` : "", counts.deviation ? `${counts.deviation} deviation${counts.deviation === 1 ? "" : "s"}` : "",
      counts.advisory ? `${counts.advisory} not followed` : ""].filter(Boolean).join(", ")
    : `${requirements.length} requirement${requirements.length === 1 ? "" : "s"}`;
  return (
    <details className="ws-step-standard" data-testid={`step-standard-${id}`} open={flagged > 0}>
      <summary>What {profile.designation} asks of the {panel(id).title.toLowerCase()}{tally ? `: ${tally}` : ""}</summary>
      <RequirementTable requirements={requirements} judged={judged} />
    </details>
  );
}

/** The rail's head (ADR-0062 amendment 1): what the engineer is setting up, the test and the standard, in one line that stays above the steps. */
export function SetupLine({ form }: { form: StudioForm }) {
  const setup = setupLine(form);
  if (!setup) {
    return <p className="ws-setup-line" data-testid="setup-line" data-state="none">Start with step 1: pick the test, then its standard.</p>;
  }
  const specimen = setup.specimen ? `, Specimen ${setup.specimen}` : "";
  return (
    <p className="ws-setup-line" data-testid="setup-line" data-state={setup.standard ? "standard" : "own"}>
      <span className="studio-muted">Setting up</span> <strong>{setup.test}</strong>{" "}
      {setup.standard ? <>under <strong>{setup.standard.designation}</strong>{specimen}</>
        : setup.offered.length ? <>to your own size, under no standard</> : <>to your own size (no standard for it in our list yet)</>}
    </p>
  );
}
