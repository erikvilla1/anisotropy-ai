import type { Metadata } from "next";
import { LaminateWorkspace } from "@/components/workspace/laminate-workspace";
import "../../studio/studio.css";
import "../workspace.css";

export const metadata: Metadata = {
  title: "Laminate response | Anisotropy",
  description: "A stack under loads per unit width: the ABD matrices, the strains, every ply's stresses and first-ply failure, in the units you pick.",
};

/** The laminate response workspace (ADR-0062, part 5): the problem's panels, the stack and the answer, the laminate assistant of ADR-0060 beside them. */
export default function LaminateWorkspacePage() {
  return (
    <main id="main" className="studio-page ws-app">
      <LaminateWorkspace apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
