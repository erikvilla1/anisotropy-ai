"use client";
import { useState } from "react";
import { ArrowUpRight, ChevronDown, Search } from "lucide-react";
import { physicsTopics, deferredPhysicsTopics } from "@/lib/physics";
import { checkedExamples, bookReference } from "@/lib/physics-foundations";
import { MathFormula } from "./math-formula";
export function PhysicsBrowser() {
  const [selected, setSelected] = useState("clt");
  const [query, setQuery] = useState("");
  const topic = physicsTopics.find((t) => t.id === selected)!;
  const matches = topic.methods.filter((m) =>
    `${m.name} ${m.detail} ${m.equation} ${m.reference?.location}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <div className="physics-catalog">
      <div className="physics-intro">
        <span className="eyebrow">COMPOSITE MECHANICS</span>
        <h2>Equations with a reference.</h2>
        <p>
          Look up the equation, its units and when it applies. These {physicsTopics.reduce((n, t) => n + t.methods.length, 0)} reference cards cover
          lamina and laminate fundamentals. They do not calculate a component analysis.
        </p>
      </div>
      <div className="physics-browser">
        <nav className="topic-list" aria-label="Physics topics">
          {physicsTopics.map((t, i) => (
            <button
              key={t.id}
              aria-pressed={t.id === selected}
              onClick={() => {
                setSelected(t.id);
                setQuery("");
              }}
            >
              <span>0{i + 1}</span>
              <strong>
                {t.title}
                <small>{t.methods.length} equations &amp; methods</small>
              </strong>
            </button>
          ))}
        </nav>
        <div className="topic-content">
          <span className="tiny-label">{topic.subtitle}</span>
          <h3>{topic.title}</h3>
          <div className="topic-assumptions">
            <strong>Assumptions & conventions</strong>
            <p>{topic.assumptions}</p>
          </div>
          <label className="library-search function-search">
            <Search size={16} />
            <input
              aria-label="Search this physics topic"
              placeholder="Find a function or equation…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <div className="method-list" key={topic.id}>
            {matches.map((m, i) => (
              <details
                key={m.name}
                className="method-entry"
                open={query ? true : undefined}
              >
                <summary>
                  <span>{String(i + 1).padStart(2, "0")}</span>
                  <strong>{m.name}</strong>
                  <ChevronDown size={17} />
                </summary>
                <div>
                  <MathFormula name={m.name} />
                  <p>{m.detail}</p>
                  <p className="equation-units"><strong>Units</strong> · {m.units}</p>
                  {m.reference && <p className="equation-reference"><a href={m.reference.url} target="_blank" rel="noreferrer">{m.reference.title} <ArrowUpRight size={13} /></a><br />{m.reference.location}</p>}
                </div>
              </details>
            ))}
          </div>
          {!matches.length && (
            <p className="empty-library">
              No functions match within this topic.
            </p>
          )}
          <a
            className="topic-source"
            href={topic.url}
            target="_blank"
            rel="noreferrer"
          >
            {topic.source}
            <ArrowUpRight size={15} />
          </a>
        </div>
      </div>
      <details className="physics-review-panel">
        <summary>Worked examples &amp; equation checks</summary>
        <p>Three textbook examples have been reproduced, alongside checks of axis rotation, stiffness symmetry and units. These verify selected formulas; they do not validate a CAD or FEA solver.</p>
        {checkedExamples.map(example => <section key={example.name}><h4>{example.name}</h4><p>{example.inputs}</p><p>{example.result}</p><a href={bookReference.url} target="_blank" rel="noreferrer">{example.reference} <ArrowUpRight size={13} /></a></section>)}
      </details>
      <details className="physics-review-panel">
        <summary>Later research: CAD, FEA &amp; advanced models</summary>
        <ul>{deferredPhysicsTopics.map(topic => <li key={topic.title}><strong>{topic.title}</strong><p>{topic.detail}</p></li>)}</ul>
      </details>
    </div>
  );
}
