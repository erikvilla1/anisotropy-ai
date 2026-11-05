"use client";

import { useRef, useState } from "react";
import { MessagesSquare, TableProperties } from "lucide-react";
import type { StudioForm } from "@/lib/studio-form";
import { CouponChat } from "./coupon-chat";
import { CouponStudio } from "./coupon-studio";
import { LaminateChat } from "./laminate-chat";

/** The studio's two ways in (ADR-0055): the guided chat by default, the full form one click away; the rows typed in one carry to the
 * other. The chat's first choice opens the laminate assistant (ADR-0060), which shares the Guided tab. */
export function StudioModes({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [mode, setMode] = useState<"chat" | "laminate" | "form">("chat");
  const latest = useRef<StudioForm | null>(null);
  const keep = (form: StudioForm) => { latest.current = form; };
  return (
    <>
      <div className="studio-modes" role="tablist" aria-label="How to set up the coupon">
        <button type="button" role="tab" aria-selected={mode !== "form"} className={mode !== "form" ? "active" : ""} onClick={() => setMode("chat")}>
          <MessagesSquare size={15} /> Guided
        </button>
        <button type="button" role="tab" aria-selected={mode === "form"} className={mode === "form" ? "active" : ""} onClick={() => setMode("form")}>
          <TableProperties size={15} /> Full form
        </button>
      </div>
      {mode === "chat"
        ? <CouponChat apiBaseUrl={apiBaseUrl} initialForm={latest.current} onFormChange={keep} onOpenForm={() => setMode("form")} onLaminate={() => setMode("laminate")} />
        : mode === "laminate" ? <LaminateChat apiBaseUrl={apiBaseUrl} onBack={() => setMode("chat")} />
        : <CouponStudio apiBaseUrl={apiBaseUrl} initialForm={latest.current} onFormChange={keep} />}
    </>
  );
}
