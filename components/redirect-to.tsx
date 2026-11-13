"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

/** How long the page waits for the new address's content to take the focus (about ten seconds of frames). */
const FOCUS_FRAMES = 600;

/** A page that moved. On the hosted site the Worker answers its address with a 301 to the new one (ADR-0058 amendment 2), so this
 * page is the fallback where no Worker runs (the dev server, a plain static copy): the browser goes to the new address with the
 * same query, saying where meanwhile, and once the new page is there the focus moves to its content, as a page load would leave it.
 * The site is a static export, so the query is read from the address itself (the prerendered page has none). */
export function RedirectTo({ path, label }: { path: string; label: string }) {
  const router = useRouter();
  const [target, setTarget] = useState(path);
  useEffect(() => {
    const query = window.location.search.replace(/^\?/, "");
    const to = query ? `${path}?${query}` : path;
    setTarget(to);
    router.replace(to);
    // This page is gone by the time the new one is drawn, so the wait is not cancelled with it.
    let frames = 0;
    const focusMain = () => {
      const main = document.getElementById("main");
      if (window.location.pathname.replace(/\/+$/, "") === path && main && !main.querySelector("[data-testid=moved]")) {
        if (!main.hasAttribute("tabindex")) main.setAttribute("tabindex", "-1");
        main.focus({ preventScroll: true });
      } else if (++frames < FOCUS_FRAMES) window.requestAnimationFrame(focusMain);
    };
    window.requestAnimationFrame(focusMain);
  }, [router, path]);
  return (
    <p className="studio-status" role="status" data-testid="moved">
      Opening <a href={target}>{label}</a>…
    </p>
  );
}
