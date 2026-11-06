import type { Metadata } from "next";
import { WorkspaceChooser } from "@/components/workspace/chooser";
import "../studio/studio.css";
import "./workspace.css";

export const metadata: Metadata = {
  title: "Workspace | Anisotropy",
  description: "Your coupon projects and the workspaces: a coupon test by finite elements, a laminate under loads, and geometry from CAD, planned.",
};

/** The workspace's front door (ADR-0062): the projects kept in this browser and one tile per kind of work. */
export default function WorkspacePage() {
  return (
    <main id="main" className="studio-page ws-page">
      <WorkspaceChooser />
    </main>
  );
}
