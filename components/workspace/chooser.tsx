"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderOpen, History, Plus } from "lucide-react";
import { mergeProjects, newLaminateProject, newProject, newWingProject, projectOfRecord, projectTitle, readProjects, upsert, writeProjects, type Project } from "@/lib/project-store";
import { answerWords, askToOpen, pastRuns, runWhen, type PastRun } from "@/lib/run-history";
import { printed } from "@/lib/studio-colors";
import { listJobs, listProjects, noProjectStore } from "@/lib/studio-api";
import { browserStorage, tabStorage, useAllTests } from "@/components/studio/project-context";
import { isTestEnabled } from "@/lib/enabled-tests";
import { problemLines } from "@/lib/laminate-chat";
import { TEST_CHOICES } from "@/lib/studio-chat";
import { wingAbout, wingMaterial } from "@/lib/wing";
import { workspace, WORKSPACES, type WorkspaceId } from "@/lib/workspaces";

function testTitle(test: string): string {
  return TEST_CHOICES.find((c) => c.test === test)?.title ?? test;
}

const when = (stamp: string): string => runWhen(stamp);

/** How many past analyses the list shows before "Show all". */
const RUNS_SHOWN = 8;

/** What a project is about, in a few words: a coupon's test, a laminate's layup, a wing's size; a coupon of a test the studio does not offer
 * yet (ADR-0089) says so, and stays listed. */
function about(project: Project, allTests: boolean): string {
  if (project.kind === "wing") return wingAbout(project.wing);
  if (project.kind === "fea") {
    const test = project.form.test;
    if (!test) return "–";
    return isTestEnabled(test, allTests) ? testTitle(test) : `${testTitle(test)}: not offered yet`;
  }
  const layup = problemLines(project.draft).find(([k]) => k === "Layup")?.[1];
  return layup || "–";
}

function materialOf(project: Project): string {
  if (project.kind === "wing") return wingMaterial(project.wing);
  if (project.kind === "fea") return project.form.library || project.form.own_name || "–";
  return problemLines(project.draft).find(([k]) => k === "Material")?.[1] || "–";
}

const ROUTE: Record<Project["kind"], WorkspaceId> = { fea: "fea", laminate: "laminate", wing: "wing" };
/** A project's kind is its workspace's one name (audit fea-screens-10). */
const kindWord = (kind: Project["kind"]): string => workspace(ROUTE[kind]).title;

/** Where the list comes from: loading, the account and this browser, this browser alone (the service keeps no projects), or this browser
 * because the saved projects could not be loaded (an outage, audit fea-screens-3). */
type Source = "checking" | "server" | "browser" | "down";
const SOURCE_WORDS: Record<Source, string> = {
  checking: "Loading your projects…",
  server: "Saved to your account and in this browser.",
  browser: "Projects are saved in this browser only; clearing its site data removes them.",
  down: "Saved projects could not be loaded. Showing the ones in this browser. Reload to try again.",
};

/** `/workspace` (ADR-0062): the projects of both kinds, the last changed first, one tile per kind of work, and under them the person's
 * own finished analyses with each one's answer, opened again as they were solved (ADR-0109). The list is this browser's
 * merged with the server's (part 6): a project kept on another machine appears here, and the later change wins. Opening a project moves
 * it to the front, which is what its workspace picks up; a new project starts blank. */
