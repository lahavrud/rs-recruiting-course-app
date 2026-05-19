export type ConsentChoices = { analytics: boolean };

const KEY = "cookie_consent";

export function getConsent(): ConsentChoices | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as ConsentChoices) : null;
  } catch {
    return null;
  }
}

export function saveConsent(choices: ConsentChoices): void {
  localStorage.setItem(KEY, JSON.stringify(choices));
}

export function applyGtmConsent(analytics: boolean): void {
  const gtag = (window as unknown as { gtag?: (...args: unknown[]) => void }).gtag;
  if (typeof gtag === "function") {
    gtag("consent", "update", {
      analytics_storage: analytics ? "granted" : "denied",
    });
  }
}
