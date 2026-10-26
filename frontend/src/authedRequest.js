import { request } from "./api";
import { useAuthStore } from "./store/authStore";
import { decodeJwtPayload } from "./utils/jwt";

// Use this for every API call that needs a logged-in user.
export async function authedRequest(path, options = {}) {
  const { accessToken, refreshAccessToken, expireSession } = useAuthStore.getState();

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
    if (err.status === 401) await expireSession(); // refresh failed too: the session is over
    throw err;
  }
}

// For things that are not plain requests (like a WebSocket): a token that is valid for at least 30 more seconds.
export async function getFreshAccessToken() {
  const { accessToken, refreshAccessToken } = useAuthStore.getState();
  const payload = accessToken ? decodeJwtPayload(accessToken) : null;
  const expiresSoon = !payload || payload.exp * 1000 < Date.now() + 30_000;
  return expiresSoon ? refreshAccessToken() : accessToken;
}
