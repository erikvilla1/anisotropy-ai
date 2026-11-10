"use client";

import { createContext, useContext, useState, useSyncExternalStore, type ReactNode } from "react";
import type { AnalysisResult } from "@/lib/laminate-api";

/** What is known about one request to the engine, keyed by the request's JSON: asked and not yet answered, answered, failed,
 * or given up before an answer (the calculator moved on to another stack). */
export type EngineEntry =
  | { state: "pending" }
  | { state: "answer"; result: AnalysisResult }
  | { state: "failed"; message: string }
  | { state: "dropped" };

export type EngineAnswers = {
  read(requestJson: string): EngineEntry | undefined;
  report(requestJson: string, entry: EngineEntry): void;
  subscribe(listener: () => void): () => void;
};

/** The engine's answers on the home page, shared between the calculator and the tour above it, so the tour shows the answer
 * the calculator already asked for instead of asking again (ADR-0001: every number is the engine's; one request per stack).
 * It holds answers and nothing else: no number is computed, changed or made up here. */
function createEngineAnswers(): EngineAnswers {
  const entries = new Map<string, EngineEntry>();
  const listeners = new Set<() => void>();
  return {
    read: (requestJson) => entries.get(requestJson),
    report(requestJson, entry) {
      // An answer stays until a newer answer replaces it: asking the same stack again, or failing to, takes nothing away.
      if (entry.state !== "answer" && entries.get(requestJson)?.state === "answer") return;
      entries.set(requestJson, entry);
      listeners.forEach((listener) => listener());
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
  };
}

const EngineAnswersContext = createContext<EngineAnswers | null>(null);

/** Wraps the tour and the calculator; it renders no element of its own. */
export function EngineAnswersProvider({ children }: { children: ReactNode }) {
  const [answers] = useState(createEngineAnswers);
  return <EngineAnswersContext.Provider value={answers}>{children}</EngineAnswersContext.Provider>;
}

/** The shared answers, or null where no provider wraps the caller: the calculator then works alone, as before. */
export function useEngineAnswers(): EngineAnswers | null {
  return useContext(EngineAnswersContext);
}

const noSubscription = () => () => {};

/** What the page knows about one request; the component renders again when that changes. */
export function useEngineEntry(requestJson: string | null): EngineEntry | undefined {
  const answers = useContext(EngineAnswersContext);
  const read = () => (answers && requestJson ? answers.read(requestJson) : undefined);
  return useSyncExternalStore(answers ? answers.subscribe : noSubscription, read, () => undefined);
}
