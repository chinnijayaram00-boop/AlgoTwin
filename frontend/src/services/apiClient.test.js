import { describe, expect, it } from "vitest";

import { describeApiError } from "./apiClient";

describe("describeApiError", () => {
  it("passes a plain string detail through", () => {
    expect(describeApiError("Invalid email or password.", "fallback")).toBe("Invalid email or password.");
  });

  it("trims a string detail", () => {
    expect(describeApiError("  spaced  ", "fallback")).toBe("spaced");
  });

  it("flattens a FastAPI validation array instead of stringifying it", () => {
    const detail = [
      { loc: ["body", "email"], msg: "value is not a valid email address", type: "value_error" },
      { loc: ["body", "password"], msg: "String should have at least 10 characters", type: "string_too_short" },
    ];

    const message = describeApiError(detail, "fallback");

    expect(message).not.toContain("[object Object]");
    expect(message).toBe(
      "email: value is not a valid email address password: String should have at least 10 characters",
    );
  });

  it("handles a single-entry validation array", () => {
    expect(describeApiError([{ loc: ["body", "name"], msg: "Name is required." }], "fallback")).toBe(
      "name: Name is required.",
    );
  });

  it("keeps a message that has no field location", () => {
    expect(describeApiError([{ loc: ["body"], msg: "Bad request" }], "fallback")).toBe("Bad request");
  });

  it("falls back for an empty detail", () => {
    expect(describeApiError("", "The API request failed.")).toBe("The API request failed.");
    expect(describeApiError(null, "The API request failed.")).toBe("The API request failed.");
    expect(describeApiError([], "The API request failed.")).toBe("The API request failed.");
  });

  it("falls back for a single object detail", () => {
    expect(describeApiError({ msg: "Database is not ready." }, "fallback")).toBe("Database is not ready.");
  });
});
