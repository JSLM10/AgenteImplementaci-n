# Frontend — VAR

React 19 con Vite, TypeScript, Tailwind v4 y Motion.

## Puesta en marcha

```bash
npm install
npm run dev
```

http://localhost:5173. Necesita el backend en marcha; la URL se configura en `.env`:

```
VITE_API_URL=http://localhost:8000
```

Vite incrusta las variables `VITE_*` en tiempo de compilación, así que cambiarla exige
reconstruir, no solo reiniciar.

## Pantallas

| Ruta | Qué hace |
|---|---|
| `/entrar` | Registro e inicio de sesión |
| `/` | Chat. Con la conversación vacía, el orbe ocupa el centro |
| `/conversacion/:id` | Una conversación con su historial |
| `/documentos` | Subida, listado con estado y borrado |

## Decisiones

**El orbe es la entrada al chat, no el chat.** `MorphOrb` está construido para una
pregunta y una respuesta: tiene una animación de ida, una fase de espera y un despliegue
final en tarjeta. Forzarlo a representar un hilo entero lo rompería. Se usa donde brilla,
en la pantalla de bienvenida, y su animación de espera corre mientras el agente trabaja
de verdad. Sus etiquetas — *Pensando, Buscando, Evaluando, Redactando* — siguen los nodos
reales del grafo.

**Las fuentes se muestran siempre.** Bajo cada respuesta hay un desplegable con los
fragmentos que la sustentan, su documento de origen y su porcentaje de similitud. Es una
de las estrategias contra las alucinaciones: el usuario puede comprobarlo por sí mismo.

**La traza del grafo es visible.** Debajo de cada respuesta aparece el camino que recorrió
la pregunta. En la sustentación permite enseñar que una pregunta rechazada nunca llegó al
nodo de generación.

**Dirección visual: sala VAR en un estadio de noche.** Fondo de césped a oscuras, líneas
de tiza para la estructura, tipografía condensada de dorsal. El color se reserva para los
estados: ámbar mientras se procesa, esmeralda cuando hay respuesta fundamentada, rojo
cuando algo falla. El orbe es el único elemento llamativo.

## Organización

```
src/
├── components/
│   ├── AppShell.tsx    marco: barra lateral y conversaciones
│   ├── Fuentes.tsx     fragmentos que respaldan una respuesta
│   ├── TrazaGrafo.tsx  camino recorrido por el grafo
│   └── ui/             el componente del orbe
├── context/            sesión del usuario
├── lib/                cliente de la API y tipos
└── pages/              Login, Chat, Documentos
```

## Comprobaciones

```bash
npx tsc --noEmit   # tipos
npm run build      # build de producción
```
