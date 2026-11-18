/** Keeps a page's script errors, as `page.on("pageerror", pageErrors(errors))`, leaving out one that is WebKit's alone (ADR-0114).
 * WebKit raises a fetch that never completed as a page error, "... due to access control checks": a request to the API, which the
 * site's specs run without (playwright.site.config.ts), and the site's own prefetches cut off when the spec goes to the next page.
 * Chromium and Firefox put the same events on the console only, so in them the page error stays what it is: a script that threw. */
export const pageErrors = (errors: string[], where?: () => string) => (error: Error) => {
  if (!/ due to access control checks\.?$/.test(error.message)) errors.push(where ? `${where()}: ${error.message}` : error.message);
};