export function WorkspaceChooser({ apiBaseUrl }: { apiBaseUrl: string }) {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [source, setSource] = useState<Source>(apiBaseUrl ? "checking" : "browser");
  const allTests = useAllTests(apiBaseUrl);
  // the person's own finished analyses, newest first (ADR-0109); null while loading, "down" when they could not be read
  const [runs, setRuns] = useState<PastRun[] | "down" | null>(null);
  const [allRuns, setAllRuns] = useState(false);
  useEffect(() => {
    if (!apiBaseUrl) return;
    const controller = new AbortController();
    listJobs(apiBaseUrl, controller.signal).then((jobs) => setRuns(pastRuns(jobs))).catch(() => { if (!controller.signal.aborted) setRuns("down"); });
    return () => controller.abort("replaced");
  }, [apiBaseUrl]);
  useEffect(() => {
    const local = readProjects(browserStorage());
    setProjects(local);
    if (!apiBaseUrl) return;
    const controller = new AbortController();
    listProjects(apiBaseUrl, controller.signal).then((records) => {
      const merged = mergeProjects(local, records.map(projectOfRecord).filter((p): p is Project => p !== null));
      writeProjects(merged, browserStorage());
      setProjects(merged);
      setSource("server");
    }).catch((error) => {
      if (controller.signal.aborted) return;
      const keepsNone = noProjectStore(error);
      setSource(keepsNone ? "browser" : "down");
      if (!keepsNone) console.warn("the projects on the server could not be read", error);
    });
    return () => controller.abort("replaced");
  }, [apiBaseUrl]);

  function open(project: Project) {
    const store = browserStorage();
    writeProjects(upsert(readProjects(store), project), store);
    router.push(workspace(ROUTE[project.kind]).href);
  }
  /** A past analysis in the coupon workspace, as it was solved; where this tab keeps nothing, its results in the viewer's own page. */
  function openRun(run: PastRun) {
    router.push(askToOpen(tabStorage(), run.job_id) ? workspace("fea").href : `/workspace/fea/view?job=${encodeURIComponent(run.job_id)}`);
  }
  function create(id: WorkspaceId) {
    if (id === "fea") open(newProject());
    else if (id === "laminate") open(newLaminateProject());
    else if (id === "wing") open(newWingProject()); // a new wing starts from the example, to change (ADR-0120)
    else router.push(workspace(id).href);
  }

  return (
    <div className="ws-chooser">
      <div className="studio-heading">
        <span className="eyebrow">WORKSPACE</span>
        <h1>Start a project</h1>
        <p>Set up and solve a coupon test, work out a laminate&apos;s response to loads, or design a wing.</p>
      </div>
      <div className="ws-tiles" data-testid="workspace-tiles">
        {WORKSPACES.map((w) => (
          <button type="button" key={w.id} className="ws-tile" data-workspace={w.id} onClick={() => create(w.id)}>
            <span className="eyebrow">{w.eyebrow}</span>
            <h3><Plus size={15} /> New {w.title} project</h3>
            <p>{w.detail}</p>
          </button>
        ))}
      </div>
      <section className="studio-panel ws-projects" data-testid="workspace-projects" data-source={source}>
        <h3><FolderOpen size={15} /> Your projects</h3>
        {source === "down"
          ? <p className="studio-alert" role="status" data-testid="projects-source">{SOURCE_WORDS.down}</p>
          : <p className="studio-muted" data-testid="projects-source">{SOURCE_WORDS[source]}</p>}
        {projects.length ? (
          <table className="studio-table">
            <thead><tr><th>Project</th><th>Kind</th><th>About</th><th>Material</th><th>Last change</th><th></th></tr></thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.id} data-project={p.id} data-kind={p.kind}>
                  <td>{projectTitle(p)}</td>
                  <td>{kindWord(p.kind)}</td>
                  <td>{about(p, allTests)}</td>
                  <td>{materialOf(p)}</td>
                  <td>{when(p.updated)}</td>
                  <td><button type="button" className="chat-link" onClick={() => open(p)}>Open</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="studio-muted">None yet. Start one from the tiles above.</p>}
      </section>
      {apiBaseUrl ? (
        <section className="studio-panel ws-projects" data-testid="workspace-analyses" data-state={runs === null ? "checking" : runs === "down" ? "down" : "listed"}>
          <h3><History size={15} /> Your analyses</h3>
          {runs === null ? <p className="studio-muted">Loading your analyses…</p>
            : runs === "down" ? <p className="studio-muted" data-testid="analyses-down">Your past analyses could not be loaded. Reload to try again.</p>
            : runs.length ? (
              <>
                <table className="studio-table">
                  <thead><tr><th>Coupon</th><th>Answer</th><th>First to fail</th><th>Finished</th><th></th></tr></thead>
                  <tbody>
                    {(allRuns ? runs : runs.slice(0, RUNS_SHOWN)).map((run) => {
                      const words = answerWords(run.answer, printed);
                      return (
                        <tr key={run.job_id} data-run={run.job_id}>
                          <td>{run.coupon}</td>
                          <td data-testid="analysis-answer">{words ? <><strong>{words.verdict}</strong> at {words.loading}</> : "–"}</td>
                          <td>{words ? words.facts.join(" · ") : "–"}</td>
                          <td>{when(run.finished_at)}</td>
                          <td><button type="button" className="chat-link" onClick={() => openRun(run)}>Open</button></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {!allRuns && runs.length > RUNS_SHOWN
                  ? <p><button type="button" className="chat-link" onClick={() => setAllRuns(true)} data-testid="analyses-all">Show all {runs.length}</button></p> : null}
              </>
            ) : <p className="studio-muted" data-testid="analyses-none">None yet. A finished analysis appears here.</p>}
        </section>
      ) : null}
    </div>
  );
}
