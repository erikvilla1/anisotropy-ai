import type { Metadata } from "next";
import { FeaWorkspace } from "@/components/workspace/fea-workspace";
import "../../studio/studio.css";
import "../workspace.css";

export const metadata: Metadata = {
  title: "Coupon FEA | Anisotropy",
  description: "A coupon test set up on the left, checked and solved by the engine and CalculiX, drawn ply by ply in the centre, with the assistant beside it.",
};

/** The coupon FEA workspace (ADR-0062): three columns on one project. `?material=` and `?prompt=` start the assistant's conversation. */
export default function FeaWorkspacePage() {
  return (
    <main id="main" className="studio-page ws-app">
      <FeaWorkspace apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
