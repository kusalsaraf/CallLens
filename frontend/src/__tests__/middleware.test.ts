import { describe, expect, it } from "vitest";
import {
  needsAppRedirect,
  needsLoginRedirect,
} from "@/lib/middleware-utils";

describe("needsLoginRedirect", () => {
  it("redirects /app when there is no refresh token", () => {
    expect(needsLoginRedirect("/app", false)).toBe(true);
  });

  it("redirects /app/overview when there is no refresh token", () => {
    expect(needsLoginRedirect("/app/overview", false)).toBe(true);
  });

  it("does not redirect /app when there is a refresh token", () => {
    expect(needsLoginRedirect("/app", true)).toBe(false);
  });

  it("does not redirect /login", () => {
    expect(needsLoginRedirect("/login", false)).toBe(false);
  });

  it("does not redirect /", () => {
    expect(needsLoginRedirect("/", false)).toBe(false);
  });
});

describe("needsAppRedirect", () => {
  it("redirects /login to /app when authenticated", () => {
    expect(needsAppRedirect("/login", true)).toBe(true);
  });

  it("redirects /signup to /app when authenticated", () => {
    expect(needsAppRedirect("/signup", true)).toBe(true);
  });

  it("does not redirect /login when unauthenticated", () => {
    expect(needsAppRedirect("/login", false)).toBe(false);
  });

  it("does not redirect /app", () => {
    expect(needsAppRedirect("/app", true)).toBe(false);
  });
});
