"use client";

import { useCallback, useEffect, type ReactNode } from "react";
import type { Preview } from "@/lib/studio-api";
import { followsShape, PLATE_TEST } from "@/lib/studio-form";
import { regionOptions, regionsOfElement, shapeWords, withLoad, withSupport, type PlateLists } from "@/lib/studio-plate";
import { sketchOf } from "@/lib/studio-sketch";
import { ANALYSIS_UNAVAILABLE } from "@/lib/studio-copy";
import { revealPanel } from "@/components/workspace/panels/step-panel";
import { Slot, useCanvasSlots, ViewMenu } from "@/components/workspace/canvas-slots";
import { JobProgress } from "./job-progress";
import { ModelDownloadMenu } from "./model-download";
import { useProject } from "./project-context";
import { ResultsView } from "./results-view";
import { Scene } from "./scene";
import type { SceneProps } from "./scene-canvas";
import { proposedInputs, sceneInputs } from "./scene-inputs";
import { SketchScene } from "./sketch";
import { shownResults } from "./use-coupon-run";

/** The package's preview: the mesh with every boundary condition and load drawn on it and listed under it, in words (ADR-0110). */
export function PreviewScene({ preview, onPick, picked, proposed, emphasis = null, tools = null }: { preview: Preview; onPick?: (element: number | null) => void; picked?: number | null;
  proposed?: SceneProps["proposed"]; emphasis?: SceneProps["emphasis"];
  /** what can be done with the model as a whole, at the right of its heading: the download of its file (ADR-0129) */
  tools?: ReactNode }) {
  const { held, loads, about } = sceneInputs(preview);
  const canvas = useCanvasSlots(); // in the FEA workspace's layout the heading and the words go to the results card (ADR-0134)
  const heading = <h3>The model <span className="studio-badge">{preview.mesh.element_count} elements, {preview.mesh.node_count} nodes</span>{tools}</h3>;
  const words = (
    <>
      {preview.shape?.length ? <p className="studio-muted" data-testid="preview-shape">{shapeWords(preview.shape)}</p> : null}
      {onPick ? <p className="studio-muted">Click an element to hold or load its regions.</p> : null}
    </>
  );
  return (
    <div className="studio-panel" data-testid="preview">
      {canvas ? null : heading}
      <Scene nodes={preview.mesh.nodes} quads={preview.mesh.quads} thickness={preview.geometry.thickness} held={held} loads={loads} proposed={proposed ?? null}
        about={about} onPick={onPick} picked={picked ?? null} emphasis={emphasis} />
      {canvas ? <Slot name="view"><div className="cv-model-words" data-testid="preview-card">{heading}{words}<ViewMenu summary="The model as set up" /></div></Slot> : words}
    </div>
  );
}

/** The centre of the coupon FEA workspace (ADR-0062): the sketch of the typed rows until the setup is checked, the package's preview after
 * it, the fields after a run; a plate's regions are picked here by clicking an element (ADR-0054). Every number comes from the fea package
 * through the API (ADR-0051); the sketch draws typed rows only. */
