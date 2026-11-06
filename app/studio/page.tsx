import type { Metadata } from "next";
import { RedirectTo } from "@/components/redirect-to";
import "./studio.css";

export const metadata: Metadata = {
  title: "Chat | Anisotropy",
  description: "The coupon studio is the coupon FEA workspace now.",
};

/** The studio's address still works: it goes to the coupon FEA workspace (ADR-0062). */
export default function StudioPage() {
  return (
    <main id="main" className="studio-page">
      <RedirectTo path="/workspace/fea" />
    </main>
  );
}
