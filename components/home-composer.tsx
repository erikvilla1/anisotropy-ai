"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUp } from "lucide-react";
export const handoffKey = "composite-scope-handoff";
export function HomeComposer() {
  const [prompt, setPrompt] = useState("");
  const [format, setFormat] = useState("auto");
  const router = useRouter();
  function submit() {
    if (!prompt.trim()) return;
    const payload = { prompt: prompt.trim(), format };
    try {
      sessionStorage.setItem(handoffKey, JSON.stringify(payload));
      router.push("/chat");
    } catch {
      router.push(
        `/chat?prompt=${encodeURIComponent(payload.prompt)}&format=${format}`,
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
          placeholder="Describe a coupon, ask a question, or define your scope…"
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
          <label>
            Response{" "}
            <select
              aria-label="Response format"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
            >
              <option value="auto">Automatic</option>
              <option value="brief">Engineering brief</option>
              <option value="table">Comparison table</option>
              <option value="checklist">Test checklist</option>
              <option value="json">Structured JSON</option>
              <option value="deliverables">Analysis package</option>
              <option value="report">LaTeX report outline</option>
            </select>
          </label>
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
        Begin your engineering scope <span>Interactive product preview</span>
      </p>
    </div>
  );
}
