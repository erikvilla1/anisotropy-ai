"use client";
import { useState } from "react";
import { ArrowUpRight, ChevronDown, Search } from "lucide-react";
import { physicsTopics } from "@/lib/physics";
import { MathFormula } from "./math-formula";

const count = (n: number) => `${n} ${n === 1 ? "equation" : "equations"}`;

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
              <span>{String(i + 1).padStart(2, "0")}</span>
              <strong>
                {t.title}
                <small>{count(t.methods.length)}</small>
              </strong>
            </button>
          ))}
        </nav>
        <div className="topic-content">
          <span className="tiny-label">{topic.subtitle}</span>
          <h2>{topic.title}</h2>
          <div className="topic-assumptions">
            <strong>Assumptions & conventions</strong>
            <p>{topic.assumptions}</p>
          </div>
          <label className="library-search function-search">
            <Search size={16} />
            <input
              aria-label="Search this physics topic"
              placeholder="Search equations"
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
                  {m.reference && <p className="equation-reference"><a href={m.reference.url} target="_blank" rel="noreferrer">{m.reference.title} <ArrowUpRight size={13} /><span className="sr-only"> (opens in a new tab)</span></a><br />{m.reference.location}</p>}
                </div>
              </details>
            ))}
          </div>
          <div role="status">
            {!matches.length && <p className="empty-library">No equations match. Clear the search or choose another topic.</p>}
          </div>
          <a
            className="topic-source"
            href={topic.url}
            target="_blank"
            rel="noreferrer"
          >
            {topic.source}
            <ArrowUpRight size={15} />
            <span className="sr-only"> (opens in a new tab)</span>
          </a>
        </div>
      </div>
    </div>
  );
}
