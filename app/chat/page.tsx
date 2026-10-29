import type { Metadata } from "next";
import { StudioModes } from "@/components/studio/studio-modes";
import "../studio/studio.css";

export const metadata: Metadata = {
  title: "Chat | Anisotropy AI",
  description: "Describe a composite coupon test in plain words; the assistant checks the setup, solves it with the Anisotropy engine and CalculiX, and shows every ply.",
};

/** The site's chat is the coupon assistant (ADR-0055 amendment 1): the studio's guided chat, full screen. */
export default function ChatPage() {
  return (
    <main id="main" className="studio-page chat-app-page">
      <h1 className="chat-page-title">Anisotropy AI chat</h1>
      <StudioModes apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
