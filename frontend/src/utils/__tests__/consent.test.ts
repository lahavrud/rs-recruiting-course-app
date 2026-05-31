import { getConsent, saveConsent } from "@/utils/consent";

beforeEach(() => localStorage.clear());

describe("consent utils", () => {
  it("returns null when nothing is stored", () => {
    expect(getConsent()).toBeNull();
  });

  it("round-trips analytics=true", () => {
    saveConsent({ analytics: true });
    expect(getConsent()).toEqual({ analytics: true });
  });

  it("round-trips analytics=false", () => {
    saveConsent({ analytics: false });
    expect(getConsent()).toEqual({ analytics: false });
  });

  it("returns null for malformed JSON", () => {
    localStorage.setItem("cookie_consent", "{not valid json}");
    expect(getConsent()).toBeNull();
  });
});
