"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUp } from "lucide-react";
import { HANDOFF_KEY, putHandoff } from "@/lib/handoff";
import { COUPON_HREF } from "@/lib/workspaces";
/** The message's key in this tab's storage, which the workspace's assistants read once (ADR-0124, `lib/handoff.ts`). */
export const handoffKey = HANDOFF_KEY;
/** A coupon described on the home page opens FEA set up for a coupon, with the description carried to its assistant (ADR-0124). */
export function HomeComposer() {
  const [prompt, setPrompt] = useState("");
  const router = useRouter();
  function submit() {
    if (!prompt.trim()) return;
    let kept = false;
    try { kept = putHandoff(window.sessionStorage, { setUp: prompt, prompt }); } catch { /* storage blocked: the address carries it */ }
    router.push(kept ? COUPON_HREF : `${COUPON_HREF}&prompt=${encodeURIComponent(prompt.trim().slice(0, 2000))}`);
  }
  return (
    <div className="hero-chat-entry">
      <form
        className="home-composer"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        <textarea
          maxLength={4000}
          rows={2}
          aria-label="Describe your engineering question"
          placeholder="Describe a coupon test, e.g. open-hole tension, IM7/8552, [45/0/-45/90]s, 6 mm hole…"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <div>
          <button
            type="submit"
            disabled={!prompt.trim()}
            aria-label="Start chat"
          >
            <ArrowUp size={21} />
          </button>
        </div>
      </form>
      <p className="composer-caption">
        Set up a coupon test <span>Checked and solved by our engine</span>
      </p>
    </div>
  );
}
