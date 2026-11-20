import type { Metadata } from "next";
import { WingWorkspace } from "@/components/workspace/wing-workspace";
import "../../studio/studio.css";
import "../workspace.css";

export const metadata: Metadata = {
  title: "Wing analysis",
  description: "A composite wing worked over its flight envelope as you change it: margins of every case, stiffness, mass and the section's shear flow.",
};

/** The wing workspace (ADR-0118): one wing description, worked by the engine's hand calculation on every change. */
export default function WingWorkspacePage() {
  return (
    <main id="main" className="studio-page ws-app">
      <WingWorkspace apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
