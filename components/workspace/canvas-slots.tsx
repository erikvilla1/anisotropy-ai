"use client";

import { createContext, useContext, useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** The places of the FEA workspace's layout (ADR-0134) that a stage puts its parts into: the results card's three columns (the project,
 * the legend and the view, the answer), the details opened over the model from the card, the layer over the model (a clicked
 * element's readout), and the View menu's part for how the model is looked at and what is drawn on it (`look`, ADR-0134 amendment 1),
 * which the View menu itself provides. */
export type SlotName = "project" | "view" | "answer" | "details" | "over" | "look";

/** The part of the window the model is framed in: its distance in pixels from each edge of the model's area, clear of the rail, the
 * tree, the card and the chat that float over it (ADR-0134 amendment 1). */
export type FreeArea = { left: number; right: number; top: number; bottom: number };

export type CanvasSlots = {
  /** the element of each place, once the shell has drawn it */
  places: Partial<Record<SlotName, HTMLElement | null>>;
  /** the ref of a place drawn by a part of the page itself rather than the shell: the View menu's `look` */
  register: (name: SlotName) => (element: HTMLElement | null) => void;
  /** whether the details over the model are open, and the way to open or close them */
  details: boolean;
  setDetails: (open: boolean) => void;
  /** where the model is framed; null until the shell has measured the window */
  free: FreeArea | null;
};

const SlotsContext = createContext<CanvasSlots | null>(null);
export const CanvasSlotsProvider = SlotsContext.Provider;

/** The layout's places when the page is in the canvas shell (ADR-0134); null elsewhere, as on `/workspace/fea/view`, where a stage
 * draws its parts in one column as before. */
export function useCanvasSlots(): CanvasSlots | null {
  return useContext(SlotsContext);
}

/** Draws its children into a place of the canvas shell, or where it stands when the page has no shell. `here` draws them where they
 * stand also while the shell has no such place, as before a View menu is on the page. */
export function Slot({ name, here = false, children }: { name: SlotName; here?: boolean; children: ReactNode }) {
  const slots = useContext(SlotsContext);
  if (!slots) return <>{children}</>;
  const place = slots.places[name];
  return place ? createPortal(children, place) : here ? <>{children}</> : null;
}

/** The button that opens and closes the details over the model (ADR-0134): the full answer, its tables and the files. */
export function DetailsToggle({ open, onToggle }: { open: boolean; onToggle: (open: boolean) => void }) {
  return (
    <button type="button" className="studio-text-button cv-details-toggle" aria-expanded={open} aria-controls="ws-details" onClick={() => onToggle(!open)}
      data-testid="details-toggle">{open ? "Hide details" : "Details"}</button>
  );
}

/** The card's View menu (ADR-0134 amendment 1): one row under the legend, "View" and what is shown, that opens upward over the model. It
 * holds what the stage puts in it and, last, the scene's own part (`look`): how the model is looked at, what is drawn on it, the supports
 * and loads applied. A press anywhere else or Esc puts it away, before Esc closes anything else. */
export function ViewMenu({ summary, children }: { summary: ReactNode; children?: ReactNode }) {
  const slots = useContext(SlotsContext);
  const menu = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const away = (event: PointerEvent) => { const m = menu.current; if (m?.open && !m.contains(event.target as Node)) m.open = false; };
    const key = (event: KeyboardEvent) => {
      const m = menu.current;
      if (event.key === "Escape" && m?.open) { m.open = false; event.preventDefault(); m.querySelector("summary")?.focus(); }
    };
    document.addEventListener("pointerdown", away); document.addEventListener("keydown", key);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", key); };
  }, []);
  return (
    <details className="cv-view-menu" data-testid="view-menu" ref={menu}>
      <summary><span className="cv-view-k">View</span><span className="cv-view-v">{summary}</span></summary>
      <div className="cv-view-menu-body">
        {children}
        <div className="cv-look" ref={slots ? slots.register("look") : undefined} />
      </div>
    </details>
  );
}
