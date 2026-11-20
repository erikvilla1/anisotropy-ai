import type { Metadata } from "next";
import { FeaWorkspace } from "@/components/workspace/fea-workspace";
import "../../studio/studio.css";
import "../workspace.css";

export const metadata: Metadata = {
  title: "FEA",
  description: "Set up a composite model, run the analysis and review every ply's results. Starts blank: say what you want to analyse.",
};

/** The FEA section (ADR-0062, ADR-0124): three columns on one project, blank until the chat or a pick sets it up. `?for=coupon` and
 * `?material=` open it set up for a coupon; `?prompt=` starts the assistant's conversation. */
export default function FeaWorkspacePage() {
  return (
    <main id="main" className="studio-page ws-app">
      <FeaWorkspace apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
