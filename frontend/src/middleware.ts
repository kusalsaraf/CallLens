import { NextResponse, type NextRequest } from "next/server";
import {
  needsAppRedirect,
  needsLoginRedirect,
} from "@/lib/middleware-utils";

export function middleware(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;
  const hasRefreshToken = request.cookies.has("refresh_token");

  if (needsLoginRedirect(pathname, hasRefreshToken)) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (needsAppRedirect(pathname, hasRefreshToken)) {
    return NextResponse.redirect(new URL("/app", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/app/:path*", "/login", "/signup"],
};
