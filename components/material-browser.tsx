"use client";
import { useState } from "react";
import { Layers3, Search } from "lucide-react";
import { curatedMaterials as materials, currentMaterial } from "@/lib/curated-materials";
import { useMaterialFeed } from "./material-provenance";
import { CitedMaterialProperties } from "./cited-material-properties";

export function MaterialBrowser() {
  const { feed, stale } = useMaterialFeed();
  const [search, setSearch] = useState("");
  const [family, setFamily] = useState("All families");
  const [selected, setSelected] = useState(materials[0].id);
  const filtered = materials.filter(
    (m) =>
      (family === "All families" || m.family === family) &&
      `${m.id} ${m.name} ${m.family} ${m.architecture} ${m.conditions} ${m.family.startsWith("Carbon") ? "carbon fiber" : ""}`
        .toLowerCase()
        .includes(search.trim().toLowerCase()),
  );
  const chosen = filtered.find((m) => m.id === selected) || filtered[0];
  const current = chosen ? currentMaterial(chosen, feed) : undefined;
  return (
    <>
      <div className="library-filters">
        <label className="library-search">
          <Search size={17} />
          <input
            aria-label="Search materials"
            placeholder="Search a material, process, or architecture…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <select
          aria-label="Filter material family"
          value={family}
          onChange={(e) => setFamily(e.target.value)}
        >
          {[
            "All families", ...new Set(materials.map(m => m.family)),
          ].map((f) => (
            <option key={f}>{f}</option>
          ))}
        </select>
        <span aria-live="polite">{filtered.length} materials</span>
      </div>
      {current ? (
        <div className="material-browser source-materials">
          <div className="material-list" aria-label="Material records">
            {filtered.map((m) => (
              <button
                key={m.id}
                aria-pressed={current.id === m.id}
                onClick={() => setSelected(m.id)}
              >
                <Layers3 size={18} />
                <span>
                  <strong>{m.name}</strong>
                  <small>
                    {m.architecture}
                  </small>
                </span>
              </button>
            ))}
          </div>
          <article className="material-detail" aria-label="Selected material">
            <div className="material-detail-title">
              <div>
                <span className="eyebrow">
                  {current.family}
                </span>
                <h2>{current.name}</h2>
              </div>
              <Layers3 size={32} strokeWidth={1} />
            </div>
            <p className="material-subtitle">{current.architecture}</p>
            <CitedMaterialProperties key={current.id} material={current} feed={feed} stale={stale} />
          </article>
        </div>
      ) : (
        <div className="empty-library">
          <Search size={29} />
          <h3>No material records match.</h3>
          <p>Try a material name, manufacturing process, or another family.</p>
          <button
            className="button small"
            onClick={() => {
              setSearch("");
              setFamily("All families");
            }}
          >
            Reset filters
          </button>
        </div>
      )}
    </>
  );
}
