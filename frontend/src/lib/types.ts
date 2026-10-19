export interface Usuario {
  id: string;
  email: string;
  nombre: string;
  creado_en: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_at: string;
  usuario: Usuario;
}

export interface Fuente {
  documento: string;
  document_id: string | null;
  pagina: number | null;
  score: number;
  extracto: string;
}

export interface Respuesta {
  conversation_id: string;
  respuesta: string;
  /** El agente se negó a responder por falta de contexto suficiente. */
  rechazada: boolean;
  fuentes: Fuente[];
  /** Nodos que recorrió el grafo de LangGraph para esta pregunta. */
  traza: string[];
  duracion_ms: number;
}

export interface Mensaje {
  id: string;
  rol: "usuario" | "agente";
  contenido: string;
  rechazada: boolean;
  fuentes: Fuente[] | null;
  creado_en: string;
}

export interface Conversacion {
  id: string;
  titulo: string;
  creado_en: string;
  actualizado_en: string;
}

export interface ConversacionDetalle extends Conversacion {
  mensajes: Mensaje[];
}

export type EstadoDocumento = "PROCESANDO" | "LISTO" | "ERROR";

export interface Documento {
  id: string;
  nombre_archivo: string;
  tipo_mime: string;
  tamano_bytes: number;
  estado: EstadoDocumento;
  error: string | null;
  num_fragmentos: number;
  es_publico: boolean;
  creado_en: string;
}
