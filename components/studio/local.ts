/** What the studio keeps in this browser besides the project: the engineer's name for the attempt log. Blocked storage is not an error. */
export const RUN_BY_KEY = "anisotropy.studio.run_by";

export function today(): string { return new Date().toISOString().slice(0, 10); }

export function remembered(key: string): string {
  try { return window.localStorage.getItem(key) ?? ""; } catch { return ""; }
}

export function remember(key: string, value: string) {
  try { window.localStorage.setItem(key, value); } catch { /* a private window or blocked storage: the name is simply not kept */ }
}
