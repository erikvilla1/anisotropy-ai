"use client";
import { MaterialBrowser } from "@/components/material-browser";
import { PhysicsBrowser } from "@/components/physics-browser";
import { useState } from "react";
import { ArrowUpRight, BookOpen, Database } from "lucide-react";

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
                  Daniel and Ishai supplies the equation references above. The supplied
                  handbook volumes support material data and design context: Volume 2
                  is MIL-HDBK-17-2F (2002); Volume 3 is CMH-17-3G (2012).
                  Handbook-specific methods will receive section-level review before inclusion.
                </p>
                <a
                  href="https://global.oup.com/academic/product/engineering-mechanics-of-composite-materials-9780195150971"
                  target="_blank"
                  rel="noreferrer"
                >
                  Daniel &amp; Ishai · Engineering Mechanics of Composite Materials,
                  second edition (2006) · Publisher &amp; book <ArrowUpRight size={15} />
                </a>
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
