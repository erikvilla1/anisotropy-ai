"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { projectTitle } from "@/lib/project-store";
import { CouponChat, CouponSpec } from "@/components/studio/coupon-chat";
import { CouponStudio } from "@/components/studio/coupon-studio";
import { ImportedStage } from "@/components/studio/imported-stage";
import { PastStage } from "@/components/studio/past-stage";
import { ProjectProvider, useProject } from "@/components/studio/project-context";
import { TowStage } from "@/components/studio/tow-stage";
import { isTow } from "@/lib/studio-tow";
import { feaKind, workspace } from "@/lib/workspaces";
import { FeaRail } from "./fea-rail";
import { FeaStartChat, FeaStartRail, FeaStartStage } from "./fea-start";
import { goTo } from "./go-to";
import { ImportRail } from "./import-rail";
import { PastRail } from "./past-rail";
import { TensionScreen } from "./tension-screen";
import { WorkspaceShell } from "./shell";

/** The FEA section (ADR-0062, ADR-0124): one panel per step on the left, the sketch, the model and the results in the centre, the
 * assistant on the right, all three on the one project store. A project not set up yet has an empty model tree and the FEA assistant,
 * which answers questions and sets it up for a kind of work, a coupon test today. A model brought in as a file takes the left and the
 * centre while it is open, and the assistant answers from it (ADR-0105); so does a past analysis opened again (ADR-0109). */
export function FeaWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const router = useRouter();
  return (
    <ProjectProvider apiBaseUrl={apiBaseUrl}>
      <FeaColumns apiBaseUrl={apiBaseUrl} onSwitch={(target, carried) => goTo(target, { prompt: carried }, router.push)} />
    </ProjectProvider>
  );
}

function FeaColumns({ apiBaseUrl, onSwitch }: { apiBaseUrl: string; onSwitch: (target: "laminate" | "cad" | "wing", carried: string) => void }) {
  const { project, form, rename, allTests, imported, past } = useProject();
  // The columns are drawn once the page runs in the browser: what they show is this browser's project and the address's `?for=`, which
  // the prerendered page cannot know, and a blank FEA project and a coupon differ in every column (ADR-0124)
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const blank = project.analysis === "none" && !imported.open && !past.open; // nothing set up yet (ADR-0124)
  if (!mounted) return null;
  // the tension screen (ADR-0090) leaves the test, the size and the pull to the software: the strip shows what it chose once checked
  return (
    <WorkspaceShell
      kind={project.analysis === "none" ? workspace("fea").title : `${workspace("fea").title} · ${feaKind(project.analysis).title}`}
      title={<input type="text" aria-label="Project name" value={project.name} placeholder={projectTitle(project)} onChange={(e) => rename(e.target.value)} data-testid="project-name" />}
      // a model brought in as a file has the left and the centre while it is open (ADR-0105); the coupon's rows wait behind it
      // a past analysis opened again has them too, shown as it was solved (ADR-0109); the project's rows wait behind it
      rail={blank ? <FeaStartRail /> : imported.open ? <ImportRail apiBaseUrl={apiBaseUrl} /> : past.open ? <PastRail apiBaseUrl={apiBaseUrl} />
        : allTests ? <FeaRail apiBaseUrl={apiBaseUrl} /> : <TensionScreen apiBaseUrl={apiBaseUrl} />}
      stage={blank ? <FeaStartStage /> : imported.open ? <ImportedStage apiBaseUrl={apiBaseUrl} /> : past.open ? <PastStage apiBaseUrl={apiBaseUrl} />
        // the model tree says the setup tab by tab (ADR-0111), so its view gives the model the room the summary strip took
        : isTow(form) && allTests ? <TowStage /> : allTests ? <><CouponSpec form={form} /><CouponStudio apiBaseUrl={apiBaseUrl} /></>
        : <CouponStudio apiBaseUrl={apiBaseUrl} />}
      assistant={blank ? <FeaStartChat /> : <CouponChat apiBaseUrl={apiBaseUrl} onSwitch={onSwitch} />}
    />
  );
}
