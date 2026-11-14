"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { FolderOpen, Plus } from "lucide-react";
import { mergeProjects, newLaminateProject, newProject, projectOfRecord, projectTitle, readProjects, upsert, writeProjects, type Project } from "@/lib/project-store";
import { listProjects, noProjectStore } from "@/lib/studio-api";
import { browserStorage, useAllTests } from "@/components/studio/project-context";
import { isTestEnabled } from "@/lib/enabled-tests";
import { problemLines } from "@/lib/laminate-chat";
import { TEST_CHOICES } from "@/lib/studio-chat";
import { workspace, WORKSPACES, type WorkspaceId } from "@/lib/workspaces";

function testTitle(test: string): string {
  return TEST_CHOICES.find((c) => c.test === test)?.title ?? test;
}

function when(stamp: string): string {
  const date = new Date(stamp);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/** What a project is about, in a few words: a coupon's test, a laminate's layup; a coupon of a test the studio does not offer yet (ADR-0089)
 * says so, and stays listed. */
function about(project: Project, allTests: boolean): string {
  if (project.kind === "fea") {
    const test = project.form.test;
    if (!test) return "–";
    return isTestEnabled(test, allTests) ? testTitle(test) : `${testTitle(test)}: not offered yet`;
  }
  const layup = problemLines(project.draft).find(([k]) => k === "Layup")?.[1];
  return layup || "–";
}

function materialOf(project: Project): string {
  if (project.kind === "fea") return project.form.library || project.form.own_name || "–";
  return problemLines(project.draft).find(([k]) => k === "Material")?.[1] || "–";
}

const ROUTE: Record<Project["kind"], WorkspaceId> = { fea: "fea", laminate: "laminate" };
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

/** `/workspace` (ADR-0062): the projects of both kinds, the last changed first, and one tile per kind of work. The list is this browser's
 * merged with the server's (part 6): a project kept on another machine appears here, and the later change wins. Opening a project moves
 * it to the front, which is what its workspace picks up; a new project starts blank. */
export function WorkspaceChooser({ apiBaseUrl }: { apiBaseUrl: string }) {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [source, setSource] = useState<Source>(apiBaseUrl ? "checking" : "browser");
  const allTests = useAllTests(apiBaseUrl);
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
  function create(id: WorkspaceId) {
    if (id === "fea") open(newProject());
    else if (id === "laminate") open(newLaminateProject());
  }

  return (
    <div className="ws-chooser">
      <div className="studio-heading">
        <span className="eyebrow">WORKSPACE</span>
        <h1>Start a project</h1>
        <p>Set up and solve a coupon test, or work out a laminate&apos;s response to loads.</p>
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
    </div>
  );
}
