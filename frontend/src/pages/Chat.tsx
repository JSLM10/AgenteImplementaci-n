import { AlertTriangle, ArrowUp, CornerDownLeft } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { refrescarConversaciones } from "../components/AppShell";
import { Fuentes } from "../components/Fuentes";
import { TrazaGrafo } from "../components/TrazaGrafo";
import MorphOrb from "../components/ui/ai-thinking-orb-and-input";
import { ApiError, api } from "../lib/api";
import type { Mensaje, Respuesta } from "../lib/types";

interface Burbuja extends Mensaje {
  traza?: string[];
  duracion_ms?: number;
}

function nuevaBurbuja(
  rol: "usuario" | "agente",
  contenido: string,
  extra: Partial<Burbuja> = {},
): Burbuja {
  return {
    id: crypto.randomUUID(),
    rol,
    contenido,
    rechazada: false,
    fuentes: null,
    creado_en: new Date().toISOString(),
    ...extra,
  };
}

export function Chat() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [mensajes, setMensajes] = useState<Burbuja[]>([]);
  const [conversacionId, setConversacionId] = useState<string | null>(id ?? null);
  const [cargando, setCargando] = useState(Boolean(id));
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [texto, setTexto] = useState("");

  // El orbe se muestra mientras la conversación esté vacía: es la entrada al
  // chat, no el chat entero.
  const [mostrarOrbe, setMostrarOrbe] = useState(!id);
  const [orbeRespondio, setOrbeRespondio] = useState(false);

  const finRef = useRef<HTMLDivElement>(null);
  const conversacionIdRef = useRef<string | null>(id ?? null);
  conversacionIdRef.current = conversacionId;

  // Cambiar de conversación reinicia la pantalla por completo.
  useEffect(() => {
    setConversacionId(id ?? null);
    setError(null);
    setOrbeRespondio(false);
    setMostrarOrbe(!id);

    if (!id) {
      setMensajes([]);
      setCargando(false);
      return;
    }

    let vigente = true;
    setCargando(true);
    (async () => {
      try {
        const detalle = await api.conversacion(id);
        if (vigente) setMensajes(detalle.mensajes);
      } catch (err) {
        if (vigente) {
          setError(
            err instanceof ApiError ? err.message : "No se pudo cargar la conversación.",
          );
        }
      } finally {
        if (vigente) setCargando(false);
      }
    })();

    return () => {
      vigente = false;
    };
  }, [id]);

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [mensajes, enviando]);

  /** Envía la pregunta y añade las dos burbujas. Devuelve la respuesta cruda. */
  const preguntar = useCallback(
    async (pregunta: string): Promise<Respuesta> => {
      const respuesta = await api.preguntar(pregunta, conversacionIdRef.current);

      setMensajes((prev) => [
        ...prev,
        nuevaBurbuja("usuario", pregunta),
        nuevaBurbuja("agente", respuesta.respuesta, {
          rechazada: respuesta.rechazada,
          fuentes: respuesta.fuentes,
          traza: respuesta.traza,
          duracion_ms: respuesta.duracion_ms,
        }),
      ]);

      // La primera pregunta crea la conversación en el servidor.
      if (!conversacionIdRef.current) {
        conversacionIdRef.current = respuesta.conversation_id;
        setConversacionId(respuesta.conversation_id);
        refrescarConversaciones();
      }

      return respuesta;
    },
    [],
  );

  /** Entrada del orbe: devuelve solo el texto, que es lo que él sabe animar. */
  const enviarDesdeOrbe = useCallback(
    async (pregunta: string): Promise<string> => {
      try {
        const respuesta = await preguntar(pregunta);
        setOrbeRespondio(true);
        return respuesta.respuesta;
      } catch (err) {
        const mensaje =
          err instanceof ApiError
            ? err.message
            : "No se pudo contactar con el agente. Inténtalo de nuevo.";
        setError(mensaje);
        setOrbeRespondio(true);
        return mensaje;
      }
    },
    [preguntar],
  );

  /** Entrada de la barra inferior, para las preguntas siguientes. */
  async function enviarDesdeBarra(e: React.FormEvent) {
    e.preventDefault();
    const pregunta = texto.trim();
    if (!pregunta || enviando) return;

    setTexto("");
    setError(null);
    setEnviando(true);
    try {
      await preguntar(pregunta);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "No se pudo contactar con el agente. Inténtalo de nuevo.",
      );
    } finally {
      setEnviando(false);
    }
  }

  function entrarAlChat() {
    setMostrarOrbe(false);
    if (conversacionId && !id) navigate(`/conversacion/${conversacionId}`, { replace: true });
  }

  return (
    <div className="flex h-full flex-col">
      {/* ── Hilo ─────────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-[760px] flex-col gap-6 px-6 py-8">
          {cargando && (
            <p className="text-sm text-[color:var(--chalk-faint)]">Cargando conversación…</p>
          )}

          {mensajes.map((m) =>
            m.rol === "usuario" ? (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className="self-end max-w-[85%] rounded-sm bg-[color:var(--turf)] px-4 py-2.5 text-[15px] text-[color:var(--chalk)]"
              >
                {m.contenido}
              </motion.div>
            ) : (
              <motion.div
                key={m.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
                className={
                  m.rechazada
                    ? "border-l-2 border-[color:var(--caution)] pl-4"
                    : "border-l-2 border-[color:var(--signal)]/30 pl-4"
                }
              >
                <div className="mb-1 flex items-center gap-1.5 font-[family-name:var(--font-display)] text-[11px] tracking-[0.14em] uppercase">
                  {m.rechazada ? (
                    <span className="flex items-center gap-1.5 text-[color:var(--caution)]">
                      <AlertTriangle size={12} />
                      Sin respaldo suficiente
                    </span>
                  ) : (
                    <span className="text-[color:var(--chalk-faint)]">VAR</span>
                  )}
                </div>

                <p className="text-[15px] leading-relaxed whitespace-pre-wrap text-[color:var(--chalk)]">
                  {m.contenido}
                </p>

                {m.fuentes && m.fuentes.length > 0 && <Fuentes fuentes={m.fuentes} />}
                {m.traza && <TrazaGrafo traza={m.traza} duracionMs={m.duracion_ms} />}
              </motion.div>
            ),
          )}

          {enviando && (
            <div className="flex items-center gap-2 pl-4 text-sm text-[color:var(--chalk-dim)]">
              <span className="flex gap-1">
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className="h-1.5 w-1.5 rounded-full bg-[color:var(--signal)]"
                    animate={{ opacity: [0.25, 1, 0.25] }}
                    transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.16 }}
                  />
                ))}
              </span>
              <span className="font-[family-name:var(--font-display)] text-xs tracking-[0.12em] uppercase">
                Revisando la base de conocimiento
              </span>
            </div>
          )}

          <AnimatePresence>
            {error && !mostrarOrbe && (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                role="alert"
                className="border-l-2 border-[color:var(--foul)] bg-[rgba(229,72,77,0.08)] py-2 pl-4 text-sm text-[color:var(--chalk)]"
              >
                {error}
              </motion.p>
            )}
          </AnimatePresence>

          <div ref={finRef} />
        </div>
      </div>

      {/* ── Barra de entrada ─────────────────────────────────────────────── */}
      {!mostrarOrbe && (
        <div className="border-t border-[color:var(--line)] bg-[color:var(--pitch-deep)]/70 px-6 py-4">
          <form onSubmit={enviarDesdeBarra} className="mx-auto flex max-w-[760px] gap-2">
            <input
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              disabled={enviando}
              placeholder="Pregunta sobre fútbol o sobre tus documentos…"
              aria-label="Escribe tu pregunta"
              className="h-11 flex-1 rounded-sm border border-[color:var(--line-strong)] bg-[color:var(--turf)] px-3 text-[15px] text-[color:var(--chalk)] transition placeholder:text-[color:var(--chalk-faint)] focus:border-[color:var(--signal)] focus:outline-none disabled:opacity-60"
            />
            <button
              type="submit"
              disabled={enviando || !texto.trim()}
              aria-label="Enviar pregunta"
              className="grid h-11 w-11 place-items-center rounded-sm bg-[color:var(--signal)] text-[#04120c] transition hover:brightness-110 disabled:cursor-not-allowed disabled:bg-[color:var(--turf-hi)] disabled:text-[color:var(--chalk-faint)]"
            >
              <ArrowUp size={18} />
            </button>
          </form>
        </div>
      )}

      {/* ── Orbe de bienvenida ───────────────────────────────────────────── */}
      {mostrarOrbe && (
        <div className="orbe-bienvenida">
          <MorphOrb onSubmit={enviarDesdeOrbe} minThinkMs={2200} />
          <AnimatePresence>
            {orbeRespondio && (
              <motion.button
                type="button"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
                onClick={entrarAlChat}
                className="fixed left-1/2 z-40 flex -translate-x-1/2 items-center gap-2 rounded-sm border border-[color:var(--line-strong)] bg-[color:var(--turf)] px-4 py-2 font-[family-name:var(--font-display)] text-xs tracking-[0.12em] text-[color:var(--chalk-dim)] uppercase transition hover:border-[color:var(--signal)] hover:text-[color:var(--chalk)]"
                style={{ top: "calc(46% + 96px)" }}
              >
                <CornerDownLeft size={13} />
                Continuar en el chat
              </motion.button>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
