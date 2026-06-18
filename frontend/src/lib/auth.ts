/**
 * Auth token helpers.
 *
 * Token is stored in two places:
 *   1. localStorage  — for client-side reads (apiFetch, Zustand store)
 *   2. cookie        — for Edge middleware reads (SSR-safe, no localStorage on Edge)
 *
 * Cookie is same-site strict, NOT http-only so the browser JS can write it.
 */

const TOKEN_KEY = "auth_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string, maxAge = 86400): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  // Mirror to cookie for Edge proxy — maxAge matches JWT expires_in from backend
  document.cookie = `${TOKEN_KEY}=${token}; path=/; SameSite=Strict; max-age=${maxAge}`;
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  // Clear cookie
  document.cookie = `${TOKEN_KEY}=; path=/; SameSite=Strict; max-age=0`;
}
