"use client";

import { createContext, useContext, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** The places of the FEA workspace's layout (ADR-0134) that a stage puts its parts into: the results card's three columns (the project,
 * the legend and the view, the answer), the details opened over the model from the card, and the layer over the model (a clicked
 * element's readout). */
export type SlotName = "project" | "view" | "answer" | "details" | "over";

export type CanvasSlots = {
  /** the element of each place, once the shell has drawn it */
  places: Partial<Record<SlotName, HTMLElement | null>>;
  /** whether the details over the model are open, and the way to open or close them */
  details: boolean;
  setDetails: (open: boolean) => void;
};

const SlotsContext = createContext<CanvasSlots | null>(null);
export const CanvasSlotsProvider = SlotsContext.Provider;

/** The layout's places when the page is in the canvas shell (ADR-0134); null elsewhere, as on `/workspace/fea/view`, where a stage
 * draws its parts in one column as before. */
export function useCanvasSlots(): CanvasSlots | null {
  return useContext(SlotsContext);
}

/** Draws its children into a place of the canvas shell, or where it stands when the page has no shell. */
export function Slot({ name, children }: { name: SlotName; children: ReactNode }) {
  const slots = useContext(SlotsContext);
  if (!slots) return <>{children}</>;
  const place = slots.places[name];
  return place ? createPortal(children, place) : null;
}

/** The button that opens and closes the details over the model (ADR-0134): the full answer, its tables and the files. */
export function DetailsToggle({ open, onToggle }: { open: boolean; onToggle: (open: boolean) => void }) {
  return (
    <button type="button" className="studio-text-button cv-details-toggle" aria-expanded={open} aria-controls="ws-details" onClick={() => onToggle(!open)}
      data-testid="details-toggle">{open ? "Hide details" : "Details"}</button>
  );
}
