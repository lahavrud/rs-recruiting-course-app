import { useEffect } from "react";

/**
 * Sets `document.title` and focuses the main page heading on mount.
 *
 * Pages should render an `<h1>` (or any element) with `data-page-heading`
 * so screen readers and keyboard users land on the new page's heading
 * after navigation. The element is briefly given `tabIndex={-1}` so it can
 * receive focus without becoming a keyboard tab stop.
 */
export function usePageTitle(title: string): void {
  useEffect(() => {
    const previous = document.title;
    document.title = title ? `${title} — RS Recruiting` : "RS Recruiting";

    const heading = document.querySelector<HTMLElement>("[data-page-heading]");
    if (heading) {
      const previousTabIndex = heading.tabIndex;
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
      // Restore tabIndex on next tick so the element doesn't stay focusable
      // for keyboard tab order.
      const id = window.setTimeout(() => {
        heading.tabIndex = previousTabIndex;
      }, 0);
      return () => {
        window.clearTimeout(id);
        document.title = previous;
      };
    }

    return () => {
      document.title = previous;
    };
  }, [title]);
}
