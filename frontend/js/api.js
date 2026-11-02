// =========================================================================
// api.js · Cómo el frontend habla con el backend.
//
// Todas las pantallas usan la función api() en vez de fetch() directo.
// Así, en UN solo lugar resolvemos: agregar el token, convertir JSON,
// mostrar errores entendibles y mandar al login si la sesión venció.
// =========================================================================

const TOKEN_KEY = "vb-token";

export const auth = {
  get token() { return localStorage.getItem(TOKEN_KEY); },
  save(token) { localStorage.setItem(TOKEN_KEY, token); },
  clear() { localStorage.removeItem(TOKEN_KEY); },
  get loggedIn() { return Boolean(this.token); },
};

// Error con el mensaje que mostramos al usuario
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// FastAPI devuelve los errores de validación (422) como una lista técnica.
// Esta función la convierte en un mensaje legible.
function readableError(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0];
    const field = first.loc?.at(-1);
    const msg = (first.msg || "").replace(/^Value error, /, "");
    return field && !["body", "__root__"].includes(field) ? `${field}: ${msg}` : msg;
  }
  return "Algo salió mal. Probá de nuevo.";
}

/**
 * Hace un pedido a la API.
 *   api("/api/expenses")                          -> GET
 *   api("/api/expenses", { method: "POST", body: {...} })
 *   api("/api/auth/login", { method: "POST", form: {...} })  (formulario)
 */
export async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;

  let payload;
  if (form) {
    payload = new URLSearchParams(form);  // formato de formulario (lo pide el login OAuth2)
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(path, { method, headers, body: payload });
  } catch {
    throw new ApiError("No hay conexión con el servidor.", 0);
  }

  // Sesión vencida o inválida: volvemos al login (salvo que ya estemos ahí)
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    auth.clear();
    location.href = `/login.html?next=${encodeURIComponent(location.pathname)}`;
    throw new ApiError("Tu sesión venció.", 401);
  }

  if (res.status === 204) return null;  // borrado OK, sin contenido
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(readableError(data?.detail), res.status);
  return data;
}

// Si no hay sesión, manda al login. Se llama al principio de cada pantalla privada.
export function requireLogin() {
  if (!auth.loggedIn) {
    location.replace(`/login.html?next=${encodeURIComponent(location.pathname)}`);
    return false;
  }
  return true;
}
