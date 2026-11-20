"use client";

import { putHandoff, type Handoff } from "@/lib/handoff";
import { couponProjects, hasWork, laminateProjects, newFeaProject, newLaminateProject, newProject, readProjects, upsert, writeProjects,
  type Project } from "@/lib/project-store";
import { sectionOf, type WorkTarget } from "@/lib/work-intent";
import { workspace } from "@/lib/workspaces";
import { browserStorage, tabStorage } from "@/components/studio/project-context";

/** The project a section opens with for a target (ADR-0124): its newest project when that holds no work, set up for the target, else a
 * new one, so a message carried over never lands in someone's work. The project left behind stays in the list. CAD keeps no projects. */
export function projectFor(target: WorkTarget, list: Project[]): Project | null {
  if (target === "cad") return null;
  if (target === "laminate") {
    const newest = laminateProjects(list)[0];
    return newest && !hasWork(newest) ? newest : newLaminateProject();
  }
  const newest = couponProjects(list)[0];
  if (target === "coupon") return newest && !hasWork(newest) ? { ...newest, analysis: "coupon" } : newProject();
  return newest && newest.analysis === "none" ? newest : newFeaProject(); // FEA itself, or a wing until it is a kind here
}

/** Opens the section a target is worked in, with its project first in this browser's list and the message carried to its assistant. */
export function goTo(target: WorkTarget, carried: Partial<Handoff>, push: (href: string) => void): void {
  const store = browserStorage();
  const list = readProjects(store);
  const project = projectFor(target, list);
  if (project) writeProjects(upsert(list, project), store);
  putHandoff(tabStorage(), carried);
  push(workspace(sectionOf(target)).href);
}
