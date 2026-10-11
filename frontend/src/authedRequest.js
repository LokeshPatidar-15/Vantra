import { request } from "./api";
import { useAuthStore } from "./store/authStore";

// Use this for every API call that needs a logged-in user.
export async function authedRequest(path, options = {}) {
  const { accessToken, refreshAccessToken, logout } = useAuthStore.getState();

  try {
    return await request(path, { ...options, token: accessToken });
  } catch (err) {
    if (err.status !== 401) throw err;
  }

  // 401: the access token expired (or is invalid). Refresh once, then retry once.
  try {
    const newToken = await refreshAccessToken();
    return await request(path, { ...options, token: newToken });
  } catch (err) {
    if (err.status === 401) await logout(); // refresh failed too: the session is over
    throw err;
  }
}
