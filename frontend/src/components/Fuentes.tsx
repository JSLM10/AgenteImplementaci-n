import { ChevronDown, FileText } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import type { Fuente } from "../lib/types";

/**
 * Los fragmentos que sustentan una respuesta.
 *
 * Es una de las seis estrategias contra las alucinaciones: el usuario puede
 * comprobar por sí mismo de dónde salió cada afirmación, en vez de tener que
 * fiarse del modelo.
 */
export function Fuentes({ fuentes }: { fuentes: Fuente[] }) {
  const [abierto, setAbierto] = useState(false);

  if (fuentes.length === 0) return null;

  return (
    <div className="mt-3 border-t border-[color:var(--line)] pt-2">
      <button
        type="button"
        onClick={() => setAbierto((v) => !v)}
        aria-expanded={abierto}
        className="flex items-center gap-1.5 font-[family-name:var(--font-display)] text-[11px] tracking-[0.12em] text-[color:var(--chalk-faint)] uppercase transition hover:text-[color:var(--chalk-dim)]"
      >
        <ChevronDown
          size={13}
          className={`transition-transform ${abierto ? "rotate-180" : ""}`}
        />
        {fuentes.length} {fuentes.length === 1 ? "fragmento" : "fragmentos"} de respaldo
      </button>

      <AnimatePresence initial={false}>
        {abierto && (
          <motion.ul
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden"
          >
            {fuentes.map((f, i) => (
              <li
                key={`${f.document_id}-${i}`}
                className="mt-2 border-l-2 border-[color:var(--signal)]/40 pl-3"
              >
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-[color:var(--chalk-faint)]">
                  <span className="inline-flex items-center gap-1 text-[color:var(--chalk-dim)]">
                    <FileText size={11} />
                    <span className="font-[family-name:var(--font-display)] tracking-wide">
                      [{i + 1}] {f.documento}
                    </span>
                  </span>
                  {f.pagina !== null && <span>página {f.pagina}</span>}
                  <span
                    className="tabular-nums"
                    title="Similitud entre la pregunta y el fragmento"
                  >
                    similitud {(f.score * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="mt-1 text-[13px] leading-relaxed text-[color:var(--chalk-dim)]">
                  {f.extracto}
                </p>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}
