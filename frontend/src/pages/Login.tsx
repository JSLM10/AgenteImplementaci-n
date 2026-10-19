import { motion } from "motion/react";
import { useState } from "react";

import { useAuth } from "../context/AuthContext";
import { ApiError } from "../lib/api";

type Modo = "entrar" | "registro";

export function Login() {
  const { entrar, registrarse } = useAuth();
  const [modo, setModo] = useState<Modo>("entrar");
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const esRegistro = modo === "registro";

  function validar(): string | null {
    if (esRegistro && nombre.trim().length < 2) {
      return "Escribe tu nombre.";
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return "Ese correo no tiene un formato válido.";
    }
    if (esRegistro) {
      if (password.length < 8) return "La contraseña necesita al menos 8 caracteres.";
      if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
        return "La contraseña debe combinar letras y números.";
      }
    } else if (!password) {
      return "Escribe tu contraseña.";
    }
    return null;
  }

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const fallo = validar();
    if (fallo) {
      setError(fallo);
      return;
    }

    setError(null);
    setEnviando(true);
    try {
      if (esRegistro) {
        await registrarse(nombre.trim(), email.trim(), password);
      } else {
        await entrar(email.trim(), password);
      }
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "No se pudo completar la operación.",
      );
    } finally {
      setEnviando(false);
    }
  }

  function cambiarModo() {
    setModo(esRegistro ? "entrar" : "registro");
    setError(null);
  }

  return (
    <div className="relative grid min-h-full lg:grid-cols-[1.1fr_1fr]">
      {/* ── Lado izquierdo: el área grande dibujada a tiza ───────────────── */}
      <div className="relative hidden overflow-hidden border-r border-[color:var(--line)] lg:block">
        <PenaltyArea />
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="relative z-10 flex h-full flex-col justify-end p-12 xl:p-16"
        >
          <p className="font-[family-name:var(--font-display)] text-[clamp(3.5rem,7vw,6rem)] leading-[0.95] font-700 text-[color:var(--chalk)]">
            Primero la
            <br />
            evidencia.
          </p>
          <p className="mt-6 max-w-[46ch] text-[15px] leading-relaxed text-[color:var(--chalk-dim)]">
            VAR responde con lo que encuentra en su base de conocimiento y te enseña el
            fragmento del que lo sacó. Cuando no hay nada que lo respalde, lo dice en vez de
            inventárselo.
          </p>
        </motion.div>
      </div>

      {/* ── Lado derecho: el formulario ──────────────────────────────────── */}
      <div className="relative z-10 grid place-items-center px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-[380px]"
        >
          <div className="mb-10 flex items-baseline gap-3">
            <span className="font-[family-name:var(--font-display)] text-3xl font-700 tracking-tight text-[color:var(--chalk)]">
              VAR
            </span>
            <span className="text-xs leading-tight text-[color:var(--chalk-faint)]">
              Verificador Aumentado
              <br />
              de Respuestas
            </span>
          </div>

          <h1 className="text-2xl text-[color:var(--chalk)]">
            {esRegistro ? "Crea tu cuenta" : "Entra a tu cuenta"}
          </h1>
          <p className="mt-2 mb-8 text-sm text-[color:var(--chalk-dim)]">
            {esRegistro
              ? "Tu cuenta guarda tus conversaciones y los documentos que subas."
              : "Las conversaciones y los documentos que subas son solo tuyos."}
          </p>

          <form onSubmit={enviar} noValidate className="flex flex-col gap-4">
            {esRegistro && (
              <Campo
                etiqueta="Nombre"
                id="nombre"
                tipo="text"
                valor={nombre}
                onChange={setNombre}
                autoComplete="name"
                placeholder="Juan Pablo"
              />
            )}

            <Campo
              etiqueta="Correo"
              id="email"
              tipo="email"
              valor={email}
              onChange={setEmail}
              autoComplete="email"
              placeholder="tu@correo.com"
            />

            <Campo
              etiqueta="Contraseña"
              id="password"
              tipo="password"
              valor={password}
              onChange={setPassword}
              autoComplete={esRegistro ? "new-password" : "current-password"}
              placeholder={esRegistro ? "Mínimo 8 caracteres" : ""}
              ayuda={esRegistro ? "Al menos 8 caracteres, con letras y números." : undefined}
            />

            {error && (
              <motion.p
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                role="alert"
                className="border-l-2 border-[color:var(--foul)] bg-[rgba(229,72,77,0.08)] py-2 pl-3 text-sm text-[color:var(--chalk)]"
              >
                {error}
              </motion.p>
            )}

            <button
              type="submit"
              disabled={enviando}
              className="mt-2 h-11 rounded-sm bg-[color:var(--signal)] font-[family-name:var(--font-display)] text-sm font-600 tracking-[0.1em] text-[#04120c] uppercase transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {enviando ? "Un momento…" : esRegistro ? "Crear cuenta" : "Entrar"}
            </button>
          </form>

          <p className="mt-8 text-sm text-[color:var(--chalk-dim)]">
            {esRegistro ? "¿Ya tienes cuenta?" : "¿Todavía no tienes cuenta?"}{" "}
            <button
              type="button"
              onClick={cambiarModo}
              className="text-[color:var(--signal)] underline underline-offset-4 hover:brightness-125"
            >
              {esRegistro ? "Entra" : "Créala"}
            </button>
          </p>
        </motion.div>
      </div>
    </div>
  );
}

interface CampoProps {
  etiqueta: string;
  id: string;
  tipo: string;
  valor: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  placeholder?: string;
  ayuda?: string;
}

function Campo({
  etiqueta,
  id,
  tipo,
  valor,
  onChange,
  autoComplete,
  placeholder,
  ayuda,
}: CampoProps) {
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm text-[color:var(--chalk-dim)]">
        {etiqueta}
      </label>
      <input
        id={id}
        type={tipo}
        value={valor}
        placeholder={placeholder}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        className="h-11 rounded-sm border border-[color:var(--line-strong)] bg-[color:var(--turf)] px-3 text-[15px] text-[color:var(--chalk)] transition placeholder:text-[color:var(--chalk-faint)] focus:border-[color:var(--signal)] focus:outline-none"
      />
      {ayuda && <p className="text-xs text-[color:var(--chalk-faint)]">{ayuda}</p>}
    </div>
  );
}

/** El área grande trazada a tiza. Se dibuja sola una vez, al cargar. */
function PenaltyArea() {
  return (
    <svg
      className="absolute inset-0 h-full w-full"
      viewBox="0 0 600 800"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <g
        fill="none"
        stroke="var(--chalk)"
        strokeOpacity="0.14"
        strokeWidth="2"
        strokeLinecap="square"
      >
        <motion.path
          d="M60 -40 V 420 H 540 V -40"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.6, ease: "easeInOut" }}
        />
        <motion.path
          d="M190 -40 V 250 H 410 V -40"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.4, delay: 0.2, ease: "easeInOut" }}
        />
        <motion.path
          d="M300 420 m -90 0 a 90 90 0 0 0 180 0"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1, delay: 0.7, ease: "easeInOut" }}
        />
        <motion.circle
          cx="300"
          cy="300"
          r="4"
          fill="var(--chalk)"
          fillOpacity="0.2"
          stroke="none"
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ duration: 0.4, delay: 1.1 }}
        />
      </g>
    </svg>
  );
}
