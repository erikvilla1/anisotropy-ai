import { Suspense } from "react";
import type { Metadata } from "next";
import { SourceViewer } from "@/components/source-viewer";
import "./sources.css";

export const metadata: Metadata = {
  title: "Source reference | Anisotropy AI",
  description: "Review a material property's textbook citation, recorded source units and displayed conversions.",
};

export default function Sources() {
  return <main id="main" className="inner-page source-page">
    <Suspense fallback={<section className="section"><p role="status">Opening source reference…</p></section>}>
      <SourceViewer />
    </Suspense>
  </main>;
}
