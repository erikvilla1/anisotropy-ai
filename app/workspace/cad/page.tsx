import type { Metadata } from "next";
import { CadWorkspace } from "@/components/workspace/cad-workspace";
import "../../studio/studio.css";
import "../workspace.css";

export const metadata: Metadata = {
  title: "CAD",
  description: "Shapes and dimensions for a composite model. Being built.",
};

/** The CAD section (ADR-0124): the three columns with an empty feature tree, while CAD is being built. */
export default function CadWorkspacePage() {
  return (
    <main id="main" className="studio-page ws-app">
      <CadWorkspace />
    </main>
  );
}
