"use client";

import { apiFetch, tokenStore } from "./client";

export interface UserOut {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface SignupRequest {
  email: string;
  password: string;
  name: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export async function apiSignup(data: SignupRequest): Promise<TokenResponse> {
  const result = await apiFetch<TokenResponse>("/api/v1/auth/signup", {
    method: "POST",
    body: JSON.stringify(data),
  });
  tokenStore.set(result.access_token);
  return result;
}

export async function apiLogin(data: LoginRequest): Promise<TokenResponse> {
  const result = await apiFetch<TokenResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  });
  tokenStore.set(result.access_token);
  return result;
}

/** Silently attempts to exchange the httpOnly refresh cookie for a new token. */
export async function apiRefresh(): Promise<TokenResponse | null> {
  try {
    const resp = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      credentials: "include",
    });
    if (!resp.ok) return null;
    const data = (await resp.json()) as TokenResponse;
    tokenStore.set(data.access_token);
    return data;
  } catch {
    return null;
  }
}

export async function apiGetMe(): Promise<UserOut> {
  return apiFetch<UserOut>("/api/v1/auth/me");
}

export async function apiLogout(): Promise<void> {
  await fetch("/api/v1/auth/logout", {
    method: "POST",
    credentials: "include",
  });
  tokenStore.set(null);
}
