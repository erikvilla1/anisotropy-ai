import type { Metadata } from "next";
import { RedirectTo } from "@/components/redirect-to";
import "./studio.css";

export const metadata: Metadata = {
  title: "Chat | Anisotropy",
  description: "The coupon studio is part of the chat now.",
};

/** The studio's address still works: it goes to the chat, the one place to work out anything (ADR-0055 amendment 3). */
export default function StudioPage() {
  return (
    <main id="main" className="studio-page">
      <RedirectTo path="/chat" />
    </main>
  );
}
