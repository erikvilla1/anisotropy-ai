"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MODEL_FILE_LABELS, modelFile, StudioError, type ModelProgram } from "@/lib/studio-api";
import { PLATE_TEST } from "@/lib/studio-form";
import { workspaceValues } from "@/lib/tension-screen";
import { remembered, RUN_BY_KEY } from "./local";
import { useProject } from "./project-context";

/** Hands the browser a file to save, made from text. */
function save(text: string, name: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  const link = document.createElement("a");
  link.href = url; link.download = name;
  document.body.appendChild(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** The model as a file for the engineer's own program (ADR-0129): the rows as they stand are sent, the fea package writes the file,
 * and the browser saves it. The rows are the ones a live solve sends, so the file is the model on the page. The page computes nothing. */
export function useModelDownload() {
  const { apiBaseUrl, form, plate, allTests, offersAll } = useProject();
  const [busy, setBusy] = useState<ModelProgram | null>(null);
  const [problem, setProblem] = useState("");
  const [saved, setSaved] = useState("");
  const download = useCallback(async (program: ModelProgram) => {
    if (!apiBaseUrl) { setProblem("The model file is not available here."); return; }
    setBusy(program); setProblem(""); setSaved("");
    try {
      const rows = { ...form, filled_by: (form.filled_by ?? "").trim() || remembered(RUN_BY_KEY) }; // as the live solve names the file
      const values = workspaceValues(rows, plate, allTests || (offersAll && form.test !== PLATE_TEST)); // the rows a live solve sends
      const file = await modelFile(apiBaseUrl, values, program);
      save(file.text, file.name);
      setSaved(`Saved the ${MODEL_FILE_LABELS[program]}.`); // the file's kind, not its name: the name carries the program's (ADR-0091)
    } catch (error) {
      setProblem(error instanceof StudioError ? error.message : "The model file could not be written. Your inputs are kept; try again.");
    } finally {
      setBusy(null);
    }
  }, [apiBaseUrl, form, plate, allTests, offersAll]);
  return { busy, problem, saved, download };
}

/** The programs offered to this visitor: the Ansys file where it is offered (ADR-0129). */
export function useModelPrograms(): ModelProgram[] {
  const { ansysModel } = useProject();
  return ansysModel ? ["abaqus", "ansys"] : ["abaqus"];
}

/** "Download model" over the model: a menu of the files offered. */
export function ModelDownloadMenu() {
  const programs = useModelPrograms();
  const { busy, problem, saved, download } = useModelDownload();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => { if (!box.current?.contains(event.target as Node)) setOpen(false); };
    const key = (event: KeyboardEvent) => { if (event.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", away); document.addEventListener("keydown", key);
    return () => { document.removeEventListener("mousedown", away); document.removeEventListener("keydown", key); };
  }, [open]);
  // spans throughout: the menu sits in the model's heading, where only phrasing content belongs
  return (
    <span className="studio-model-tools" ref={box} data-testid="model-download">
      <button type="button" className="studio-model-button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)} disabled={busy !== null}
        data-testid="model-download-open">{busy ? "Writing the file…" : "Download model"}</button>
      {open ? (
        <span className="studio-model-menu" role="menu">
          {programs.map((program) => (
            <button key={program} type="button" role="menuitem" onClick={() => { setOpen(false); void download(program); }} data-testid={`model-download-${program}`}>
              {MODEL_FILE_LABELS[program]}</button>
          ))}
          <span className="studio-muted">The model as it is set up now, for your own copy of the program.</span>
        </span>
      ) : null}
      {problem ? <span className="studio-problem studio-model-note" role="alert" data-testid="model-download-problem">{problem}</span> : null}
      {saved && !open ? <span className="studio-muted studio-model-note" role="status" data-testid="model-download-saved">{saved}</span> : null}
    </span>
  );
}

/** The same downloads as buttons in the assistant's answer (ADR-0129): one per file the answer offers. */
export function ModelFileButtons({ offers }: { offers: ModelProgram[] }) {
  const { busy, problem, saved, download } = useModelDownload();
  if (!offers.length) return null;
  return (
    <div data-testid="chat-model-file-buttons">
      <div className="chat-chips">
        {offers.map((program) => (
          <button key={program} type="button" onClick={() => void download(program)} disabled={busy !== null} data-testid={`chat-model-file-${program}`}>
            {busy === program ? "Writing the file…" : MODEL_FILE_LABELS[program]}</button>
        ))}
      </div>
      {problem ? <p className="studio-problem" role="alert" data-testid="chat-model-file-problem">{problem}</p> : null}
      {saved ? <p className="studio-muted" role="status">{saved}</p> : null}
    </div>
  );
}
