export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

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

async function request(path, { method = "GET", body, token } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    // fetch only throws on network failure (a CORS block looks like this too)
    throw new Error(
      "Could not reach the server. Is the backend running? (A CORS problem also shows up like this: check the browser console.)"
    );
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    // response had no JSON body
  }

  // fetch does NOT throw on 4xx/5xx, so we check response.ok ourselves
  if (!response.ok) {
    throw new Error(extractErrorMessage(data, `Request failed (${response.status})`));
  }
  return data;
}

export const signup = (email, password) =>
  request("/api/auth/signup", { method: "POST", body: { email, password } });

export const login = (email, password) =>
  request("/api/auth/login", { method: "POST", body: { email, password } });

export const getMe = (token) => request("/api/auth/me", { token });
