import type { Metadata } from "next";
import { RedirectTo } from "@/components/redirect-to";
import "../studio/studio.css";

export const metadata: Metadata = {
  title: "Chat | Anisotropy",
  description: "The chat is the assistant column of the coupon FEA workspace now.",
};

/** The chat's address still works: it goes to the coupon FEA workspace with the same query, where the assistant sits beside the model
 * (ADR-0062; ADR-0055 amendment 3 superseded in part). */
export default function ChatPage() {
  return (
    <main id="main" className="studio-page">
      <RedirectTo path="/workspace/fea" />
    </main>
  );
}
