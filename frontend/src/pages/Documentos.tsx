import { FileText, Loader2, Lock, Trash2, Upload } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api } from "../lib/api";
import type { Documento } from "../lib/types";

const FORMATOS = ".pdf,.txt,.md,.csv,.docx";

function tamanoLegible(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function Documentos() {
  const [documentos, setDocumentos] = useState<Documento[]>([]);
  const [cargando, setCargando] = useState(true);
  const [subiendo, setSubiendo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [arrastrando, setArrastrando] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const cargar = useCallback(async () => {
    try {
      setDocumentos(await api.documentos());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo cargar la lista.");
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  // Mientras haya documentos procesándose, se consulta el estado cada 2 s.
  // El procesamiento ocurre en segundo plano en el servidor, así que la lista
  // tiene que enterarse sola de cuándo termina.
  useEffect(() => {
    const hayPendientes = documentos.some((d) => d.estado === "PROCESANDO");
    if (!hayPendientes) return;

    const temporizador = window.setInterval(() => void cargar(), 2000);
    return () => window.clearInterval(temporizador);
  }, [documentos, cargar]);

  async function subir(archivo: File) {
    setError(null);
    setAviso(null);
    setSubiendo(true);
    try {
      const { documento } = await api.subirDocumento(archivo);
      setDocumentos((prev) => [documento, ...prev]);
      setAviso(`${documento.nombre_archivo} recibido. Procesando…`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo subir el archivo.");
    } finally {
      setSubiendo(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function borrar(doc: Documento) {
    setError(null);
    try {
      await api.borrarDocumento(doc.id);
      setDocumentos((prev) => prev.filter((d) => d.id !== doc.id));
      setAviso(`${doc.nombre_archivo} eliminado.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar.");
    }
  }

  function soltar(e: React.DragEvent) {
    e.preventDefault();
    setArrastrando(false);
    const archivo = e.dataTransfer.files?.[0];
    if (archivo) void subir(archivo);
  }

  const propios = documentos.filter((d) => !d.es_publico);
  const comunes = documentos.filter((d) => d.es_publico);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[760px] px-6 py-8">
        <h1 className="text-3xl text-[color:var(--chalk)]">Documentos</h1>
        <p className="mt-2 mb-8 max-w-[62ch] text-sm leading-relaxed text-[color:var(--chalk-dim)]">
          Todo lo que subas pasa a formar parte de lo que el agente puede consultar. Se
          extrae el texto, se parte en fragmentos y se guarda vectorizado. A partir de ahí,
          podrá responder preguntas sobre su contenido citando el fragmento exacto.
        </p>

        {/* ── Zona de carga ──────────────────────────────────────────────── */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setArrastrando(true);
          }}
          onDragLeave={() => setArrastrando(false)}
          onDrop={soltar}
          className={`flex flex-col items-center gap-3 border border-dashed px-6 py-10 text-center transition ${
            arrastrando
              ? "border-[color:var(--signal)] bg-[rgba(52,211,153,0.05)]"
              : "border-[color:var(--line-strong)]"
          }`}
        >
          {subiendo ? (
            <Loader2 size={22} className="animate-spin text-[color:var(--signal)]" />
          ) : (
            <Upload size={22} className="text-[color:var(--chalk-faint)]" />
          )}
          <div>
            <p className="text-sm text-[color:var(--chalk)]">
              Arrastra un archivo aquí o{" "}
              <button
                type="button"
                onClick={() => inputRef.current?.click()}
                className="text-[color:var(--signal)] underline underline-offset-4"
              >
                búscalo en tu equipo
              </button>
            </p>
            <p className="mt-1 text-xs text-[color:var(--chalk-faint)]">
              PDF, TXT, MD, CSV o DOCX · hasta 25 MB
            </p>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={FORMATOS}
            className="hidden"
            onChange={(e) => {
              const archivo = e.target.files?.[0];
              if (archivo) void subir(archivo);
            }}
          />
        </div>

        <AnimatePresence>
          {error && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              role="alert"
              className="mt-4 border-l-2 border-[color:var(--foul)] bg-[rgba(229,72,77,0.08)] py-2 pl-3 text-sm text-[color:var(--chalk)]"
            >
              {error}
            </motion.p>
          )}
          {aviso && !error && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="mt-4 border-l-2 border-[color:var(--signal)] py-2 pl-3 text-sm text-[color:var(--chalk-dim)]"
            >
              {aviso}
            </motion.p>
          )}
        </AnimatePresence>

        {/* ── Listas ─────────────────────────────────────────────────────── */}
        {cargando ? (
          <p className="mt-10 text-sm text-[color:var(--chalk-faint)]">Cargando…</p>
        ) : (
          <>
            <Seccion titulo="Tus documentos" vacio="Todavía no has subido ninguno.">
              {propios.map((d) => (
                <Fila key={d.id} doc={d} onBorrar={() => void borrar(d)} />
              ))}
            </Seccion>

            <Seccion
              titulo="Base común de fútbol"
              descripcion="Cargada con el sistema y disponible para todas las cuentas. Llega hasta el Mundial de 2022."
              vacio="La base común está vacía."
            >
              {comunes.map((d) => (
                <Fila key={d.id} doc={d} />
              ))}
            </Seccion>
          </>
        )}
      </div>
    </div>
  );
}

function Seccion({
  titulo,
  descripcion,
  vacio,
  children,
}: {
  titulo: string;
  descripcion?: string;
  vacio: string;
  children: React.ReactNode;
}) {
  const hayContenido = Array.isArray(children) ? children.length > 0 : Boolean(children);
  return (
    <section className="mt-10">
      <h2 className="font-[family-name:var(--font-display)] text-sm tracking-[0.14em] text-[color:var(--chalk-dim)] uppercase">
        {titulo}
      </h2>
      {descripcion && (
        <p className="mt-1 text-xs text-[color:var(--chalk-faint)]">{descripcion}</p>
      )}
      {hayContenido ? (
        <ul className="mt-3 border-t border-[color:var(--line)]">{children}</ul>
      ) : (
        <p className="mt-3 text-sm text-[color:var(--chalk-faint)]">{vacio}</p>
      )}
    </section>
  );
}

function Fila({ doc, onBorrar }: { doc: Documento; onBorrar?: () => void }) {
  return (
    <motion.li
      layout
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex items-center gap-3 border-b border-[color:var(--line)] py-3"
    >
      <FileText size={15} className="shrink-0 text-[color:var(--chalk-faint)]" />

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm text-[color:var(--chalk)]">{doc.nombre_archivo}</p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-[color:var(--chalk-faint)]">
          <span>{tamanoLegible(doc.tamano_bytes)}</span>
          {doc.estado === "LISTO" && (
            <span>
              {doc.num_fragmentos} {doc.num_fragmentos === 1 ? "fragmento" : "fragmentos"}
            </span>
          )}
          {doc.estado === "ERROR" && doc.error && (
            <span className="text-[color:var(--foul)]">{doc.error}</span>
          )}
        </p>
      </div>

      <Estado estado={doc.estado} />

      {onBorrar ? (
        <button
          type="button"
          onClick={onBorrar}
          aria-label={`Eliminar ${doc.nombre_archivo}`}
          className="shrink-0 text-[color:var(--chalk-faint)] transition hover:text-[color:var(--foul)]"
        >
          <Trash2 size={15} />
        </button>
      ) : (
        <span
          className="shrink-0 text-[color:var(--chalk-faint)]"
          title="Los documentos de la base común no se pueden eliminar"
        >
          <Lock size={14} />
        </span>
      )}
    </motion.li>
  );
}

function Estado({ estado }: { estado: Documento["estado"] }) {
  const estilos: Record<Documento["estado"], string> = {
    PROCESANDO: "text-[color:var(--caution)]",
    LISTO: "text-[color:var(--signal)]",
    ERROR: "text-[color:var(--foul)]",
  };
  const texto: Record<Documento["estado"], string> = {
    PROCESANDO: "Procesando",
    LISTO: "Listo",
    ERROR: "Error",
  };

  return (
    <span
      className={`shrink-0 font-[family-name:var(--font-display)] text-[11px] tracking-[0.12em] uppercase ${estilos[estado]}`}
    >
      {estado === "PROCESANDO" && (
        <Loader2 size={11} className="mr-1 inline animate-spin align-[-1px]" />
      )}
      {texto[estado]}
    </span>
  );
}
