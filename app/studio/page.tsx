import type { Metadata } from "next";
import { CouponStudio } from "@/components/studio/coupon-studio";
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
        <p>State the coupon, check the setup, solve, and read every ply. The engine computes every number; the page draws it.</p>
      </div>
      <CouponStudio apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
