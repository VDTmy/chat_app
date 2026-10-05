import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "../types";
import { useChatStore } from "./chatStore";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
}

/** Fetches the real user profile from /auth/me using a given access token */
async function fetchUserProfile(accessToken: string): Promise<User> {
  const res = await fetch(`${API_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) {
    throw new Error("Failed to fetch user profile");
  }
  return res.json() as Promise<User>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,

      login: async (email, password) => {
        const res = await fetch(`${API_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        const data = (await res.json()) as {
          access_token: string;
          refresh_token: string;
          token_type: string;
          detail?: string | { msg: string }[];
        };

        if (!res.ok) {
          const detail = data.detail;
          throw new Error(
            typeof detail === "string"
              ? detail
              : Array.isArray(detail)
              ? detail.map((d) => d.msg).join(", ")
              : "Đăng nhập thất bại"
          );
        }

        // Fetch real user profile (contains UUID, avatar_url, etc.)
        const user = await fetchUserProfile(data.access_token);

        set({
          user,
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          isAuthenticated: true,
        });
      },

      register: async (email, username, password) => {
        const res = await fetch(`${API_URL}/auth/register`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, username, password }),
        });

        const data = (await res.json()) as {
          access_token: string;
          refresh_token: string;
          token_type: string;
          detail?: string | { msg: string }[];
        };

        if (!res.ok) {
          const detail = data.detail;
          throw new Error(
            typeof detail === "string"
              ? detail
              : Array.isArray(detail)
              ? detail.map((d) => d.msg).join(", ")
              : "Đăng ký thất bại"
          );
        }

        // Fetch real user profile with correct UUID
        const user = await fetchUserProfile(data.access_token);

        set({
          user,
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          isAuthenticated: true,
        });
      },

      logout: () => {
        // Clear all chat state first so stale data isn't shown on re-login
        useChatStore.getState().resetChat();
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        });
      },

      setTokens: (accessToken, refreshToken) => {
        set({ accessToken, refreshToken });
      },
    }),
    {
      name: "auth-storage",
    }
  )
);
