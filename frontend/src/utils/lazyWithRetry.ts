import { lazy, type ComponentType } from "react";

const RELOAD_FLAG = "rsr.lazy-reload";

/**
 * Drop-in replacement for `React.lazy` that survives a deploy happening
 * while the SPA is open in the user's tab.
 *
 * Vite produces hashed chunk filenames (DashboardPage-<hash>.js). Each
 * deploy invalidates those hashes — but a browser holding the old SPA in
 * memory still asks for the old filename when navigating to a lazy route,
 * gets a 404, and crashes the navigation with:
 *
 *   TypeError: error loading dynamically imported module
 *
 * Fix: catch chunk-load failures and force a single full reload, which
 * re-fetches index.html and pulls in the new chunk hashes. We gate on a
 * sessionStorage flag so a real (persistent) load failure can't loop
 * forever — the second time we just rethrow.
 */
export function lazyWithRetry<T extends ComponentType<unknown>>(
  factory: () => Promise<{ default: T }>,
) {
  return lazy(async () => {
    try {
      const mod = await factory();
      // Successful load — clear any leftover flag from a previous deploy.
      sessionStorage.removeItem(RELOAD_FLAG);
      return mod;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      const isChunkLoadError = /dynamically imported module|Failed to fetch dynamically imported|Loading chunk \d+ failed|Importing a module script failed/i.test(
        message,
      );

      if (isChunkLoadError && !sessionStorage.getItem(RELOAD_FLAG)) {
        sessionStorage.setItem(RELOAD_FLAG, "1");
        window.location.reload();
        // Block React's render path until the reload happens — never resolve.
        return await new Promise<{ default: T }>(() => {});
      }

      // Either not a chunk-load error or we've already reloaded once.
      // Re-throw so the user / Sentry can see something is actually broken.
      throw err;
    }
  });
}
