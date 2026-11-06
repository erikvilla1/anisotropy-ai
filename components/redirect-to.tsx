"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

/** A page that moved: the browser goes to its new address with the same query, and a link is shown meanwhile. The site is a static
 * export, so the redirect runs in the browser, reading the query from the address itself (the prerendered page has none). */
export function RedirectTo({ path }: { path: string }) {
  const router = useRouter();
  const [target, setTarget] = useState(path);
  useEffect(() => {
    const query = window.location.search.replace(/^\?/, "");
    const to = query ? `${path}?${query}` : path;
    setTarget(to);
    router.replace(to);
  }, [router, path]);
  return <p className="studio-status" data-testid="moved">This page moved to <a href={target}>{path}</a>.</p>;
}
