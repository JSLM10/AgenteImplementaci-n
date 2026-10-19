import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { useAuth } from "./context/AuthContext";
import { Chat } from "./pages/Chat";
import { Documentos } from "./pages/Documentos";
import { Login } from "./pages/Login";

function Cargando() {
  return (
    <div className="grid h-full place-items-center">
      <div className="flex items-center gap-3 text-[color:var(--chalk-dim)]">
        <span className="h-2 w-2 animate-pulse rounded-full bg-[color:var(--signal)]" />
        <span className="font-[family-name:var(--font-display)] text-sm tracking-[0.12em] uppercase">
          Comprobando sesión
        </span>
      </div>
    </div>
  );
}

/** Ninguna pantalla del sistema es accesible sin sesión activa. */
function RutaProtegida({ children }: { children: React.ReactNode }) {
  const { usuario, cargando } = useAuth();
  if (cargando) return <Cargando />;
  if (!usuario) return <Navigate to="/entrar" replace />;
  return <>{children}</>;
}

export default function App() {
  const { usuario, cargando } = useAuth();

  return (
    <Routes>
      <Route
        path="/entrar"
        element={cargando ? <Cargando /> : usuario ? <Navigate to="/" replace /> : <Login />}
      />
      <Route
        path="/"
        element={
          <RutaProtegida>
            <AppShell />
          </RutaProtegida>
        }
      >
        <Route index element={<Chat />} />
        <Route path="conversacion/:id" element={<Chat />} />
        <Route path="documentos" element={<Documentos />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
