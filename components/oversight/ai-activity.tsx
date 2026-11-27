"use client";

import { useEffect, useRef, useState } from "react";
import {
  clock, givenUp, money, NO_ADDRESS, NotHere, PlanGone, poll, readActivity, readPlanStory, readWeekly, REFRESH_MS, storyLines, toneOf,
  watchFeed, whoShort, type Feed, type PlanStory, type Watch, type Weekly,
} from "@/lib/oversight";

type Tab = "now" | "weekly";
/** One reading of the page as it stands: not asked yet or under way (null), read, or failed with the words to show. */
type Read<T> = { value: T } | { error: string } | null;

const words = (e: unknown): string => (e instanceof Error ? e.message : String(e));

/** The founders' AI activity page (ADR-0145): every call to the model, plan and approval newest first, read again every few seconds
 * while the tab is in view; a plan's story beside the feed when its row is picked; and the last eight weeks. Read only. What goes
 * wrong with one reading is said where that reading shows, and goes when the reading next succeeds. */
export function AiActivity({ apiBaseUrl }: { apiBaseUrl: string }) {
  const [tab, setTab] = useState<Tab>("now");
  const [feed, setFeed] = useState<Feed | null>(null);
  const [error, setError] = useState<string | null>(apiBaseUrl ? null : NO_ADDRESS);
  const [notHere, setNotHere] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const [story, setStory] = useState<Read<PlanStory>>(null);
  const [week, setWeek] = useState<Read<Weekly>>(null);
  const [weekAsked, setWeekAsked] = useState(0);
  const [olderAsked, setOlderAsked] = useState(false);
  const watch = useRef<Watch | null>(null);

  // The feed: read now, then again every REFRESH_MS after each read ends, while the tab is in view. A first read that fails is
  // tried again the same way, and its error goes with the next read that succeeds.
  useEffect(() => {
    if (!apiBaseUrl) { setError(NO_ADDRESS); return; }
    const stop = new AbortController();
    let end = () => {};
    const watching = watchFeed((ask) => readActivity(apiBaseUrl, ask, stop.signal), {
      feed: (read) => { setFeed(read); setError(null); },
      error: (e) => {
        if (e instanceof NotHere) { setNotHere(true); end(); } else if (!givenUp(e)) setError(words(e));
      },
    });
    watch.current = watching;
    end = poll(() => watching.refresh(), REFRESH_MS);
    return () => { end(); watching.stop(); stop.abort(); watch.current = null; };
  }, [apiBaseUrl]);

  // A plan's story. A plan that is no longer there, or a story that could not be read, is said in the story's panel: the feed stays.
  useEffect(() => {
    setStory(null);
    if (!picked) return;
    const stop = new AbortController();
    readPlanStory(apiBaseUrl, picked, stop.signal).then((value) => setStory({ value }), (e) => {
      if (e instanceof NotHere) setNotHere(true);
      else if (e instanceof PlanGone) setStory({ error: "This plan is no longer in the records: its project was deleted." });
      else if (!givenUp(e)) setStory({ error: words(e) });
    });
    return () => stop.abort();
  }, [apiBaseUrl, picked]);

  // The weeks, read when the tab is opened; "Try again" asks once more after a failure.
  const weekRead = week !== null && "value" in week;
  useEffect(() => {
    if (tab !== "weekly" || weekRead) return;
    const stop = new AbortController();
    setWeek(null);
    readWeekly(apiBaseUrl, stop.signal).then((value) => setWeek({ value }), (e) => {
      if (e instanceof NotHere || e instanceof PlanGone) setNotHere(true);
      else if (!givenUp(e)) setWeek({ error: words(e) });
    });
    return () => stop.abort();
  }, [apiBaseUrl, tab, weekRead, weekAsked]);

  const showOlder = () => {
    if (!watch.current || olderAsked) return;
    setOlderAsked(true);
    void watch.current.older().finally(() => setOlderAsked(false));
  };

  if (notHere) {
    return <section className="ai-empty"><h1>Page not found</h1><p>There is nothing at this address.</p></section>;
  }

  const events = feed?.events ?? null;
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
      {tab === "now" ? (
        <div className="ai-columns">
          <div className="ai-feed">
            {error ? <p className="ai-error" role="alert" data-testid="ai-feed-error">{error}{apiBaseUrl ? " The page keeps trying." : ""}</p> : null}
            {events === null ? (error ? null : <p className="ai-muted">Reading the activity&hellip;</p>) : events.length === 0 ? (
              <p className="ai-muted">Nothing yet. Every call to the model, plan and approval appears here as it happens.</p>
            ) : (
              <>
                <table className="ai-table" data-testid="ai-feed">
                  <thead><tr><th>When</th><th>Who</th><th>What</th><th>Model</th><th>Outcome</th><th className="ai-num">Time</th><th className="ai-num">Cost</th></tr></thead>
                  <tbody>
                    {events.map((e) => {
                      const plan = e.plan;
                      const shown = plan !== null && plan === picked;
                      return (
                        // A click anywhere on a plan's row shows its story; the keyboard and a screen reader have the button in it.
                        <tr key={e.key} data-picked={shown} className={plan ? "ai-pickable" : undefined} onClick={plan ? () => setPicked(plan) : undefined}>
                          <td>{clock(e.at)}</td>
                          <td title={e.who}>{whoShort(e.who)}</td>
                          <td>
                            {plan ? (
                              <button type="button" className="ai-pick" aria-pressed={shown} aria-controls="ai-story"
                                aria-label={`${e.what}: show this plan's story`} onClick={() => setPicked(plan)}>{e.what}</button>
                            ) : e.what}
                            {e.ask && e.kind !== "call" ? <span className="ai-ask">{e.ask}</span> : null}
                          </td>
                          <td>{e.model ?? <span className="ai-muted">no model</span>}{e.checked === false ? <span className="ai-flag"> not checked</span> : null}</td>
                          <td><span className="ai-dot" data-tone={toneOf(e)} />{e.outcome}</td>
                          <td className="ai-num">{e.seconds === null ? "–" : `${e.seconds.toFixed(1)} s`}</td>
                          <td className="ai-num">{money(e.cost_usd)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {feed?.floor ? <button type="button" className="ai-more" onClick={showOlder} disabled={olderAsked}>{olderAsked ? "Reading older…" : "Show older"}</button> : null}
              </>
            )}
          </div>
          <aside className="ai-story" id="ai-story" aria-live="polite" data-testid="ai-story">
            {!picked ? <p className="ai-muted">Pick a plan, or a call made for one, to see its story.</p> : story === null ? <p className="ai-muted">Reading the plan&hellip;</p>
              : "error" in story ? <p className="ai-error" data-testid="ai-story-error">{story.error}</p> : (
                <>
                  <h2>One plan&rsquo;s story</h2>
                  <p className="ai-muted">A {story.value.kind}, {whoShort(story.value.who)}, now {story.value.state}</p>
                  <ol className="ai-lines">
                    {storyLines(story.value).map((line, i) => (
                      <li key={i}><span className="ai-dot" data-tone={line.tone} /><span><b>{line.head}</b>{line.detail ? <span className="ai-detail">{line.detail}</span> : null}</span></li>
                    ))}
                  </ol>
                </>
              )}
          </aside>
        </div>
      ) : week !== null && "error" in week ? (
        <p className="ai-error" role="alert" data-testid="ai-week-error">{week.error} <button type="button" className="ai-more" onClick={() => setWeekAsked((n) => n + 1)}>Try again</button></p>
      ) : (
        <WeekView week={week?.value ?? null} />
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
