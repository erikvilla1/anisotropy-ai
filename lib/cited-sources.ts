// Every source the library cites, once, grouped by rights class: the source of each material dataset and the references the
// physics cards cite. The references panel lists these, so it cannot name fewer sources than the pages use (ADR-0018).
import { curatedMaterials, materialDatasets } from "./curated-materials";
import { physicsReferences } from "./physics-foundations";
import { sourceRightsClasses, type SourceRights } from "./source-rights";
import { textbookSource } from "./textbook-source";

export type CitedSource = { title: string; detail: string; url: string; search: boolean; rights: SourceRights };

export function citedSources(): { rights: SourceRights; sources: CitedSource[] }[] {
  const byUrl = new Map<string, CitedSource>();
  for (const { source } of curatedMaterials.flatMap(materialDatasets)) {
    if (byUrl.has(source.url)) continue;
    const year = source.date?.slice(0, 4);
    // The textbook reads as it does on its cards, in its full citation form.
    byUrl.set(source.url, source.id === textbookSource.id
      ? { title: textbookSource.fullCitation, detail: "", url: source.url, search: false, rights: source.rights }
      : { title: source.title, url: source.url, search: source.linkKind === "search", rights: source.rights,
        detail: [source.authors, source.publisher, year].filter(Boolean).join(" · ") });
  }
  for (const ref of physicsReferences) {
    if (byUrl.has(ref.url)) continue;
    const [title, ...rest] = ref.title.split(" · ");
    const listed = ref.listed ?? { title, detail: rest.join(" · ") };
    byUrl.set(ref.url, { ...listed, url: ref.url, search: false, rights: ref.rights });
  }
  const sources = [...byUrl.values()].sort((a, b) => a.title.localeCompare(b.title));
  return sourceRightsClasses
    .map(rights => ({ rights, sources: sources.filter(s => s.rights === rights) }))
    .filter(group => group.sources.length > 0);
}
