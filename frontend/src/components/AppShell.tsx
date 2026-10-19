import { FileText, LogOut, MessageSquarePlus, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import { api } from "../lib/api";
import type { Conversacion } from "../lib/types";

/**
 * Marco de la aplicación: barra lateral de conversaciones, cabecera y el
 * contenido de la ruta activa.
 *
 * La lista de conversaciones se refresca con un evento global en vez de con un
 * gestor de estado: el chat avisa cuando crea una conversación nueva y aquí se
 * vuelve a pedir la lista. Para dos pantallas, montar un store completo sería
 * más maquinaria de la que el problema pide.
 */
export function AppShell() {
  const { usuario, salir } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { id: conversacionActiva } = useParams();
  const [conversaciones, setConversaciones] = useState<Conversacion[]>([]);

  const cargar = useCallback(async () => {
    try {
      setConversaciones(await api.conversaciones());
    } catch {
      // Una lista vacía es un fallo tolerable: no impide chatear.
    }
  }, []);

  useEffect(() => {
    void cargar();
    const refrescar = () => void cargar();
    window.addEventListener("var:conversaciones", refrescar);
    return () => window.removeEventListener("var:conversaciones", refrescar);
  }, [cargar]);

  async function borrar(id: string, e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    try {
      await api.borrarConversacion(id);
      setConversaciones((prev) => prev.filter((c) => c.id !== id));
      if (conversacionActiva === id) navigate("/");
    } catch {
      /* si falla, la conversación sigue en la lista */
    }
  }

  const enDocumentos = location.pathname.startsWith("/documentos");

  return (
    <div className="relative z-10 grid h-full grid-cols-1 md:grid-cols-[260px_1fr]">
      {/* ── Barra lateral ────────────────────────────────────────────────── */}
      <aside className="hidden flex-col border-r border-[color:var(--line)] bg-[color:var(--pitch-deep)] md:flex">
        <div className="flex items-baseline gap-2 px-5 py-5">
          <span className="font-[family-name:var(--font-display)] text-2xl font-700 text-[color:var(--chalk)]">
            VAR
          </span>
          <span className="text-[10px] leading-none text-[color:var(--chalk-faint)]">
            agente documental
          </span>
        </div>

        <nav className="flex flex-col gap-1 px-3">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-sm px-3 py-2 text-sm transition ${
                isActive && !enDocumentos
                  ? "bg-[color:var(--turf)] text-[color:var(--chalk)]"
                  : "text-[color:var(--chalk-dim)] hover:bg-[color:var(--turf)]/60 hover:text-[color:var(--chalk)]"
              }`
            }
          >
            <MessageSquarePlus size={16} />
            Nueva conversación
          </NavLink>
          <NavLink
            to="/documentos"
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-sm px-3 py-2 text-sm transition ${
                isActive
                  ? "bg-[color:var(--turf)] text-[color:var(--chalk)]"
                  : "text-[color:var(--chalk-dim)] hover:bg-[color:var(--turf)]/60 hover:text-[color:var(--chalk)]"
              }`
            }
          >
            <FileText size={16} />
            Documentos
          </NavLink>
        </nav>

        <div className="mt-6 px-5 pb-2">
          <span className="font-[family-name:var(--font-display)] text-[11px] tracking-[0.14em] text-[color:var(--chalk-faint)] uppercase">
            Conversaciones
          </span>
        </div>

        <div className="flex-1 overflow-y-auto px-3 pb-4">
          {conversaciones.length === 0 ? (
            <p className="px-3 py-2 text-xs text-[color:var(--chalk-faint)]">
              Todavía no has preguntado nada.
            </p>
          ) : (
            <ul className="flex flex-col gap-0.5">
              <AnimatePresence initial={false}>
                {conversaciones.map((c) => (
                  <motion.li
                    key={c.id}
                    layout
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, height: 0 }}
                  >
                    <NavLink
                      to={`/conversacion/${c.id}`}
                      className={({ isActive }) =>
                        `group flex items-center gap-2 rounded-sm px-3 py-2 text-sm transition ${
                          isActive
                            ? "bg-[color:var(--turf)] text-[color:var(--chalk)]"
                            : "text-[color:var(--chalk-dim)] hover:bg-[color:var(--turf)]/60"
                        }`
                      }
                    >
                      <span className="flex-1 truncate">{c.titulo}</span>
                      <button
                        type="button"
                        onClick={(e) => borrar(c.id, e)}
                        aria-label={`Eliminar ${c.titulo}`}
                        className="shrink-0 opacity-0 transition group-hover:opacity-100 hover:text-[color:var(--foul)] focus-visible:opacity-100"
                      >
                        <Trash2 size={14} />
                      </button>
                    </NavLink>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          )}
        </div>

        <div className="border-t border-[color:var(--line)] px-5 py-4">
          <p className="truncate text-sm text-[color:var(--chalk)]">{usuario?.nombre}</p>
          <p className="mb-3 truncate text-xs text-[color:var(--chalk-faint)]">
            {usuario?.email}
          </p>
          <button
            type="button"
            onClick={() => void salir()}
            className="flex items-center gap-2 text-xs text-[color:var(--chalk-dim)] transition hover:text-[color:var(--foul)]"
          >
            <LogOut size={14} />
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* ── Contenido ────────────────────────────────────────────────────── */}
      <main className="relative min-w-0 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}

/** Avisa a la barra lateral de que la lista de conversaciones cambió. */
export function refrescarConversaciones() {
  window.dispatchEvent(new Event("var:conversaciones"));
}
