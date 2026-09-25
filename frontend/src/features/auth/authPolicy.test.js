import { describe, expect, it } from "vitest";

import { MIN_PASSWORD_LENGTH, PASSWORD_HINT, resolveDestination } from "./authPolicy";

describe("auth policy constants", () => {
  it("states the password requirement the backend enforces", () => {
    expect(MIN_PASSWORD_LENGTH).toBe(10);
    expect(PASSWORD_HINT).toContain("10");
  });
});

describe("resolveDestination", () => {
  it("defaults to the workspace", () => {
    expect(resolveDestination(undefined)).toBe("/dashboard");
    expect(resolveDestination(null)).toBe("/dashboard");
    expect(resolveDestination({})).toBe("/dashboard");
  });

  it("honours a captured same-origin path", () => {
    expect(resolveDestination({ from: "/problems" })).toBe("/problems");
    expect(resolveDestination({ from: "/problems/two-sum?tab=hints" })).toBe("/problems/two-sum?tab=hints");
  });

  it("refuses to bounce the user back into the auth pages", () => {
    expect(resolveDestination({ from: "/login" })).toBe("/dashboard");
    expect(resolveDestination({ from: "/register" })).toBe("/dashboard");
  });

  it("refuses absolute and protocol-relative URLs", () => {
    expect(resolveDestination({ from: "https://evil.example/steal" })).toBe("/dashboard");
    expect(resolveDestination({ from: "//evil.example/steal" })).toBe("/dashboard");
  });

  it("refuses a non-string or blank value", () => {
    expect(resolveDestination({ from: 42 })).toBe("/dashboard");
    expect(resolveDestination({ from: "   " })).toBe("/dashboard");
  });
});
