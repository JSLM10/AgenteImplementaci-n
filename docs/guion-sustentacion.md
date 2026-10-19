# Guion de sustentación — VAR

Duración objetivo: **8 minutos**. Cubre los siete puntos que exige la sección 5.3 del
enunciado.

---

## Antes de empezar (15 minutos antes)

Una lista de comprobación corta evita el 90 % de los desastres en vivo.

```bash
# 1. Base de datos
docker compose up -d postgres

# 2. Ollama con el modelo cargado en memoria
ollama run qwen3.5:4b "hola"      # fuerza la carga; luego Ctrl-D

# 3. Backend
cd backend && uv run uvicorn app.main:app

# 4. Frontend
cd frontend && npm run dev
```

**Espera a ver `Modelo de embeddings en memoria` en el log del backend** antes de
preguntar nada. Sin esa precarga, la primera pregunta tarda 25 segundos en vez de 12.

Deja preparados:
- El navegador en `http://localhost:5173`, **sin sesión iniciada**.
- El archivo `docs/demo/acta-club-la-quebrada.md` a mano para subirlo.
- El editor abierto en `backend/app/agents/graph.py`.
- Una pestaña con la URL pública del despliegue.

---

## 0:00 — 1:00 · Tema y arquitectura

> «VAR, Verificador Aumentado de Respuestas. El nombre viene del videoarbitraje: el VAR
> revisa la evidencia antes de decidir y, si las imágenes no son concluyentes, no cambia
> la decisión. Eso es exactamente lo que hace nuestro agente.
>
> Sabe de fútbol de entrada, pero lo importante es que aprende de cualquier documento que
> le subas. Y cuando no encuentra respaldo, lo dice en vez de inventárselo.»

Enseña el diagrama de arquitectura. Nombra las cuatro piezas en una frase cada una:
frontend React, API FastAPI protegida, agente LangGraph, PostgreSQL con pgvector. Menciona
que el modelo corre local, con Ollama.

**No te extiendas aquí.** La arquitectura se explica mejor con el sistema funcionando.

---

## 1:00 — 1:40 · Autenticación

Regístrate en vivo con una cuenta nueva.

> «Todo endpoint de la API exige token. Y no lo decimos de palabra: al arrancar, la
> aplicación recorre su propia tabla de rutas y, si alguna quedara expuesta, no arranca.»

Si hay tiempo y quieres enseñarlo: en otra pestaña, `curl http://localhost:8000/api/chat`
devuelve 401.

---

## 1:40 — 3:20 · Preguntas que el agente responde

Aparece el orbe. Primera pregunta:

> **¿Quién ganó el Mundial de 2022?**

Mientras la animación corre, aprovecha:

> «Las etiquetas que van girando —Pensando, Buscando, Evaluando, Redactando— no son
> decorativas: son los nodos reales por los que está pasando la pregunta en el grafo.»

Cuando llegue la respuesta, pasa al chat y **despliega las fuentes**:

> «Aquí está lo importante. No solo responde: enseña de qué fragmento salió la respuesta,
> de qué documento, y con qué porcentaje de similitud. Puedo comprobarlo yo mismo.»

Señala la traza del grafo bajo la respuesta.

Segunda y tercera pregunta, ya en el chat:

> **¿Cuántos Balones de Oro tiene Messi?**
> **¿Qué es el fuera de juego?**

---

## 3:20 — 4:20 · Preguntas que el agente rechaza

> **¿Cuál es la mejor receta para preparar sushi?**

> «Un modelo de lenguaje normal contestaría. Sabe hacer sushi. Pero este agente no
> responde con lo que el modelo sabe, sino con lo que encuentra en su base de
> conocimiento, y ahí no hay nada de sushi.»

Después, la que mejor funciona:

> **¿Quién ganó el Mundial de 2026?**

> «Esta es más interesante, porque sí es de fútbol. Nuestra base llega hasta 2022. El
> agente no se inventa un campeón: reconoce que no tiene la información.»

