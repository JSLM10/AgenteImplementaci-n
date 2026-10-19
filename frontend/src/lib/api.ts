/**
 * Cliente de la API.
 *
 * Centraliza tres cosas que si se dispersan acaban mal: la URL base, el token
 * de acceso y la renovación automática cuando caduca. Ninguna pantalla hace
 * fetch por su cuenta.
 */

import type {
  Conversacion,
  ConversacionDetalle,
  Documento,
  Respuesta,
  TokenResponse,
  Usuario,
} from "./types";

const BASE_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const CLAVE_ACCESS = "var.access_token";
const CLAVE_REFRESH = "var.refresh_token";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const tokens = {
  get access() {
    return localStorage.getItem(CLAVE_ACCESS);
  },
  get refresh() {
    return localStorage.getItem(CLAVE_REFRESH);
  },
  guardar(data: TokenResponse) {
    localStorage.setItem(CLAVE_ACCESS, data.access_token);
    localStorage.setItem(CLAVE_REFRESH, data.refresh_token);
  },
  limpiar() {
    localStorage.removeItem(CLAVE_ACCESS);
    localStorage.removeItem(CLAVE_REFRESH);
  },
};

/** Se dispara cuando la sesión ya no es recuperable, para devolver al login. */
let alCaducarSesion: (() => void) | null = null;
export function registrarCaducidadDeSesion(cb: () => void) {
  alCaducarSesion = cb;
}

async function leerError(res: Response): Promise<string> {
  try {
    const cuerpo = await res.json();
    if (typeof cuerpo?.detail === "string") return cuerpo.detail;
    // Errores de validación: el backend devuelve una lista de campos.
    if (Array.isArray(cuerpo?.errores) && cuerpo.errores.length > 0) {
      return cuerpo.errores.map((e: { mensaje: string }) => e.mensaje).join(". ");
    }
    if (typeof cuerpo?.detail === "object") return JSON.stringify(cuerpo.detail);
  } catch {
    /* la respuesta no era JSON */
  }
  return `Error ${res.status}`;
}

/** Una sola renovación en vuelo aunque varias peticiones fallen a la vez. */
let renovacionEnCurso: Promise<boolean> | null = null;

async function renovarToken(): Promise<boolean> {
  const refresh = tokens.refresh;
  if (!refresh) return false;

  if (!renovacionEnCurso) {
    renovacionEnCurso = (async () => {
      try {
        const res = await fetch(`${BASE_URL}/api/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!res.ok) return false;
        tokens.guardar((await res.json()) as TokenResponse);
        return true;
      } catch {
        return false;
      } finally {
        renovacionEnCurso = null;
      }
    })();
  }
  return renovacionEnCurso;
}

interface Opciones {
  method?: string;
  body?: unknown;
  /** Para subida de archivos: el navegador pone su propio Content-Type. */
  formData?: FormData;
  reintentar?: boolean;
}

async function peticion<T>(ruta: string, opciones: Opciones = {}): Promise<T> {
  const { method = "GET", body, formData, reintentar = true } = opciones;

  const headers: Record<string, string> = {};
  const access = tokens.access;
  if (access) headers.Authorization = `Bearer ${access}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${ruta}`, {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
    });
  } catch {
    throw new ApiError(
      "No se pudo conectar con el servidor. Comprueba que el backend esté en marcha.",
      0,
    );
  }

  if (res.status === 401 && reintentar && tokens.refresh) {
    if (await renovarToken()) {
      return peticion<T>(ruta, { ...opciones, reintentar: false });
    }
    tokens.limpiar();
    alCaducarSesion?.();
    throw new ApiError("La sesión expiró. Vuelve a entrar.", 401);
  }

  if (!res.ok) {
    throw new ApiError(await leerError(res), res.status);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // ─── Autenticación ───────────────────────────────────────────────────────
  registrar: (datos: { email: string; nombre: string; password: string }) =>
    peticion<TokenResponse>("/api/auth/register", { method: "POST", body: datos }),

  iniciarSesion: (datos: { email: string; password: string }) =>
    peticion<TokenResponse>("/api/auth/login", { method: "POST", body: datos }),

  yo: () => peticion<Usuario>("/api/auth/me"),

  cerrarSesion: () => peticion<{ mensaje: string }>("/api/auth/logout", { method: "POST" }),

  // ─── Chat ────────────────────────────────────────────────────────────────
  preguntar: (pregunta: string, conversationId: string | null) =>
    peticion<Respuesta>("/api/chat", {
      method: "POST",
      body: { pregunta, conversation_id: conversationId },
    }),

  conversaciones: () => peticion<Conversacion[]>("/api/conversations"),

  conversacion: (id: string) => peticion<ConversacionDetalle>(`/api/conversations/${id}`),

  borrarConversacion: (id: string) =>
    peticion<{ mensaje: string }>(`/api/conversations/${id}`, { method: "DELETE" }),

  // ─── Documentos ──────────────────────────────────────────────────────────
  documentos: () => peticion<Documento[]>("/api/documents"),

  documento: (id: string) => peticion<Documento>(`/api/documents/${id}`),

  subirDocumento: (archivo: File) => {
    const fd = new FormData();
    fd.append("archivo", archivo);
    return peticion<{ documento: Documento; mensaje: string }>("/api/documents", {
      method: "POST",
      formData: fd,
    });
  },

  borrarDocumento: (id: string) =>
    peticion<{ mensaje: string }>(`/api/documents/${id}`, { method: "DELETE" }),
};
