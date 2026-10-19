# Guía de despliegue

Tres servicios, todos con plan gratuito. Orden obligatorio: primero la base de datos,
luego el backend, y el frontend al final, porque necesita la URL del backend en tiempo de
compilación.

Tiempo estimado: **30–40 minutos**, casi todo esperando compilaciones.

---

## 1. Base de datos — Neon

Neon da PostgreSQL gratuito y permanente, con pgvector incluido.

1. Entra en [neon.tech](https://neon.tech) y crea una cuenta.
2. **Create project**. Nombre: `var`. Región: la más cercana.
3. En el panel, copia la cadena de conexión (**Connection string**, formato *psql*). Tiene
   esta pinta:

   ```
   postgresql://usuario:clave@ep-algo-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

4. **Cámbiale el esquema** para que SQLAlchemy use el driver correcto: sustituye
   `postgresql://` por `postgresql+psycopg://`. Queda así:

   ```
   postgresql+psycopg://usuario:clave@ep-algo-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

   Guarda esa cadena: es el valor de `DATABASE_URL`.

> La extensión `vector` y las tablas las crea el backend solo, la primera vez que arranca.
> No hay que ejecutar ningún SQL a mano.

---

## 2. Backend — Hugging Face Spaces

Spaces da 16 GB de RAM y 2 vCPU gratis, que es lo que hace falta para cargar un modelo
local. Render gratis da 512 MB, donde PyTorch ni siquiera carga.

1. Entra en [huggingface.co](https://huggingface.co) y crea una cuenta.
2. **New Space**:
   - *Space name*: `var-backend`
   - *License*: MIT
   - *Select the Space SDK*: **Docker** → *Blank*
   - *Space hardware*: CPU basic (gratis)
   - Visibilidad: **Public**
3. Clona el Space vacío y copia dentro el contenido de `backend/`:

   ```bash
   git clone https://huggingface.co/spaces/TU_USUARIO/var-backend
   cd var-backend

   cp -r /ruta/al/proyecto/backend/* .
   cp /ruta/al/proyecto/docs/plantillas/README-space.md README.md
   ```

   El `README.md` lleva la cabecera YAML que Spaces necesita para saber que es un
   despliegue Docker y en qué puerto escucha.

4. En la pestaña **Settings → Variables and secrets** del Space, añade:

   | Clave | Tipo | Valor |
   |---|---|---|
   | `DATABASE_URL` | Secret | La cadena de Neon del paso 1 |
   | `JWT_SECRET` | Secret | Genera uno nuevo (abajo) |
   | `LLM_PROVIDER` | Variable | `huggingface` |
   | `HF_MODEL` | Variable | `Qwen/Qwen2.5-1.5B-Instruct` |
   | `AUTH_PROVIDER` | Variable | `local` |
   | `ENABLE_GROUNDEDNESS_CHECK` | Variable | `false` |
   | `CORS_ORIGINS` | Variable | Se rellena en el paso 3 |

   Para el secreto:

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   > **No reutilices el `JWT_SECRET` del `.env` local.** Está en tu máquina y podría
   > acabar en el repositorio.

5. Sube los archivos:

   ```bash
   git add -A
   git commit -m "Backend VAR"
   git push
   ```

6. Spaces construye la imagen. Tarda **10–15 minutos** la primera vez, porque descarga
   PyTorch y el modelo de embeddings. Sigue el progreso en la pestaña **Logs**.

7. Cuando termine, comprueba:

   ```
   https://TU_USUARIO-var-backend.hf.space/api/health
   ```

   Debe devolver `"estado": "ok"` y `"base_datos": "ok"`. Esa es la **URL pública del
   backend**.

> **La primera pregunta será lenta** (varios minutos): el modelo de HuggingFace se
> descarga y se carga al vuelo. Las siguientes van mucho mejor. El Space se duerme tras
> 48 horas sin tráfico y se despierta solo con la primera petición.

---

## 3. Frontend — Vercel

1. Entra en [vercel.com](https://vercel.com) y conecta tu cuenta de GitHub.
2. **Add New → Project** y elige el repositorio.
3. Configura:
   - *Framework Preset*: **Vite**
   - *Root Directory*: **`frontend`** ← importante, no la raíz
   - El resto, por defecto: `vercel.json` ya trae el build y el enrutado.
4. En **Environment Variables**, añade:

   | Clave | Valor |
   |---|---|
   | `VITE_API_URL` | `https://TU_USUARIO-var-backend.hf.space` |

   Sin barra final.

5. **Deploy**. Tarda un par de minutos.

6. Copia la URL que te da (`https://algo.vercel.app`) y **vuelve al Space de Hugging
   Face** para poner esa URL en `CORS_ORIGINS`. Sin ese paso el navegador bloqueará todas
   las peticiones.

   El Space se reinicia solo al cambiar una variable.

---

## 4. Comprobación final

En la URL de Vercel:

1. Regístrate con una cuenta nueva.
2. Entra en **Documentos**: deben aparecer los 8 documentos de fútbol.
3. Pregunta **¿Quién ganó el Mundial de 2022?** y espera. La primera tarda.
4. Pregunta **¿Cuál es la mejor receta para preparar sushi?**: debe rechazarla.

Si el paso 2 muestra la lista vacía, el backend no pudo sembrar el corpus: mira los
**Logs** del Space.

---

## Problemas frecuentes

**`connection to server failed` en los logs del Space.**
La `DATABASE_URL` no lleva `+psycopg` o le falta `?sslmode=require`.

**El frontend carga pero todo da error de red.**
`CORS_ORIGINS` en el Space no coincide con el dominio de Vercel. Tiene que ser exacto,
con `https://` y sin barra final.

**Cambié `VITE_API_URL` y el frontend sigue apuntando al sitio viejo.**
Vite incrusta las variables al compilar, no al arrancar. Hay que volver a desplegar en
Vercel (**Deployments → Redeploy**).

**El Space se queda sin memoria al construir.**
Cambia `HF_MODEL` a un modelo más pequeño, por ejemplo `Qwen/Qwen2.5-0.5B-Instruct`.

**Las respuestas en la nube son peores que en local.**
Es lo esperado y está declarado en el documento técnico: el modelo de la nube es de 1,5 B
y el local de 4 B. La demostración en vivo va por el entorno local.

---

## Qué anotar para el documento técnico

Cuando termines, rellena en `docs/documento-tecnico.md` §12:

- URL del frontend (Vercel)
- URL del backend (Hugging Face Spaces)
- Cualquier problema que te encontraras que no esté en la lista de arriba
