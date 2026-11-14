/** The site's changelog (ADR-0077 amendment 46): the versions the team has published and what changed in each, as the home
 * page lists them, newest first. It is empty until a version is published: the lead's word of 2026-11-14 is that nothing
 * is yet. A release here is one of CHANGELOG.md's released versions, cut down to a title and a few lines for a visitor;
 * tests/changelog.test.ts checks that each is in that file with the same date, so nothing is announced here that the
 * repository does not record. */

/** What kind of change a line is. The list shows the word itself, never a colour alone. */
export const CHANGE_KINDS = ["Added", "Improved", "Fixed"] as const;
export type ChangeKind = (typeof CHANGE_KINDS)[number];

export type Release = {
  /** The version as CHANGELOG.md's heading names it, for example "Engine 0.1.0". */
  version: string;
  /** The day it was released, as YYYY-MM-DD. */
  date: string;
  /** What the release is, in a few words. */
  title: string;
  changes: { kind: ChangeKind; text: string }[];
};

export const releases: readonly Release[] = [];

/** What is wrong with a list of releases, in words; empty when it can be shown. */
export function releaseProblems(list: readonly Release[]): string[] {
  const problems: string[] = [];
  list.forEach((release, index) => {
    const name = release.version || `release ${index + 1}`;
    if (!release.version.trim()) problems.push(`${name} has no version`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(release.date) || Number.isNaN(Date.parse(`${release.date}T00:00:00Z`))) problems.push(`${name}: "${release.date}" is not a day`);
    if (!release.title.trim()) problems.push(`${name} has no title`);
    if (!release.changes.length) problems.push(`${name} lists no change`);
    for (const change of release.changes) {
      if (!CHANGE_KINDS.includes(change.kind)) problems.push(`${name}: "${change.kind}" is not a kind of change`);
      if (!change.text.trim()) problems.push(`${name} has an empty line`);
    }
    if (index > 0 && list[index - 1].date < release.date) problems.push(`${name} is newer than the release listed before it`);
  });
  if (new Set(list.map((release) => release.version)).size !== list.length) problems.push("a version is listed twice");
  return problems;
}

/** A release's day as the list prints it: October 2, 2026. */
export const releaseDay = (date: string): string => new Intl.DateTimeFormat("en-US", { year: "numeric", month: "long", day: "numeric", timeZone: "UTC" }).format(new Date(`${date}T00:00:00Z`));