Explica brevemente que hay seis barreras, y nombra las dos más visibles: el umbral de
similitud, que descarta fragmentos **antes** de que el modelo los vea, y el nodo evaluador,
que decide si lo recuperado alcanza.

---

## 4:20 — 5:50 · Carga de un documento y pregunta que depende de él

Ve a **Documentos** y pregunta primero, en el chat:

> **¿Quién es el máximo goleador del Club La Quebrada?**

Rechazo. Ahora sube `acta-club-la-quebrada.md` arrastrándolo.

> «El archivo se recibe, se extrae su texto, se parte en fragmentos, se generan los
> embeddings y se guardan en la base vectorial. Pasa de PROCESANDO a LISTO solo.»

Cuando esté en **LISTO**, repite la pregunta:

> **¿Quién es el máximo goleador del Club La Quebrada y cuántos goles marcó?**

> «Duván Restrepo, 17 goles. Y ahí está la fuente: el acta que acabo de subir. Esto no
> existe en ningún sitio, es un documento que nos inventamos. El modelo no podía saberlo:
> lo ha leído del documento.»

Una segunda pregunta del mismo documento, para rematar:

> **¿Cuánto se multa por llegar tarde al entrenamiento?**

---

## 5:50 — 7:20 · El código y el grafo

Abre `backend/app/agents/graph.py`.

> «El grafo son siete nodos y dos bifurcaciones. Está escrito a mano con StateGraph, no es
> un agente prefabricado.»

Señala `_ruta_tras_evaluar`:

```python
def _ruta_tras_evaluar(state):
    return "generar" if state.get("contexto_suficiente") else "rechazar"
```

> «Esta línea es el corazón del trabajo. Si el contexto no alcanza, el nodo de generación
> **no llega a ejecutarse**. No es que le pidamos al modelo que no invente: es que no le
> damos la oportunidad.»

Si queda tiempo, abre `nodes.py` y enseña el nodo `evaluar`, o `prompts.py` con las reglas
de generación.

---

## 7:20 — 8:00 · Despliegue

Abre la URL pública. Haz una pregunta.

> «Backend en Hugging Face Spaces, base de datos en Neon y frontend en Vercel. No usamos
> Render, que es lo que sugería el enunciado, porque su plan gratuito da 512 MB de RAM y
> PyTorch ni llega a cargar. Spaces da 16 gigas.
>
> En la nube el modelo es más pequeño, así que responde más despacio y peor redactado. Lo
> decimos en el documento técnico: es la limitación real de ejecutar un modelo local sin
> GPU.»

---

## Preguntas probables del jurado

**¿Por qué no usasteis `create_react_agent`?**
Porque deja que el modelo decida si busca o no, y un modelo pequeño a menudo decide
responder de memoria — justo el fallo que queríamos evitar. En nuestro grafo la búsqueda
no es opcional: toda pregunta pasa por el nodo de recuperación.

**¿Qué pasa si subo un documento que miente?**
El agente lo repetirá y citará la fuente. No comprueba la veracidad del documento, solo
que la respuesta provenga de él. Esa es exactamente la garantía que ofrece un RAG, y por
eso enseñar las fuentes es parte del diseño.

**¿Cuánto tarda en responder?**
Unos 12 segundos por pregunta con el modelo cargado; 25 la primera, porque hay que cargar
el modelo de embeddings. Está medido nodo por nodo en el documento técnico.

**¿Por qué ese modelo y no otro?**
Lo medimos. `qwen3.5:4b` con el razonamiento desactivado da 11,7 tokens por segundo frente
a los 4,8 de `llama3`. Con el razonamiento activo devolvía respuestas vacías, porque
gastaba el presupuesto de tokens pensando.

**¿Los documentos de un usuario los ve otro?**
No. La búsqueda filtra por `es_publico OR owner_id = usuario`. La base de fútbol es común;
lo que sube cada uno es suyo.

**¿Por qué los embeddings no son de Ollama, como en clase?**
Porque local y nube comparten base vectorial, y vectores generados por modelos distintos
no son comparables. Además, con los embeddings en Ollama habríamos necesitado un Ollama
también en la nube.
