import { retrieveDocument, type Document } from "./documents";
import { MonitorStore } from "./store";
import type { Source } from "./sources";

export async function runChecks(store: MonitorStore, force = false, retrieve: (source: Source) => Promise<Document> = retrieveDocument) {
  const lease = store.acquire();
  if (!lease) throw new Error("Another monitor is checking sources; try again later");
  const outcomes: { source: string; outcome: string }[] = [];
  try {
    for (const source of store.sources) {
      if (!force && store.state(source.id).next_check > new Date().toISOString()) continue;
      try {
        const document = await retrieve(source);
        outcomes.push({ source: source.id, outcome: store.recordSuccess(source, document) });
      } catch (error) {
        store.recordFailure(source, error instanceof Error ? error.message : "Source check failed");
        outcomes.push({ source: source.id, outcome: "failed" });
      }
    }
  } finally { store.release(lease); }
  return outcomes;
}
