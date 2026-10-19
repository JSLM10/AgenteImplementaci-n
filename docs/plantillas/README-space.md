---
title: VAR Backend
emoji: ⚽
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# VAR — Verificador Aumentado de Respuestas · backend

API del agente RAG construido con LangChain y LangGraph. Responde únicamente con
información recuperada de su base de conocimiento vectorial y rechaza de forma explícita
cuando no encuentra respaldo suficiente.

Trabajo de la asignatura Implementación e Integración de Software.
Equipo: Juan Pablo Muñoz · Gabriel Giraldo · Luis Brito.

## Endpoints

- `GET /api/health` — estado del servicio y configuración activa
- `GET /api/health/grafo` — diagrama del grafo de LangGraph, generado del código compilado
- `GET /docs` — documentación interactiva

El resto de endpoints exige un token de acceso.

## Configuración

Se ajusta por variables de entorno desde **Settings → Variables and secrets**:

| Clave | Tipo |
|---|---|
| `DATABASE_URL` | Secret — PostgreSQL con pgvector |
| `JWT_SECRET` | Secret |
| `LLM_PROVIDER` | `huggingface` en este despliegue |
| `HF_MODEL` | Modelo local de generación |
| `CORS_ORIGINS` | Dominio del frontend |
| `ENABLE_GROUNDEDNESS_CHECK` | `false` aquí, por el coste en CPU |

> **`app_port: 7860`.** Es el puerto que expone Spaces. El `Dockerfile` lee `$PORT`, que
> Spaces fija a ese valor, así que la misma imagen sirve en local con el 8000.

El código completo, con el frontend y la documentación, está en el repositorio del
proyecto.
