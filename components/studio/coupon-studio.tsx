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
      {onPick ? <p className="studio-muted">Click an element to hold or load its regions.</p> : null}
    </div>
  );
}

/** The centre of the coupon FEA workspace (ADR-0062): the sketch of the typed rows until the setup is checked, the package's preview after
 * it, the fields after a run; a plate's regions are picked here by clicking an element (ADR-0054). Every number comes from the fea package
 * through the API (ADR-0051); the sketch draws typed rows only. */
export function CouponStudio({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { form, plate, setPlate, run: runner } = useProject();
  const { checked, job, fields, explanation, live, living, liveAt, fieldsAt } = runner;
  // the newer of our kernel's live answer and the full run's fields (ADR-0086): an edit after a run is answered live, a run after it replaces it
  const showLive = Boolean(live?.fields) && (!fields || liveAt > fieldsAt);
  const shown = showLive ? live?.fields ?? null : fields;
  const shownExplanation = showLive ? live?.explanation ?? null : explanation;
  const [pickedElement, setPickedElement] = useState<number | null>(null);
  const { clearChecked } = runner;
  const editPlate = useCallback((lists: PlateLists) => { setPlate(lists); clearChecked(); }, [setPlate, clearChecked]);
  const isPlate = form.test === PLATE_TEST;
  const viewerLink = job ? `/workspace/fea/view?job=${encodeURIComponent(job.job_id)}` : null;
  const sketch = !shown && !checked?.preview ? sketchOf(form, isPlate ? plate : null) : null;
  return (
    <section className="studio-output">
      {job ? <JobProgress job={job} /> : null}
      {shown ? (
        <>
          {viewerLink && !showLive ? <p className="studio-viewer-link"><a href={viewerLink} target="_blank" rel="noreferrer" data-testid="viewer-link">Open results in a new window</a></p> : null}
          <ResultsView fields={shown} explanation={shownExplanation} job={showLive ? null : job} apiBase={apiBaseUrl} preview={checked?.preview ?? null}
            live={showLive && live ? { seconds: live.seconds, warm: live.warm } : null} updating={living} showFiles={false} />
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
              <h3>The coupon <span className="studio-badge">sketch, not meshed</span></h3>
              <SketchScene sketch={sketch} />
              <p className="studio-muted">{sketch.width} × {sketch.length} {sketch.lengthUnit}{sketch.tabs !== null ? `, ${sketch.tabs} ${sketch.lengthUnit} tabs` : ""}{sketch.tabThickness !== null ? ` bonded ${sketch.tabThickness} ${sketch.lengthUnit} thick with a ${sketch.tabBevel}° bevel` : ""}{sketch.hole !== null ? `, a ${sketch.hole} ${sketch.lengthUnit} hole` : ""}{sketch.dogbone !== null ? `, a dog-bone narrowing to ${sketch.dogbone.narrowWidth} by ${sketch.dogbone.narrowLength} ${sketch.lengthUnit} through ${sketch.dogbone.radius} ${sketch.lengthUnit} fillets${sketch.dogbone.outerRadius !== null ? ` and ${sketch.dogbone.outerRadius} ${sketch.lengthUnit} outer radii` : ""}` : ""}{sketch.strain !== null ? `, a ${sketch.strain.length} ${sketch.lengthUnit} ${sketch.strain.device} at the centre` : ""}{sketch.isotropic && sketch.toScale ? `, ${sketch.thickness} ${sketch.lengthUnit} thick` : ""}.{sketch.standard ? ` Sized for ${sketch.standard}${sketch.specimen ? `, ${sketch.specimen}` : ""}.` : ""}</p>
            </div>
          ) : (
            <div className="studio-empty" data-testid="empty-scene">
              <h3>No model yet</h3>
              <p>The model appears here once the coupon is set up.</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
