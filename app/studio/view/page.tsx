import type { Metadata } from "next";
import { RedirectTo } from "@/components/redirect-to";
import "../studio.css";

export const metadata: Metadata = {
  title: "Viewer | Anisotropy",
  description: "The viewer moved under the chat.",
};

/** An old viewer link keeps its job: it goes to `/chat/view` with the same query (ADR-0055 amendment 3). */
export default function StudioViewPage() {
  return (
    <main id="main" className="studio-page">
      <RedirectTo path="/chat/view" />
    </main>
  );
}
