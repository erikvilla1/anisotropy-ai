"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUp } from "lucide-react";
export const handoffKey = "composite-scope-handoff";
export function HomeComposer() {
  const [prompt, setPrompt] = useState("");
  const router = useRouter();
  function submit() {
    if (!prompt.trim()) return;
    const payload = { prompt: prompt.trim() };
    try {
      sessionStorage.setItem(handoffKey, JSON.stringify(payload));
      router.push("/chat");
    } catch {
      router.push(
        `/chat?prompt=${encodeURIComponent(payload.prompt)}`,
      );
    }
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
