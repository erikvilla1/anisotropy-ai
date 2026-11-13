"use client";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ArrowUpRight, BookOpen, Database } from "lucide-react";
import { MaterialBrowser } from "@/components/material-browser";
import { PhysicsBrowser } from "@/components/physics-browser";
import { citedSources } from "@/lib/cited-sources";
import { physicsCardCount } from "@/lib/physics";
import { sourceRightsPolicy } from "@/lib/source-rights";

const TABS = [
  { id: "materials", label: "Materials", Icon: Database, title: "Material properties",
    intro: "Find a composite. Compare properties in English and SI units. Open the reference." },
  { id: "physics", label: "Physics & references", Icon: BookOpen, title: "Physics & references",
    intro: `${physicsCardCount} equations for lamina and laminate analysis, each with its assumptions, units and source.` },
] as const;
type TabId = (typeof TABS)[number]["id"];
const sourceGroups = citedSources();

// The tab and the selected material live in the address (/library?tab=physics, /library?material=im7-8552), so a link
// reopens the same view. The site is a static export: the page reads the address once it is in the browser.
function readAddress(): { tab: TabId; material: string | null } {
  const params = new URLSearchParams(window.location.search);
  return { tab: params.get("tab") === "physics" ? "physics" : "materials", material: params.get("material") };
}
function writeAddress({ tab, material }: { tab: TabId; material: string | null }) {
  const params = new URLSearchParams(window.location.search);
  if (tab === "physics") params.set("tab", "physics");
  else params.delete("tab");
  if (material) params.set("material", material);
  else params.delete("material");
  const query = params.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`);
}

export default function Library() {
  const [tab, setTab] = useState<TabId>("materials");
  const [material, setMaterial] = useState<string | null>(null);
  const tabs = useRef<Partial<Record<TabId, HTMLButtonElement | null>>>({});
  useEffect(() => {
    const sync = () => {
      const address = readAddress();
      setTab(address.tab);
      setMaterial(address.material);
    };
    sync();
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);
  function choose(next: TabId, focus = false) {
    setTab(next);
    writeAddress({ tab: next, material });
    if (focus) tabs.current[next]?.focus();
  }
  function selectMaterial(id: string) {
    setMaterial(id);
    writeAddress({ tab, material: id });
  }
  // Arrow keys, Home and End move between the tabs; only the selected tab is in the Tab order.
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const index = TABS.findIndex(t => t.id === tab);
    const next = event.key === "ArrowRight" ? (index + 1) % TABS.length
      : event.key === "ArrowLeft" ? (index - 1 + TABS.length) % TABS.length
      : event.key === "Home" ? 0 : event.key === "End" ? TABS.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault();
    choose(TABS[next].id, true);
  }
  const current = TABS.find(t => t.id === tab)!;
  return (
    <main id="main" className="inner-page">
      <section className="section library-intro">
        <h1>{current.title}</h1>
        <p>{current.intro}</p>
      </section>
      <section className="section library-section">
        <div className="library-tabs" role="tablist" aria-label="Library category" onKeyDown={onKeyDown}>
          {TABS.map(({ id, label, Icon }) => (
            <button
              key={id}
              ref={element => { tabs.current[id] = element; }}
              role="tab"
              id={`library-tab-${id}`}
              aria-controls={`library-panel-${id}`}
              aria-selected={tab === id}
              tabIndex={tab === id ? 0 : -1}
              onClick={() => choose(id)}
            >
              <Icon size={16} /> {label}
            </button>
          ))}
        </div>
        {TABS.map(({ id }) => (
          <div key={id} role="tabpanel" id={`library-panel-${id}`} aria-labelledby={`library-tab-${id}`} hidden={tab !== id}>
            {tab === id && id === "materials" && <MaterialBrowser selected={material} onSelect={selectMaterial} />}
            {tab === id && id === "physics" && <><PhysicsBrowser /><ReferencesPanel /></>}
          </div>
        ))}
      </section>
    </main>
  );
}

/** Every source the library cites, grouped by what its rights class lets the site show. Classes no source uses are not listed. */
function ReferencesPanel() {
  return (
    <div className="references-panel">
      <span className="eyebrow">SOURCE LIBRARY</span>
      <h2>Sources we cite.</h2>
      <p>Every value and equation is cited to its source. Licensed works are cited by table or figure and page, never reproduced.</p>
      {sourceGroups.map(group => (
        <section key={group.rights} className="rights-group" aria-labelledby={`rights-${group.rights}`}>
          <h3 id={`rights-${group.rights}`}><span className={`rights-chip rights-${group.rights}`}>{sourceRightsPolicy[group.rights].label}</span></h3>
          <p>{sourceRightsPolicy[group.rights].summary}</p>
          <ul className="source-list">
            {group.sources.map(source => (
              <li key={source.url}>
                {source.search
                  ? <span>{source.title}</span>
                  : <a href={source.url} target="_blank" rel="noreferrer">{source.title} <ArrowUpRight size={13} /><span className="sr-only"> (opens in a new tab)</span></a>}
                {source.detail && <small>{source.detail}</small>}
                {source.search && <a href={source.url} target="_blank" rel="noreferrer">Search {new URL(source.url).hostname.replace(/^www\./, "")} <ArrowUpRight size={13} /><span className="sr-only"> (opens in a new tab)</span></a>}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
