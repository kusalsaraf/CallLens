/**
 * Pure auth-routing logic extracted from middleware for unit-testability.
 * Middleware delegates to these so tests don't need next/server mocks.
 */

export function needsLoginRedirect(
  pathname: string,
  hasRefreshToken: boolean
): boolean {
  return pathname.startsWith("/app") && !hasRefreshToken;
}

export function needsAppRedirect(
  pathname: string,
  hasRefreshToken: boolean
): boolean {
  return (
    (pathname === "/login" || pathname === "/signup") && hasRefreshToken
  );
}
