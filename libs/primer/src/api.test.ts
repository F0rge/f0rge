import { describe, expect, it } from "vitest";
import { apiFailure } from "./api";
import { publicFieldErrors } from "./validation";
describe("public API error handling", () => {
  it("keeps field errors, denied and conflict meanings without debugging details", () => {
    const error = apiFailure(422, {
      error: {
        code: "validation_failed",
        message: "Some fields are invalid.",
        error_id: "opaque-id",
        field_errors: [
          { field: "price", code: "invalid", message: "Invalid price." },
        ],
        debug: "private",
      },
    });
    expect(error.fields[0]?.field).toBe("price");
    expect(error.message).not.toContain("private");
    expect(error.errorId).toBe("opaque-id");
    expect(apiFailure(403, {}).denied).toBe(true);
    expect(apiFailure(409, {}).conflict).toBe(true);
  });
  it("does not show raw failed-service or malformed response data", () => {
    expect(
      apiFailure(500, { detail: "password=private" }).message,
    ).not.toContain("private");
    expect(apiFailure(500, null).fields).toEqual([]);
  });
  it("maps only public TanStack field validation messages", () => {
    expect(
      publicFieldErrors([
        "Required",
        { message: "Invalid" },
        null,
        42,
        { debug: "private" },
      ]),
    ).toEqual(["Required", "Invalid"]);
  });
});
