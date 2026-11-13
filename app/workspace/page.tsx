import type { Metadata } from "next";
import { WorkspaceChooser } from "@/components/workspace/chooser";
import "../studio/studio.css";
import "./workspace.css";

export const metadata: Metadata = {
  title: "Workspace",
  description: "Your coupon projects, and the tools to analyze them.",
};

/** The workspace's front door (ADR-0062): the projects kept in this browser and one tile per kind of work. */
export default function WorkspacePage() {
  return (
    <main id="main" className="studio-page ws-page">
      <WorkspaceChooser apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
