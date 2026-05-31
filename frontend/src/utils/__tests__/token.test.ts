import { decodeToken } from "@/utils/token";

const ACCESS_TOKEN_KEY = "access_token";

function makeJwt(payload: Record<string, unknown>): string {
  const toBase64Url = (obj: unknown) =>
    btoa(JSON.stringify(obj))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=/g, "");
  return `${toBase64Url({ alg: "HS256", typ: "JWT" })}.${toBase64Url(payload)}.fakesig`;
}

const VALID_PAYLOAD = {
  sub: "user-1",
  email: "test@example.com",
  role: "ADMIN",
  exp: Math.floor(Date.now() / 1000) + 3600,
};

beforeEach(() => localStorage.clear());

describe("decodeToken", () => {
  it("returns the decoded payload for a valid token", () => {
    const token = makeJwt(VALID_PAYLOAD);
    localStorage.setItem(ACCESS_TOKEN_KEY, token);

    const result = decodeToken(token);

    expect(result).toMatchObject({
      sub: "user-1",
      email: "test@example.com",
      role: "ADMIN",
    });
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBe(token);
  });

  it("returns null and clears localStorage for an expired token", () => {
    const expiredToken = makeJwt({ ...VALID_PAYLOAD, exp: Math.floor(Date.now() / 1000) - 1 });
    localStorage.setItem(ACCESS_TOKEN_KEY, expiredToken);

    const result = decodeToken(expiredToken);

    expect(result).toBeNull();
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
  });

  it("returns null and clears localStorage for a malformed JWT", () => {
    localStorage.setItem(ACCESS_TOKEN_KEY, "not.a.jwt");

    const result = decodeToken("not.a.jwt");

    expect(result).toBeNull();
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
  });

  it("returns null and clears localStorage when exp is missing", () => {
    const noExp = { sub: VALID_PAYLOAD.sub, email: VALID_PAYLOAD.email, role: VALID_PAYLOAD.role };
    const token = makeJwt(noExp);
    localStorage.setItem(ACCESS_TOKEN_KEY, token);

    const result = decodeToken(token);

    expect(result).toBeNull();
    expect(localStorage.getItem(ACCESS_TOKEN_KEY)).toBeNull();
  });
});
