import type { Metadata } from "next";
import { WorkspaceChooser } from "@/components/workspace/chooser";
import "../studio/studio.css";
import "./workspace.css";

export const metadata: Metadata = {
  title: "Workspace",
  description: "Say what you want to work on, or pick FEA, CAD or Laminate; your projects and analyses.",
};

/** The workspace's front door (ADR-0062, ADR-0124): a box that reads what you want to work on, one tile per section, the projects kept
 * in this browser and on the account, and the finished analyses. */
export default function WorkspacePage() {
  return (
    <main id="main" className="studio-page ws-page">
      <WorkspaceChooser apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
