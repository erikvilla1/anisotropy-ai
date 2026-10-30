"use client";

import { useRef, useState } from "react";
import { MessagesSquare, TableProperties } from "lucide-react";
import type { StudioForm } from "@/lib/studio-form";
import { CouponChat } from "./coupon-chat";
import { CouponStudio } from "./coupon-studio";

/** The studio's two ways in (ADR-0055): the guided chat by default, the full form one click away; the rows typed in one carry to the other. */
export function StudioModes({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [mode, setMode] = useState<"chat" | "form">("chat");
  const latest = useRef<StudioForm | null>(null);
  const keep = (form: StudioForm) => { latest.current = form; };
  return (
    <>
      <div className="studio-modes" role="tablist" aria-label="How to set up the coupon">
        <button type="button" role="tab" aria-selected={mode === "chat"} className={mode === "chat" ? "active" : ""} onClick={() => setMode("chat")}>
          <MessagesSquare size={15} /> Guided
        </button>
        <button type="button" role="tab" aria-selected={mode === "form"} className={mode === "form" ? "active" : ""} onClick={() => setMode("form")}>
          <TableProperties size={15} /> Full form
        </button>
      </div>
      {mode === "chat"
        ? <CouponChat apiBaseUrl={apiBaseUrl} initialForm={latest.current} onFormChange={keep} onOpenForm={() => setMode("form")} />
        : <CouponStudio apiBaseUrl={apiBaseUrl} initialForm={latest.current} onFormChange={keep} />}
    </>
  );
}
