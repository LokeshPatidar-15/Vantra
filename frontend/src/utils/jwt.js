// Reads the payload of a JWT. This does NOT verify the signature (only the server can);
// it only shows that anyone can read what is inside a token.
export function decodeJwtPayload(token) {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}