export function CouponStudio({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { form, plate, setPlate, run: runner, picked, setPicked, place, proposed, emphasis, allTests, view, setShownField } = useProject();
  const { checked, job, explanation, live, living, problem } = runner;
  // the newer of our kernel's live answer and the full run's fields (ADR-0086): an edit after a run is answered live, a run after it replaces it
  const { fields: shown, live: showLive } = shownResults(runner);
  const shownExplanation = showLive ? live?.explanation ?? null : explanation;
  const { clearChecked } = runner;
  // a hold or a load added by a click opens where it is listed: the full form's panel, or the model tree's tab (ADR-0111)
  const editPlate = useCallback((lists: PlateLists, where: "conditions" | "loads") => {
    setPlate(lists); clearChecked();
    window.setTimeout(() => revealPanel(allTests ? "loads" : where), 0);
  }, [setPlate, clearChecked, allTests]);
  const isPlate = form.test === PLATE_TEST;
  // the element clicked on a plate's preview is the project's, as one clicked on the results is: the assistant reads "here" from it
  // (ADR-0101). A new preview is a new mesh, so the click on the last one is let go; the results view keeps its own.
  const previewed = checked?.preview ?? null;
  const pickedElement = shown ? null : picked;
  useEffect(() => { if (!shown) setPicked(null); }, [previewed, shown, setPicked]);
  const viewerLink = job ? `/workspace/fea/view?job=${encodeURIComponent(job.job_id)}` : null;
  const canvas = useCanvasSlots(); // in the FEA workspace's layout the run's steps and the files go to the card's project column (ADR-0134)
  const sketch = !shown && !checked?.preview ? sketchOf(form, isPlate ? plate : null) : null;
  return (
    <section className="studio-output">
      <Slot name="project">
        {job ? <JobProgress job={job} brief={!allTests} /> : null}
        {/* the model as a file for the engineer's own program, once there is a model to write (ADR-0129): beside the results' link
            here, and in the model's heading before a run, so it takes no room of its own from the model. In the FEA workspace's layout
            it stays here from the first model on, one menu that a run's results arriving does not close (ADR-0134) */}
        {shown || (canvas && checked?.preview) ? (
          <div className="studio-viewer-row">
            {shown && viewerLink && !showLive ? <p className="studio-viewer-link"><a href={viewerLink} target="_blank" rel="noreferrer" data-testid="viewer-link">Open results in a new window</a></p> : <span />}
            <ModelDownloadMenu />
          </div>
        ) : null}
      </Slot>
      {shown ? (
        <>
          <ResultsView fields={shown} explanation={shownExplanation} job={showLive ? null : job} apiBase={apiBaseUrl} preview={checked?.preview ?? null}
            live={showLive && live ? { seconds: live.seconds, warm: live.warm } : null} updating={living} showFiles={false}
            onPicked={setPicked} place={place} proposed={isPlate ? proposed : null} emphasis={emphasis} view={view} onShown={setShownField}
            linearPreview={Boolean(showLive && live) && followsShape(form)} />
        </>
      ) : (
        <>
          {checked?.preview ? (
            <>
              <PreviewScene preview={checked.preview} tools={canvas ? null : <ModelDownloadMenu />} onPick={isPlate ? setPicked : undefined} picked={pickedElement}
                proposed={isPlate ? proposedInputs(checked.preview, proposed) : null} emphasis={emphasis} />
              {isPlate && pickedElement !== null ? <Slot name="over">{(() => {
                const preview = checked.preview;
                const touched = regionsOfElement(pickedElement, preview.mesh.quads, preview.mesh.node_sets, preview.mesh.element_sets, regionOptions(form, plate));
                return (
                  <div className="studio-picked" data-testid="picked-regions">
                    <span>Element {pickedElement + 1} belongs to:</span>
                    {touched.map((r) => (
                      <span key={r.name}><strong>{r.name}</strong>{" "}
                        <button type="button" className="studio-text-button" onClick={() => editPlate(withSupport(plate, r.name), "conditions")}>hold</button>{" "}
                        <button type="button" className="studio-text-button" onClick={() => editPlate(withLoad(plate, r.name, r.kind), "loads")}>load</button></span>
                    ))}
                    {!touched.length ? <span className="studio-muted">no named region; draw a box around it</span> : null}
                  </div>
                );
              })()}</Slot> : null}
            </>
          ) : sketch ? (
            <div className="studio-panel" data-testid="sketch">
              {canvas ? null : <h3>The coupon <span className="studio-badge">sketch, not meshed</span></h3>}
              <SketchScene sketch={sketch} />
              <SketchWords canvas={canvas !== null}><p className="studio-muted">{sketch.width} × {sketch.length} {sketch.lengthUnit}{sketch.tabs !== null ? `, ${sketch.tabs} ${sketch.lengthUnit} tabs` : ""}{sketch.tabThickness !== null ? ` bonded ${sketch.tabThickness} ${sketch.lengthUnit} thick with a ${sketch.tabBevel}° bevel` : ""}{sketch.hole !== null ? `, a ${sketch.hole} ${sketch.lengthUnit} hole` : ""}{sketch.dogbone !== null ? `, a dog-bone narrowing to ${sketch.dogbone.narrowWidth} by ${sketch.dogbone.narrowLength} ${sketch.lengthUnit} through ${sketch.dogbone.radius} ${sketch.lengthUnit} fillets${sketch.dogbone.outerRadius !== null ? ` and ${sketch.dogbone.outerRadius} ${sketch.lengthUnit} outer radii` : ""}` : ""}{sketch.strain !== null ? `, a ${sketch.strain.length} ${sketch.lengthUnit} ${sketch.strain.device} at the centre` : ""}{sketch.isotropic && sketch.toScale ? `, ${sketch.thickness} ${sketch.lengthUnit} thick` : ""}.{sketch.standard ? ` Sized for ${sketch.standard}${sketch.specimen ? `, ${sketch.specimen}` : ""}.` : ""}</p></SketchWords>
            </div>
          ) : (
            <div className="studio-empty" data-testid="empty-scene">
              <h3>No model yet</h3>
              {/* while the service is down, the empty stage says what it waits for (audit fea-run-48) */}
              <p>{problem === ANALYSIS_UNAVAILABLE ? "The model appears when the analysis service responds." : "The model appears here once the coupon is set up."}</p>
            </div>
          )}
        </>
      )}
    </section>
  );
}

/** The sketch's words: under it, or in the results card in the FEA workspace's layout (ADR-0134), with its heading. */
function SketchWords({ canvas, children }: { canvas: boolean; children: ReactNode }) {
  if (!canvas) return <>{children}</>;
  return <Slot name="view"><div className="cv-model-words" data-testid="sketch-card"><h3>The coupon <span className="studio-badge">sketch, not meshed</span></h3>{children}</div></Slot>;
}
