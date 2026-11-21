import type { Metadata } from "next";
import { RepairWorkspace } from "@/components/workspace/repair-workspace";
import "../../studio/studio.css";
import "../workspace.css";
import "../canvas.css";
import "../repair.css";

export const metadata: Metadata = {
  title: "Patch repair",
  description: "A stepped patch bonded to a composite laminate: the bondline's stresses by hand as you change it, its slice solved on request, and a report.",
};

/** The repair's page (ADR-0135): one repair description, worked by the engine's hand calculation on every change and as a solved
 * slice on request, in layout D (ADR-0134). */
export default function RepairWorkspacePage() {
  return (
    <main id="main" className="studio-page ws-app cv-app">
      <RepairWorkspace apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
