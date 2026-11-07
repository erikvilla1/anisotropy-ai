"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FolderOpen, Plus } from "lucide-react";
import { mergeProjects, newLaminateProject, newProject, projectOfRecord, projectTitle, readProjects, upsert, writeProjects, type Project } from "@/lib/project-store";
import { listProjects, noProjectStore } from "@/lib/studio-api";
import { browserStorage } from "@/components/studio/project-context";
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

/** What a project is about, in a few words: a coupon's test, a laminate's layup. */
function about(project: Project): string {
  if (project.kind === "fea") return project.form.test ? testTitle(project.form.test) : "–";
  const layup = problemLines(project.draft).find(([k]) => k === "Layup")?.[1];
  return layup || "–";
}

function materialOf(project: Project): string {
  if (project.kind === "fea") return project.form.library || project.form.own_name || "–";
  return problemLines(project.draft).find(([k]) => k === "Material")?.[1] || "–";
}

const KIND_WORD: Record<Project["kind"], string> = { fea: "Coupon FEA", laminate: "Laminate response" };
const ROUTE: Record<Project["kind"], WorkspaceId> = { fea: "fea", laminate: "laminate" };

type Source = "checking" | "server" | "browser";
const SOURCE_WORDS: Record<Source, string> = {
  checking: "Reading the projects kept on the server…",
  server: "Kept on the server under your sign-in, and in this browser; a project from another machine appears here too.",
  browser: "Kept in this browser only: this API keeps no projects (run records are off), so clearing the site's data loses them.",
};

/** `/workspace` (ADR-0062): the projects of both kinds, the last changed first, and one tile per kind of work. The list is this browser's
 * merged with the server's (part 6): a project kept on another machine appears here, and the later change wins. Opening a project moves
 * it to the front, which is what its workspace picks up; a new project starts blank. */
export function WorkspaceChooser({ apiBaseUrl }: { apiBaseUrl: string }) {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [source, setSource] = useState<Source>(apiBaseUrl ? "checking" : "browser");
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
    }).catch((error) => { if (!controller.signal.aborted) setSource("browser"); if (!noProjectStore(error)) console.warn("the projects on the server could not be read", error); });
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
        <h1>What are we working out?</h1>
        <p>A coupon test by finite elements, a laminate under loads, or, later, geometry from a CAD file. Every number comes from the engine; the pages only ask and show.</p>
      </div>
      <div className="ws-tiles" data-testid="workspace-tiles">
        {WORKSPACES.map((w) => (
          w.status === "built" ? (
            <button type="button" key={w.id} className="ws-tile" data-workspace={w.id} data-status={w.status} onClick={() => create(w.id)}>
              <span className="eyebrow">{w.eyebrow}</span>
              <h3><Plus size={15} /> New {w.title.toLowerCase()} project</h3>
              <p>{w.detail}</p>
            </button>
          ) : (
            <Link key={w.id} className="ws-tile" href={w.href} data-workspace={w.id} data-status={w.status}>
              <span className="eyebrow">{w.eyebrow} · PLANNED</span>
              <h3>{w.title}</h3>
              <p>{w.detail}</p>
            </Link>
          )
        ))}
      </div>
      <section className="studio-panel ws-projects" data-testid="workspace-projects" data-source={source}>
        <h3><FolderOpen size={15} /> Your projects</h3>
        <p className="studio-muted" data-testid="projects-source">{SOURCE_WORDS[source]}</p>
        {projects.length ? (
          <table className="studio-table">
            <thead><tr><th>Project</th><th>Kind</th><th>About</th><th>Material</th><th>Last change</th><th></th></tr></thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.id} data-project={p.id} data-kind={p.kind}>
                  <td>{projectTitle(p)}</td>
                  <td>{KIND_WORD[p.kind]}</td>
                  <td>{about(p)}</td>
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
