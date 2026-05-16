/**
 * Suspense fallback for the lazy `LandingPage` route.
 *
 * Renders the same DOM as the static `.initial-banner` block in
 * `frontend/index.html` so the LCP element is *visually and structurally*
 * continuous from HTML-parse time through React hydration until the
 * LandingPage chunk lands. Without this, `createRoot.render()` wipes the
 * static block and React's default RouteFallback (a spinner) becomes the
 * first React-painted content — Chrome's LCP timer resets to that paint.
 *
 * The CSS for `.initial-banner` / `.initial-logo` / `.initial-wordmark` is
 * defined in `index.html`'s `<style>` block (inline, not in the bundled
 * stylesheet) so it applies before the Tailwind CSS loads.
 */
export default function LandingFallback() {
  return (
    <div className="initial-banner" role="presentation">
      <img
        className="initial-logo"
        src="/logo.svg"
        alt="RS Recruiting"
        width={112}
        height={112}
      />
      <span className="initial-wordmark">RS Recruiting</span>
    </div>
  );
}
