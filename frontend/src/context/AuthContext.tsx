import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api, registrarCaducidadDeSesion, tokens } from "../lib/api";
import type { Usuario } from "../lib/types";

interface AuthContextValue {
  usuario: Usuario | null;
  cargando: boolean;
  entrar: (email: string, password: string) => Promise<void>;
  registrarse: (nombre: string, email: string, password: string) => Promise<void>;
  salir: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);

  // Al cargar la página, si hay un token guardado se comprueba contra el
  // servidor: puede haber caducado o haberse revocado al cerrar sesión.
  useEffect(() => {
    let vigente = true;

    registrarCaducidadDeSesion(() => {
      if (vigente) setUsuario(null);
    });

    (async () => {
      if (!tokens.access) {
        setCargando(false);
        return;
      }
      try {
        const yo = await api.yo();
        if (vigente) setUsuario(yo);
      } catch {
        tokens.limpiar();
      } finally {
        if (vigente) setCargando(false);
      }
    })();

    return () => {
      vigente = false;
    };
  }, []);

  const entrar = useCallback(async (email: string, password: string) => {
    const datos = await api.iniciarSesion({ email, password });
    tokens.guardar(datos);
    setUsuario(datos.usuario);
  }, []);

  const registrarse = useCallback(
    async (nombre: string, email: string, password: string) => {
      const datos = await api.registrar({ nombre, email, password });
      tokens.guardar(datos);
      setUsuario(datos.usuario);
    },
    [],
  );

  const salir = useCallback(async () => {
    try {
      await api.cerrarSesion();
    } catch {
      // Aunque el servidor no responda, la sesión local se cierra igual.
    }
    tokens.limpiar();
    setUsuario(null);
  }, []);

  const valor = useMemo(
    () => ({ usuario, cargando, entrar, registrarse, salir }),
    [usuario, cargando, entrar, registrarse, salir],
  );

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
