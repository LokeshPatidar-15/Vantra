export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

// An Error that also remembers the HTTP status, so callers can react to 401 etc.
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status; // 0 means the request never reached the server
  }
}

// FastAPI sends errors as {"detail": "text"} or, for validation (422),
// {"detail": [{"loc": [...], "msg": "..."}, ...]}. Turn both into one string.
function extractErrorMessage(data, fallback) {
  if (!data || data.detail === undefined) return fallback;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => {
        const field = item.loc?.[item.loc.length - 1];
        return field ? `${field}: ${item.msg}` : item.msg;
      })
      .join(". ");
  }
  return fallback;
}

export async function request(path, { method = "GET", body, token } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      credentials: "include", // lets the browser send and store the refresh-token cookie
    });
  } catch {
    // fetch only throws on network failure (a CORS block looks like this too)
    throw new ApiError(
      "Could not reach the server. Is the backend running? (A CORS problem also shows up like this: check the browser console.)",
      0
    );
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    // response had no JSON body (e.g. 204 No Content)
  }

  // fetch does NOT throw on 4xx/5xx, so we check response.ok ourselves
  if (!response.ok) {
    throw new ApiError(extractErrorMessage(data, `Request failed (${response.status})`), response.status);
  }
  return data;
}

export const signup = (email, password) =>
  request("/api/auth/signup", { method: "POST", body: { email, password } });

export const login = (email, password) =>
  request("/api/auth/login", { method: "POST", body: { email, password } });

export const getMe = (token) => request("/api/auth/me", { token });

export const refreshSession = () => request("/api/auth/refresh", { method: "POST" });

export const logoutRequest = () => request("/api/auth/logout", { method: "POST" });
