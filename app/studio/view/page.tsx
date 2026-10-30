import type { Metadata } from "next";
import { Suspense } from "react";
import { StudioViewer } from "@/components/studio/studio-viewer";
import "../studio.css";

export const metadata: Metadata = {
  title: "Viewer | Anisotropy AI",
  description: "The 3D view of one solved coupon, by its job.",
};

export default function StudioViewPage() {
  return (
    <main id="main" className="studio-page studio-view-page">
      <div className="studio-heading">
        <span className="eyebrow">STUDIO / VIEWER</span>
        <h1>One solved coupon.</h1>
      </div>
      <Suspense fallback={<p className="studio-status">Reading the job from the address…</p>}>
        <StudioViewer apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
      </Suspense>
    </main>
  );
}
