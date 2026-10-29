"use client";
import Link from "next/link";
import { Workspace } from "@/components/workspace";
export default function DataPage() {
  return (
    <main id="main" className="inner-page chat-page">
      <div className="section studio-heading">
        <div>
          <span className="eyebrow">RESEARCH / TEST-DATA PREVIEW</span>
          <h1>Bring the evidence together.</h1>
          <p>
            Inspect a sample submission, or check a CSV locally in your browser.
          </p>
        </div>
        <Link className="text-button" href="/chat">
          Open the coupon assistant →
        </Link>
      </div>
      <Workspace activeTab="data" setActiveTab={() => {}} standalone />
    </main>
  );
}
