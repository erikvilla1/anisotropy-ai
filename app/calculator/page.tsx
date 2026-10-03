import type { Metadata } from "next";
import { LaminateCalculator } from "@/components/laminate-calculator";
import "./calculator.css";

export const metadata: Metadata = {
  title: "Laminate calculator | Anisotropy AI",
  description: "Calculate laminate stiffness, mid-plane strains and curvatures with the Anisotropy engine.",
};

export default function CalculatorPage() {
  return (
    <main id="main" className="calculator-page">
      <div className="calculator-heading">
        <span className="eyebrow">ANALYSIS / CLASSICAL LAMINATE THEORY</span>
        <h1>From layup to response.</h1>
        <p>Define your laminate and loads. Inspect its stiffness, strain and curvature.</p>
      </div>
      <LaminateCalculator apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
