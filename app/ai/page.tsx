import type { Metadata } from "next";
import { AiActivity } from "@/components/oversight/ai-activity";
import "./ai.css";

export const metadata: Metadata = {
  title: "AI activity",
  description: "What the AI does, as it happens: every call to the model, every plan and approval, and the weeks.",
  robots: { index: false, follow: false },
};

/** The founders' AI activity page (ADR-0145). The page itself is plain; what it shows comes from the API, which answers a founder's
 * sign-in alone and anyone else 404. */
export default function AiActivityPage() {
  return (
    <main id="main" className="ai-page">
      <AiActivity apiBaseUrl={process.env.NEXT_PUBLIC_ANISOTROPY_API_URL?.trim() || ""} />
    </main>
  );
}
