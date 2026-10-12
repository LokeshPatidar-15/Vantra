import { create } from "zustand";

import { getMe, login as loginRequest, logoutRequest, refreshSession } from "../api";

// While one refresh request is running, everyone who needs a new token
// waits for that same request instead of starting their own.
let refreshPromise = null;

export const useAuthStore = create((set, get) => ({
  accessToken: null, // lives only in memory, never in localStorage
  user: null,
  status: "loading", // "loading" | "authenticated" | "unauthenticated"
  sessionExpired: false, // true when a logged-in session ended because refresh failed

  refreshAccessToken: () => {
    if (!refreshPromise) {
      refreshPromise = refreshSession()
        .then(({ access_token }) => {
          set({ accessToken: access_token });
          return access_token;
        })
        .finally(() => {
          refreshPromise = null;
        });
    }
    return refreshPromise;
  },

  login: async (email, password) => {
    const { access_token } = await loginRequest(email, password);
    const user = await getMe(access_token);
    set({ accessToken: access_token, user, status: "authenticated", sessionExpired: false });
  },

  // Runs once when the app starts: if the refresh cookie is still valid, log the user back in.
  restoreSession: async () => {
    try {
      const accessToken = await get().refreshAccessToken();
      const user = await getMe(accessToken);
      set({ user, status: "authenticated" });
    } catch {
      set({ accessToken: null, user: null, status: "unauthenticated" });
    }
  },

  // The user clicked "Log out".
  logout: async () => {
    try {
      await logoutRequest();
    } catch {
      // even if the call fails, clear the local state
    }
    set({ accessToken: null, user: null, status: "unauthenticated", sessionExpired: false });
  },

  // The session died on its own (refresh failed): same cleanup, but tell the user why.
  expireSession: async () => {
    try {
      await logoutRequest();
    } catch {
      // ignore
    }
    set({ accessToken: null, user: null, status: "unauthenticated", sessionExpired: true });
  },
}));
