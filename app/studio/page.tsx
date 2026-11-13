import type { Metadata } from "next";
import { RedirectTo } from "@/components/redirect-to";
import "./studio.css";

// The page it goes to, by its own title and description (app/workspace/fea/page.tsx).
export const metadata: Metadata = {
  title: "Coupon FEA",
  description: "Set up a composite coupon test, run the analysis and review every ply's results.",
};

/** The studio's address still works: it goes to the coupon FEA workspace (ADR-0062); on the hosted site the Worker sends it there
 * first (ADR-0058 amendment 2). */
export default function StudioPage() {
  return (
    <main id="main" className="studio-page">
      <RedirectTo path="/workspace/fea" label="Coupon FEA" />
    </main>
  );
}
