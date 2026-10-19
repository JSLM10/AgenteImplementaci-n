import { motion } from "motion/react";

/**
 * El camino que recorrió la pregunta por el grafo de LangGraph.
 *
 * No es decoración: durante la sustentación permite enseñar, pregunta a
 * pregunta, que el agente pasó por el nodo de recuperación y por el de
 * evaluación de contexto antes de contestar, y que una pregunta rechazada
 * nunca llegó al nodo de generación.
 */
export function TrazaGrafo({ traza, duracionMs }: { traza: string[]; duracionMs?: number }) {
  if (traza.length === 0) return null;

  // Los nodos omitidos se anotan en la traza como "reformular(omitido)".
  const pasos = traza.map((paso) => {
    const marca = paso.match(/^(.+?)\((.+)\)$/);
    return marca ? { nombre: marca[1], nota: marca[2] } : { nombre: paso, nota: null };
  });

  return (
    <div className="mt-2 flex flex-wrap items-center gap-x-1.5 gap-y-1 font-[family-name:var(--font-display)] text-[10px] tracking-[0.1em] text-[color:var(--chalk-faint)] uppercase">
      {pasos.map((paso, i) => (
        <motion.span
          key={`${paso.nombre}-${i}`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: i * 0.04 }}
          className="flex items-center gap-1.5"
        >
          {i > 0 && <span className="text-[color:var(--chalk-faint)]/50">·</span>}
          <span className={paso.nota ? "opacity-45" : "text-[color:var(--chalk-dim)]"}>
            {paso.nombre}
          </span>
        </motion.span>
      ))}
      {duracionMs !== undefined && (
        <span className="ml-1 tabular-nums opacity-60">{(duracionMs / 1000).toFixed(1)}s</span>
      )}
    </div>
  );
}
