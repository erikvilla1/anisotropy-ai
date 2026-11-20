"use client";

import { putHandoff, type Handoff } from "@/lib/handoff";
import { couponProjects, hasWork, laminateProjects, newFeaProject, newLaminateProject, newProject, newWingProject, readProjects, upsert, wingProjects,
  writeProjects, type Project } from "@/lib/project-store";
import { sectionOf, type WorkTarget } from "@/lib/work-intent";
import { WING_HREF, workspace } from "@/lib/workspaces";
import { browserStorage, tabStorage } from "@/components/studio/project-context";

/** The project a section opens with for a target (ADR-0124): its newest project when that holds no work, set up for the target, else a
 * new one, so a message carried over never lands in someone's work. The project left behind stays in the list. CAD keeps no projects; a
 * wing is a project of its own kind (ADR-0122), new from the example unless the newest is still the example (ADR-0118 amendment 1). */
export function projectFor(target: WorkTarget, list: Project[]): Project | null {
  if (target === "cad") return null;
  if (target === "laminate") {
    const newest = laminateProjects(list)[0];
    return newest && !hasWork(newest) ? newest : newLaminateProject();
  }
  if (target === "wing") {
    const newest = wingProjects(list)[0];
    return newest && !hasWork(newest) ? newest : newWingProject();
  }
  const newest = couponProjects(list)[0];
  if (target === "coupon") return newest && !hasWork(newest) ? { ...newest, analysis: "coupon" } : newProject();
  return newest && newest.analysis === "none" ? newest : newFeaProject(); // FEA itself
}

/** Opens the section a target is worked in (a wing on its own page under FEA), with its project first in this browser's list and the
 * message carried to its assistant. */
export function goTo(target: WorkTarget, carried: Partial<Handoff>, push: (href: string) => void): void {
  const store = browserStorage();
  const list = readProjects(store);
  const project = projectFor(target, list);
  if (project) writeProjects(upsert(list, project), store);
  if (target === "wing") { push(WING_HREF); return; } // the wing's page has no chat to take a message yet (step 5 of its plan)
  putHandoff(tabStorage(), carried);
  push(workspace(sectionOf(target)).href);
}
