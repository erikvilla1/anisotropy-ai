import type { Metadata } from "next";
import { RedirectTo } from "@/components/redirect-to";
import "../studio.css";

// The page it goes to, by its own title and description (app/workspace/fea/view/page.tsx).
export const metadata: Metadata = {
  title: "Viewer",
  description: "3D results of one solved coupon.",
};

/** An old viewer link keeps its job: it goes to `/workspace/fea/view` with the same query (ADR-0062); on the hosted site the Worker
 * sends it there first (ADR-0058 amendment 2). */
export default function StudioViewPage() {
  return (
    <main id="main" className="studio-page">
      <RedirectTo path="/workspace/fea/view" label="the viewer" />
    </main>
  );
}
