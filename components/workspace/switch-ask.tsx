"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { TARGET_TITLES, type WorkTarget } from "@/lib/work-intent";

/** The one question before another section opens while this project holds work (ADR-0124, the founder's "Ask only if work is open"):
 * what opens, that the work here is kept, and one tap either way. Answered once; the buttons then rest. */
export function SwitchAsk({ target, kept, onGo, onStay }: {
  target: WorkTarget; kept: "coupon" | "laminate"; onGo: () => void; onStay: () => void;
}) {
  const [answered, setAnswered] = useState<"go" | "stay" | null>(null);
  const title = TARGET_TITLES[target];
  const section = target === "coupon" || target === "wing" ? `FEA for a ${title.toLowerCase()}` : title;
  return (
    <div data-testid="chat-switch" data-target={target} data-answered={answered ?? undefined}>
      <h4>Open {section}?</h4>
      <p>Your {kept} is saved under Projects, as it is now.{target === "wing" ? "" : " Your message goes with you."}</p>
      <div className="chat-chips">
        <button type="button" className="chat-primary" disabled={answered !== null} data-testid="switch-go" onClick={() => { setAnswered("go"); onGo(); }}>
          Yes, open {title} <ArrowRight size={14} />
        </button>
        <button type="button" disabled={answered !== null} data-testid="switch-stay" onClick={() => { setAnswered("stay"); onStay(); }}>Stay here</button>
      </div>
    </div>
  );
}
