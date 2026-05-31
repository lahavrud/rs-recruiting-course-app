import { apiErrorKey } from "@/utils/apiError";

function makeAxiosError(status: number): unknown {
  return { isAxiosError: true, response: { status } };
}

describe("apiErrorKey", () => {
  it("returns tooManyRequests for 429", () => {
    expect(apiErrorKey(makeAxiosError(429))).toBe("common.errors.tooManyRequests");
  });

  it("returns forbidden for 403", () => {
    expect(apiErrorKey(makeAxiosError(403))).toBe("common.errors.forbidden");
  });

  it("returns notFound for 404", () => {
    expect(apiErrorKey(makeAxiosError(404))).toBe("common.errors.notFound");
  });

  it("returns conflict for 409", () => {
    expect(apiErrorKey(makeAxiosError(409))).toBe("common.errors.conflict");
  });

  it("returns genericError for an unmapped status", () => {
    expect(apiErrorKey(makeAxiosError(500))).toBe("common.genericError");
  });

  it("returns genericError for a non-axios error", () => {
    expect(apiErrorKey(new Error("boom"))).toBe("common.genericError");
  });

  it("override takes precedence over the default mapping", () => {
    expect(
      apiErrorKey(makeAxiosError(409), { 409: "admin.custom.conflict" }),
    ).toBe("admin.custom.conflict");
  });

  it("override handles a status that has no built-in mapping", () => {
    expect(apiErrorKey(makeAxiosError(422), { 422: "form.invalid" })).toBe("form.invalid");
  });
});
