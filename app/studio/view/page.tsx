import type { Metadata } from "next";
import { RedirectTo } from "@/components/redirect-to";
import "../studio.css";

// The page it goes to, by its own title and description (app/workspace/fea/view/page.tsx).
export const metadata: Metadata = {
  title: "Results",
  description: "Results of a coupon analysis: the model, first-ply failure, ply stresses and the report.",
};

/** An old viewer link keeps its job: it goes to `/workspace/fea/view` with the same query (ADR-0062); on the hosted site the Worker
 * sends it there first (ADR-0058 amendment 2). */
export default function StudioViewPage() {
  return (
    <main id="main" className="studio-page">
      <RedirectTo path="/workspace/fea/view" label="the results" />
    </main>
  );
}
