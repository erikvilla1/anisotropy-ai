"use client";
import { useState } from "react";
import { ArrowUpRight, ChevronDown, Search } from "lucide-react";
import { physicsTopics } from "@/lib/physics";
export function PhysicsBrowser() {
  const [selected, setSelected] = useState("clt");
  const [query, setQuery] = useState("");
  const topic = physicsTopics.find((t) => t.id === selected)!;
  const matches = topic.methods.filter((m) =>
    `${m.name} ${m.detail} ${m.equation}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <div className="physics-catalog">
      <div className="physics-intro">
        <span className="eyebrow">THE METHOD, OPEN TO INSPECTION</span>
        <h2>Understand every step.</h2>
        <p>
          A growing function and equation catalog. Start with the ply, build the
          laminate, recover local stresses, then evaluate failure and verify the
          result. These are educational references; no numerical analysis is
          performed in this preview.
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
                <small>{t.methods.length} functions & methods</small>
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
                  <pre className="physics-equation">{m.equation}</pre>
                  <p>{m.detail}</p>
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
          {topic.id === "failure" && (
            <a
              className="topic-source"
              href="https://docs.software.vt.edu/abaqusv2024/English/SIMACAEMATRefMap/simamat-c-damageinitfibercomposite.htm"
              target="_blank"
              rel="noreferrer"
            >
              Hashin initiation conventions · technical reference
              <ArrowUpRight size={15} />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
