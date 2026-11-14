"use client";

import { useRouter } from "next/navigation";
import { projectTitle } from "@/lib/project-store";
import { CouponChat, CouponSpec } from "@/components/studio/coupon-chat";
import { CouponStudio } from "@/components/studio/coupon-studio";
import { ProjectProvider, useProject } from "@/components/studio/project-context";
import { TowStage } from "@/components/studio/tow-stage";
import { isTow } from "@/lib/studio-tow";
import { underD3039 } from "@/lib/tension-screen";
import { formDefinition, unitLabels, type StudioForm } from "@/lib/studio-form";
import { workspace } from "@/lib/workspaces";
import { FeaRail } from "./fea-rail";
import { TensionScreen } from "./tension-screen";
import { WorkspaceShell } from "./shell";

/** The coupon FEA workspace (ADR-0062): one panel per step on the left, the sketch, the model and the results in the centre, the coupon
 * assistant on the right, all three on the one project store. */
export function FeaWorkspace({ apiBaseUrl }: { apiBaseUrl: string }) {
  const router = useRouter();
  return (
    <ProjectProvider apiBaseUrl={apiBaseUrl}>
      <FeaColumns apiBaseUrl={apiBaseUrl} onLaminate={() => router.push("/workspace/laminate")} />
    </ProjectProvider>
  );
}

function FeaColumns({ apiBaseUrl, onLaminate }: { apiBaseUrl: string; onLaminate: () => void }) {
  const { project, form, rename, allTests, run } = useProject();
  // the tension screen (ADR-0090) leaves the test, the size and the pull to the software: the strip shows what it chose once checked
  const built = run.checked?.checklist.built ?? [];
  const shown: StudioForm = allTests ? form : { ...form, test: form.test || "unnotched tension",
    ...Object.fromEntries(built.filter((b) => !(form[b.row] ?? "").trim()).map((b) => [b.row, String(b.value)])) };
  // before the check, the size's source and the load the package will apply, in the words the strip uses once checked (audit fea-screens-J1-3)
  const pull = formDefinition.tension;
  const fallback = allTests ? undefined : { Size: underD3039(form) ? "ASTM D3039, Table 2" : "your size",
    Load: pull ? `${pull.value} ${unitLabels(pull.units).length} ${pull.control}` : "" };
  return (
    <WorkspaceShell
      kind={workspace("fea").title}
      title={<input type="text" aria-label="Project name" value={project.name} placeholder={projectTitle(project)} onChange={(e) => rename(e.target.value)} data-testid="project-name" />}
      rail={allTests ? <FeaRail apiBaseUrl={apiBaseUrl} /> : <TensionScreen apiBaseUrl={apiBaseUrl} />}
      stage={isTow(form) && allTests ? <TowStage /> : <><CouponSpec form={shown} fallback={fallback} /><CouponStudio apiBaseUrl={apiBaseUrl} /></>}
      assistant={<CouponChat apiBaseUrl={apiBaseUrl} onLaminate={onLaminate} />}
    />
  );
}
