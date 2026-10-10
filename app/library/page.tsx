"use client";
import { MaterialBrowser } from "@/components/material-browser";
import { PhysicsBrowser } from "@/components/physics-browser";
import { useState } from "react";
import { ArrowUpRight, BookOpen, Database } from "lucide-react";
import { handbookReferences, sourceRightsClasses, sourceRightsPolicy } from "@/lib/source-rights";

export default function Library() {
  const [tab, setTab] = useState("Materials");
  return (
    <main id="main" className="inner-page">
      <section className="section library-intro">
        <h1>{tab === "Materials" ? "Material properties" : "Physics & references"}</h1>
        <p>{tab === "Materials" ? "Find a composite. Compare properties in English and SI units. Open the reference." : "Find an equation. Check its assumptions, units and source."}</p>
      </section>
      <section className="section library-section">
        <div
          className="library-tabs"
          role="tablist"
          aria-label="Library category"
        >
          {["Materials", "Physics & references"].map(
            (t) => (
              <button
                key={t}
                role="tab"
                id={`library-tab-${t.split(" ")[0]}`}
                aria-controls="library-content"
                aria-selected={tab === t}
                onClick={() => setTab(t)}
              >
                {t === "Materials" ? (
                  <Database size={16} />
                ) : (
                  <BookOpen size={16} />
                )}{" "}
                {t}
              </button>
            ),
          )}
        </div>
        <div
          role="tabpanel"
          id="library-content"
          aria-labelledby={`library-tab-${tab.split(" ")[0]}`}
        >
          {tab === "Materials" && <MaterialBrowser />}
          {tab === "Physics & references" && (
            <>
              <PhysicsBrowser />
              <div className="references-panel">
                <span className="eyebrow">SOURCE LIBRARY</span>
                <h3>Composite mechanics references.</h3>
                <p>
                  Daniel and Ishai supplies the equation references above. Every source in this
                  library carries a rights class that decides what the website may show. We never
                  host copies of copyrighted books or handbooks; values are cited by table and page
                  and readers consult their own copy. Handbook-specific methods receive
                  section-level review before inclusion.
                </p>
                <ul className="rights-list" aria-label="Source rights classes">
                  {sourceRightsClasses.map(rights => (
                    <li key={rights}>
                      <span className={`rights-chip rights-${rights}`}>{sourceRightsPolicy[rights].label}</span>
                      <span>{sourceRightsPolicy[rights].summary}</span>
                    </li>
                  ))}
                </ul>
                {handbookReferences.map(ref => (
                  <a key={ref.id} href={ref.url} target="_blank" rel="noreferrer">
                    <span>
                      {ref.title} · <span className={`rights-chip rights-${ref.rights}`}>{sourceRightsPolicy[ref.rights].label}</span>
                    </span>
                    <ArrowUpRight size={15} />
                  </a>
                ))}
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
