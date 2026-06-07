"use client";

/**
 * Zustand auth store.
 *
 * Handles login/logout and exposes auth state to the rest of the app.
 * Token persistence is handled by the auth helpers in lib/auth.ts.
 */

import { create } from "zustand";
import { apiFetch } from "@/lib/api";
import { clearToken, getToken, setToken } from "@/lib/auth";

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

interface AuthState {
  token: string | null;
  isAuthenticated: boolean;
  /** Login with password. Throws on wrong password or network error. */
  login: (password: string) => Promise<void>;
  logout: () => void;
  /** Call once on app mount to hydrate from localStorage */
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  isAuthenticated: false,

  hydrate: () => {
    const token = getToken();
    if (token) {
      set({ token, isAuthenticated: true });
    }
  },

  login: async (password: string) => {
    const data = await apiFetch<LoginResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
      skipAuth: true,
    });
    setToken(data.access_token, data.expires_in);
    set({ token: data.access_token, isAuthenticated: true });
  },

  logout: () => {
    clearToken();
    set({ token: null, isAuthenticated: false });
  },
}));
