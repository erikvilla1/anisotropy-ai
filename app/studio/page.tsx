import type { Metadata } from "next";
import { StudioModes } from "@/components/studio/studio-modes";
import "./studio.css";

export const metadata: Metadata = {
  title: "Coupon studio | Anisotropy AI",
  description: "State a coupon test, check its setup, solve it with the Anisotropy engine and read the result in 3D.",
};

export default function StudioPage() {
  return (
    <main id="main" className="studio-page">
      <div className="studio-heading">
        <span className="eyebrow">STUDIO / COUPON TESTS</span>
        <h1>From the coupon to its stresses.</h1>
        <p>Describe the coupon or answer a few questions. The setup is checked against the run&apos;s rules, solved by our engine and CalculiX, and every ply is drawn in 3D. The engine computes every number; the page draws it.</p>
      </div>
      <StudioModes apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
