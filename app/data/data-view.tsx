"use client";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { DataWorkspace } from "@/components/data-workspace";

export function DataView() {
  return (
    <main id="main" className="inner-page chat-page">
      <div className="section studio-heading">
        <div>
          <span className="eyebrow">TEST DATA</span>
          <h1>Bring the evidence together.</h1>
          <p>
            Check a CSV of coupon results in your browser, or try the example.
          </p>
        </div>
        <Link className="text-button" href="/workspace/fea">
          Open Workspace <ArrowRight size={15} />
        </Link>
      </div>
      <DataWorkspace />
    </main>
  );
}
