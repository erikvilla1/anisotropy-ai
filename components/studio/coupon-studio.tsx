"use client";

import { useCallback, useState } from "react";
import type { Preview } from "@/lib/studio-api";
import { PLATE_TEST } from "@/lib/studio-form";
import { regionOptions, regionsOfElement, withLoad, withSupport, type PlateLists } from "@/lib/studio-plate";
import { sketchOf } from "@/lib/studio-sketch";
import { printed } from "@/lib/studio-colors";
import { JobProgress } from "./job-progress";
import { useProject } from "./project-context";
import { ResultsView } from "./results-view";
import { Scene } from "./scene";
import type { SceneMarker } from "./scene-canvas";
import { SketchScene } from "./sketch";

/** The nodes a load acts on: a node set, or the corner nodes of an element set (a pressure on an area region). */
function nodesOf(preview: Preview, set: string): number[] {
  if (preview.mesh.node_sets[set]) return preview.mesh.node_sets[set];
  const elements = preview.mesh.element_sets[set];
  if (!elements) return [];
  return [...new Set(elements.flatMap((e) => preview.mesh.quads[e] ?? []))];
}

/** The package's preview: the mesh with what is held and loaded, before a run. */
export function PreviewScene({ preview, onPick, picked }: { preview: Preview; onPick?: (element: number | null) => void; picked?: number | null }) {
  const held: SceneMarker[] = preview.held.map((h) => ({ nodes: preview.mesh.node_sets[h.set] ?? [], label: `${h.set}: held ${h.directions.join(", ")}` }));
  const loaded = preview.loaded ? { nodes: nodesOf(preview, preview.loaded.set), direction: preview.loaded.direction,
    label: `${preview.loaded.set}: ${preview.loaded.control} ${printed(preview.loaded.value)} ${preview.loaded.unit} along ${preview.loaded.direction}` } : null;
  const loads = (preview.loads ?? []).map((l) => ({ nodes: nodesOf(preview, l.set), direction: l.direction, label: `${l.set}: ${l.control} ${printed(l.value)} ${l.unit} along ${l.direction}` }));
  return (
    <div className="studio-panel" data-testid="preview">
      <h3>The model <span className="studio-badge">{preview.mesh.element_count} elements, {preview.mesh.node_count} nodes</span></h3>
      <Scene nodes={preview.mesh.nodes} quads={preview.mesh.quads} thickness={preview.geometry.thickness} held={held} loaded={loaded} loads={loads} onPick={onPick} picked={picked ?? null} />
      {onPick ? <p className="studio-muted">Click an element to hold or load the regions it belongs to.</p> : null}
    </div>
  );
}

/** The centre of the coupon FEA workspace (ADR-0062): the sketch of the typed rows until the setup is checked, the package's preview after
 * it, the fields after a run; a plate's regions are picked here by clicking an element (ADR-0054). Every number comes from the fea package
 * through the API (ADR-0051); the sketch draws typed rows only. */
export function CouponStudio({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { form, plate, setPlate, run: runner } = useProject();
  const { checked, job, fields, explanation } = runner;
  const [pickedElement, setPickedElement] = useState<number | null>(null);
  const { clearChecked } = runner;
  const editPlate = useCallback((lists: PlateLists) => { setPlate(lists); clearChecked(); }, [setPlate, clearChecked]);
  const isPlate = form.test === PLATE_TEST;
  const viewerLink = job ? `/workspace/fea/view?job=${encodeURIComponent(job.job_id)}` : null;
  const sketch = !fields && !checked?.preview ? sketchOf(form, isPlate ? plate : null) : null;
  return (
    <section className="studio-output">
      {fields ? (
        <>
          {viewerLink ? <p className="studio-viewer-link"><a href={viewerLink} target="_blank" rel="noreferrer" data-testid="viewer-link">Open the viewer in a new window</a></p> : null}
          <ResultsView fields={fields} explanation={explanation} job={job} apiBase={apiBaseUrl} preview={checked?.preview ?? null} />
          {job ? <JobProgress job={job} /> : null}
        </>
      ) : (
        <>
          {checked?.preview ? (
            <>
              <PreviewScene preview={checked.preview} onPick={isPlate ? setPickedElement : undefined} picked={pickedElement} />
              {isPlate && pickedElement !== null ? (() => {
                const preview = checked.preview;
                const touched = regionsOfElement(pickedElement, preview.mesh.quads, preview.mesh.node_sets, preview.mesh.element_sets, regionOptions(form, plate));
                return (
                  <div className="studio-picked" data-testid="picked-regions">
                    <span>Element {pickedElement + 1} belongs to:</span>
                    {touched.map((r) => (
                      <span key={r.name}><strong>{r.name}</strong>{" "}
                        <button type="button" className="studio-text-button" onClick={() => editPlate(withSupport(plate, r.name))}>hold</button>{" "}
                        <button type="button" className="studio-text-button" onClick={() => editPlate(withLoad(plate, r.name, r.kind))}>load</button></span>
                    ))}
                    {!touched.length ? <span className="studio-muted">no named region; draw a box around it</span> : null}
                  </div>
                );
              })() : null}
            </>
          ) : sketch ? (
            <div className="studio-panel" data-testid="sketch">
              <h3>The coupon <span className="studio-badge">sketch of the typed rows, not meshed</span></h3>
              <SketchScene sketch={sketch} />
              <p className="studio-muted">{sketch.width} by {sketch.length} {sketch.lengthUnit}{sketch.tabs !== null ? `, ${sketch.tabs} ${sketch.lengthUnit} tabs` : ""}{sketch.hole !== null ? `, a ${sketch.hole} ${sketch.lengthUnit} hole` : ""}, as typed. {sketch.toScale ? `The thickness is drawn in proportion, ${sketch.plies} plies.` : "The thickness is drawn as a thin slab until the plies and their thickness are given."} Check the setup to mesh it and see the held end and the load.</p>
            </div>
          ) : (
            <div className="studio-empty" data-testid="empty-scene">
              <h3>No model yet</h3>
              <p>Give the coupon&apos;s width and length under Geometry and a sketch appears here; check the setup and the mesh, the held tab and the pulled tab follow.</p>
            </div>
          )}
          {job ? <JobProgress job={job} /> : null}
        </>
      )}
    </section>
  );
}
