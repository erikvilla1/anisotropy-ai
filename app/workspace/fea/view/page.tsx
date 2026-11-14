import type { Metadata } from "next";
import { Suspense } from "react";
import { StudioViewer } from "@/components/studio/studio-viewer";
import "../../../studio/studio.css";

export const metadata: Metadata = {
  title: "Results",
  description: "Results of a coupon analysis: the model, first-ply failure, ply stresses and the report.",
};

/** The results window a solved coupon opens from the workspace, by the job's link (ADR-0051; under the workspace since ADR-0062). Its heading
 * says what it holds, results, and the coupon once they are read; with no job it says so and where results come from (audit fea-screens-14). */
export default function FeaViewPage() {
  return (
    <main id="main" className="studio-page studio-view-page">
      <div className="studio-heading">
        <span className="eyebrow">WORKSPACE / RESULTS</span>
        <h1>Results</h1>
      </div>
      <Suspense fallback={<p className="studio-status">Loading…</p>}>
        <StudioViewer apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
      </Suspense>
    </main>
  );
}
