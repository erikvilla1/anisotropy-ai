"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  clock, mergeNewer, money, NotHere, readActivity, readPlanStory, readWeekly, REFRESH_MS, storyLines, toneOf, whoShort,
  type ActivityEvent, type PlanStory, type Weekly,
} from "@/lib/oversight";

type Tab = "now" | "weekly";

/** The founders' AI activity page (ADR-0145): every call to the model, plan and approval newest first, refreshed every few seconds;
 * a plan's story beside the feed when its row is picked; and the last eight weeks. Read only. */
export function AiActivity({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [tab, setTab] = useState<Tab>("now");
  const [events, setEvents] = useState<ActivityEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notHere, setNotHere] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [story, setStory] = useState<PlanStory | null>(null);
  const [week, setWeek] = useState<Weekly | null>(null);
  const [older, setOlder] = useState(true);
  const newest = useRef<string | null>(null);

  const failed = useCallback((e: unknown) => {
    if (e instanceof NotHere) setNotHere(true);
    else if (!(e instanceof DOMException && e.name === "AbortError")) setError(e instanceof Error ? e.message : String(e));
  }, []);

  useEffect(() => {
    const stop = new AbortController();
    readActivity(apiBaseUrl, {}, stop.signal).then((read) => { setEvents(read); newest.current = read[0]?.at ?? null; }, failed);
    return () => stop.abort();
  }, [apiBaseUrl, failed]);

  const loaded = events !== null;
  useEffect(() => {
    if (!loaded || notHere) return;
    const timer = window.setInterval(() => {
      const since = newest.current;
      if (!since) {
        readActivity(apiBaseUrl).then((read) => { if (read.length) { setEvents(read); newest.current = read[0].at; } }, failed);
        return;
      }
      readActivity(apiBaseUrl, { since }).then((read) => {
        if (!read.length) return;
        newest.current = read[0].at;
        setEvents((shown) => mergeNewer(shown ?? [], read));
      }, failed);
    }, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [apiBaseUrl, loaded, notHere, failed]);

  useEffect(() => {
    if (!picked) { setStory(null); return; }
    const stop = new AbortController();
    setStory(null);
    readPlanStory(apiBaseUrl, picked, stop.signal).then(setStory, failed);
    return () => stop.abort();
  }, [apiBaseUrl, picked, failed]);

  useEffect(() => {
    if (tab !== "weekly" || week) return;
    const stop = new AbortController();
    readWeekly(apiBaseUrl, stop.signal).then(setWeek, failed);
    return () => stop.abort();
  }, [apiBaseUrl, tab, week, failed]);

  const loadOlder = () => {
    const oldest = events?.at(-1)?.at;
    if (!oldest) return;
    readActivity(apiBaseUrl, { before: oldest }).then((read) => {
      if (!read.length) setOlder(false);
      setEvents((shown) => [...(shown ?? []), ...read]);
    }, failed);
  };

  if (notHere) {
    return <section className="ai-empty"><h1>Page not found</h1><p>There is nothing at this address.</p></section>;
  }

  return (
    <section className="ai-shell" data-testid="ai-activity">
      <header className="ai-top">
        <h1>AI activity</h1>
        <nav className="ai-tabs" aria-label="Views">
          <button type="button" aria-pressed={tab === "now"} onClick={() => setTab("now")}>Now</button>
          <button type="button" aria-pressed={tab === "weekly"} onClick={() => setTab("weekly")}>Weekly</button>
        </nav>
        <span className="ai-note">Founders only. Customers&rsquo; rows show what happened, not what they wrote.</span>
      </header>
      {error ? <p className="ai-error" role="alert">{error}</p> : null}
      {tab === "now" ? (
        <div className="ai-columns">
          <div className="ai-feed">
            {events === null ? <p className="ai-muted">Reading the activity&hellip;</p> : events.length === 0 ? (
              <p className="ai-muted">Nothing yet. Every call to the model, plan and approval appears here as it happens.</p>
            ) : (
              <>
                <table className="ai-table" data-testid="ai-feed">
                  <thead><tr><th>When</th><th>Who</th><th>What</th><th>Model</th><th>Outcome</th><th className="ai-num">Time</th><th className="ai-num">Cost</th></tr></thead>
                  <tbody>
                    {events.map((e) => (
                      <tr key={`${e.kind}-${e.at}-${e.plan ?? ""}-${e.run ?? ""}-${e.what}`} data-picked={e.plan !== null && e.plan === picked}
                        className={e.plan ? "ai-pickable" : undefined} onClick={e.plan ? () => setPicked(e.plan) : undefined}
                        tabIndex={e.plan ? 0 : undefined} onKeyDown={e.plan ? (k) => { if (k.key === "Enter") setPicked(e.plan); } : undefined}>
                        <td>{clock(e.at)}</td>
                        <td title={e.who}>{whoShort(e.who)}</td>
                        <td>{e.what}{e.ask && e.kind !== "call" ? <span className="ai-ask">{e.ask}</span> : null}</td>
                        <td>{e.model ?? <span className="ai-muted">no model</span>}{e.checked === false ? <span className="ai-flag"> not checked</span> : null}</td>
                        <td><span className="ai-dot" data-tone={toneOf(e)} />{e.outcome}</td>
                        <td className="ai-num">{e.seconds === null ? "–" : `${e.seconds.toFixed(1)} s`}</td>
                        <td className="ai-num">{money(e.cost_usd)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {older ? <button type="button" className="ai-more" onClick={loadOlder}>Show older</button> : null}
              </>
            )}
          </div>
          <aside className="ai-story" aria-live="polite" data-testid="ai-story">
            {!picked ? <p className="ai-muted">Pick a plan, or a call made for one, to see its story.</p> : !story ? <p className="ai-muted">Reading the plan&hellip;</p> : (
              <>
                <h2>One plan&rsquo;s story</h2>
                <p className="ai-muted">A {story.kind}, {whoShort(story.who)}, now {story.state}</p>
                <ol className="ai-lines">
                  {storyLines(story).map((line, i) => (
                    <li key={i}><span className="ai-dot" data-tone={line.tone} /><span><b>{line.head}</b>{line.detail ? <span className="ai-detail">{line.detail}</span> : null}</span></li>
                  ))}
                </ol>
              </>
            )}
          </aside>
        </div>
      ) : (
        <WeekView week={week} />
      )}
    </section>
  );
}

function cells(row: Record<string, string | number | boolean | null>, keys: string[]) {
  return keys.map((k) => <td key={k} className={typeof row[k] === "number" ? "ai-num" : undefined}>{row[k] === null ? "–" : String(row[k])}</td>);
}

function WeekView({ week }: { week: Weekly | null }) {
  if (!week) return <p className="ai-muted">Reading the weeks&hellip;</p>;
  const guards = ["week_of", "feature", "asked", "kept", "set_aside", "capped", "set_aside_pct", "usual_set_aside_pct", "flag"];
  const costs = ["week_of", "feature", "calls", "cost_usd", "cost_per_call_usd", "models", "flag"];
  return (
    <div className="ai-week" data-testid="ai-week">
      <p className="ai-muted">Since {week.since}, UTC weeks from Monday.</p>
      <h2>Calls answered by a model outside the checked list</h2>
      {week.unchecked.length === 0 ? <p className="ai-muted">None.</p> : (
        <table className="ai-table"><thead><tr><th>Week of</th><th>Model</th><th className="ai-num">Calls</th></tr></thead>
          <tbody>{week.unchecked.map((r, i) => <tr key={i}>{cells(r, ["week_of", "model", "calls"])}</tr>)}</tbody></table>
      )}
      <h2>Plans by how they ended</h2>
      {week.plans.length === 0 ? <p className="ai-muted">No plans yet.</p> : (
        <table className="ai-table"><thead><tr><th>Week of</th><th>On</th><th>Ended</th><th className="ai-num">Plans</th></tr></thead>
          <tbody>{week.plans.map((r, i) => <tr key={i}>{cells(r, ["week_of", "kind", "state", "plans"])}</tr>)}</tbody></table>
      )}
      <h2>Why plans were refused</h2>
      {week.refused.length === 0 ? <p className="ai-muted">None refused.</p> : (
        <table className="ai-table"><thead><tr><th>Reason</th><th className="ai-num">Plans</th></tr></thead>
          <tbody>{week.refused.map((r, i) => <tr key={i}><td>{r.reason}</td><td className="ai-num">{r.plans}</td></tr>)}</tbody></table>
      )}
      <h2>The guards, per route</h2>
      {week.guards.length === 0 ? <p className="ai-muted">No answers yet.</p> : (
        <table className="ai-table"><thead><tr><th>Week of</th><th>Route</th><th className="ai-num">Asked</th><th className="ai-num">Kept</th><th className="ai-num">Set aside</th>
          <th className="ai-num">Capped</th><th className="ai-num">Set aside %</th><th className="ai-num">Usual %</th><th>Flag</th></tr></thead>
          <tbody>{week.guards.map((r, i) => <tr key={i}>{cells(r, guards)}</tr>)}</tbody></table>
      )}
      <h2>Cost per feature</h2>
      {week.costs.length === 0 ? <p className="ai-muted">No calls yet.</p> : (
        <table className="ai-table"><thead><tr><th>Week of</th><th>Feature</th><th className="ai-num">Calls</th><th className="ai-num">US$</th><th className="ai-num">Per call</th>
          <th>Models</th><th>Flag</th></tr></thead>
          <tbody>{week.costs.map((r, i) => <tr key={i}>{cells(r, costs)}</tr>)}</tbody></table>
      )}
    </div>
  );
}
