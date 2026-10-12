# Modern LangChain & LangGraph Mastery

**🌐 Idioma:** [English](README.md) · **Español**

> Materiales de un curso moderno de LangChain y LangGraph. Construye agentes, sistemas RAG y aplicaciones con LLM listos para producción, con proyectos prácticos y aprendiendo directamente de la documentación oficial.

![Estado](https://img.shields.io/badge/estado-en%20desarrollo-orange)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![LangChain](https://img.shields.io/badge/LangChain-v1-green)
![LangGraph](https://img.shields.io/badge/LangGraph-v1-green)
![Docs verificadas](https://img.shields.io/badge/docs%20verificadas-2026--10--11-informational)

> **Nota sobre el idioma:** este README está en español. El temario, los notebooks y el resto de los materiales del curso están en inglés, porque la documentación oficial de LangChain, LangGraph y Groq también lo está.

---

## ¿Por qué este curso?

La mayoría de los tutoriales de LangChain que encuentras en internet se escribieron para la API anterior a la v1 (cadenas LCEL, clases de memoria, `create_react_agent`) y usan IDs de modelos que los proveedores ya dieron de baja. Este curso se basa en **la documentación oficial actual** y te enseña a mantenerte al día por tu cuenta.

Vas a aprender a:

- construir agentes con **`create_agent` de LangChain v1** y moldearlos con **middleware** (guardrails, aprobación humana, reintentos, resúmenes);
- orquestar flujos durables y con estado usando **LangGraph** (persistencia, interrupciones, *time travel*, subgrafos, streaming);
- diseñar sistemas **RAG** que citan sus fuentes y cuya calidad se mide, no se adivina;
- conectar agentes con el mundo mediante **herramientas, búsqueda web y MCP**;
- coordinar **sistemas multiagente** y usar **Deep Agents** para tareas largas;
- agregar **voz y entrada/salida multimodal** con Whisper y Orpheus de Groq;
- **probar, evaluar y trazar** con pytest y LangSmith, y luego **desplegar un servicio propio** con FastAPI y Docker;
- usar **Jupyter** como profesional, no solo como borrador.

Cada atajo que toma el curso (planes gratuitos, modelos en *preview*, almacenamiento local) viene con una **⚠️ Nota de producción** que explica qué hacer en un sistema real ([todas las notas de producción](docs/production-notes.md)).

## Dos partes

| Parte | Módulos | Qué vas a poder hacer al final | Tiempo estimado (a medio tiempo) |
|---|---|---|---|
| **Parte 1 — Core** | 00–08 | Diseñar, construir y depurar agentes, sistemas RAG y flujos de LangGraph con memoria, guardrails, herramientas MCP y aprobación humana | ~14–16,5 semanas |
| **Parte 2 — Pro** | 09–13 | Construir sistemas multiagente y de voz, demostrar su calidad con evaluaciones y operar agentes como un servicio propio en producción (más un electivo opcional de modelos locales y *fine-tuning*) | ~9–10 semanas + proyectos finales |

## ¿Para quién es?

- Desarrolladores Python que quieren convertirse en **ingenieros de IA** y construir aplicaciones con LLM confiables.
- Científicos de datos que quieren pasar de los notebooks a sistemas de agentes en producción.
- Cualquier persona que aprendió el "LangChain viejo" y quiere un modelo mental limpio y actualizado.

### Requisitos previos

- Manejar Python con soltura (funciones, clases, *type hints*, entornos virtuales, `pip`).
- Conocimientos básicos de git y de la línea de comandos.
- No necesitas experiencia previa con LangChain, LangGraph ni machine learning.
- Equipo: Windows, macOS o Linux. El curso se desarrolla en **Windows + Anaconda + Jupyter Notebook**.

## Cómo usar este repositorio

1. **Verifica tu entorno** con [setup/VERIFY_ENVIRONMENT.md](setup/VERIFY_ENVIRONMENT.md). En este paso no se instala nada; solo revisas lo que ya tienes. ¿Te confunden los entornos? Lee [Python environments, compared](setup/PYTHON_ENVIRONMENTS_COMPARED.md) (pip, venv, conda, uv, Poetry y más, explicados en lenguaje sencillo; en inglés). Las instrucciones completas de instalación llegarán al final del curso en [setup/FULL_SETUP_APPENDIX.md](setup/FULL_SETUP_APPENDIX.md).
2. Copia `.env.example` a `.env` y agrega solo las claves que necesita el módulo actual (el Módulo 00 solo necesita `GROQ_API_KEY`).
3. Lee el [temario del curso](COURSE_OUTLINE.md). Ahí está cada lección, notebook, lista de lecturas y especificación de proyecto.
4. Avanza por `modules/` en orden. Cada carpeta de módulo tiene un README con sus lecciones.
5. Sigue [CONVENTIONS.md](CONVENTIONS.md) para la estructura de los notebooks, los comentarios, las notas de producción y los commits.
6. Registra tus *research checkpoints* en [docs/research-log.md](docs/research-log.md) y tus decisiones de modelos en [docs/decision-log.md](docs/decision-log.md).

## Módulos

### Parte 1 — Core

| # | Módulo | Estado |
|---|---|---|
| 00 | [Fundamentos, herramientas y habilidades de investigación](modules/00-foundations/) | 📝 Planificado |
| 01 | [Modelos, mensajes y prompts](modules/01-models-messages-prompts/) | 📝 Planificado |
| 02 | [Herramientas y tus primeros agentes](modules/02-tools-and-agents/) | 📝 Planificado |
| 03 | [Memoria e ingeniería de contexto](modules/03-memory-and-context/) | 📝 Planificado |
| 04 | [Middleware, guardrails y aprobación humana](modules/04-middleware-guardrails-hitl/) | 📝 Planificado |
| 05 | [MCP y herramientas externas](modules/05-mcp-and-external-tools/) | 📝 Planificado |
| 06 | [Documentos, embeddings y RAG](modules/06-rag/) | 📝 Planificado |
| 07 | [Fundamentos de LangGraph](modules/07-langgraph-fundamentals/) | 📝 Planificado |
| 08 | [LangGraph para producción](modules/08-langgraph-production-features/) | 📝 Planificado |

### Parte 2 — Pro

| # | Módulo | Estado |
|---|---|---|
| 09 | [Sistemas multiagente y Deep Agents](modules/09-multi-agent-and-deep-agents/) | 📝 Planificado |
| 10 | [Multimodalidad y voz](modules/10-multimodal-and-voice/) | 📝 Planificado |
| 11 | [Pruebas, evaluación y observabilidad](modules/11-testing-evaluation-observability/) | 📝 Planificado |
| 12 | [Producción y despliegue (FastAPI + Docker, autoalojado)](modules/12-production-and-deployment/) | 📝 Planificado |
| 13 | [Modelos locales y fine-tuning (electivo)](modules/13-local-models-and-fine-tuning/) | 📝 Planificado |
| — | [Proyectos finales (capstones)](capstones/) | 📝 Planificado |

Leyenda: 📝 Planificado · 🚧 En progreso · ✅ Completo · 🔍 Revisado (verificado de punta a punta)

## Filosofía de herramientas: primero lo gratuito, lo pago solo cuando aporta de verdad

| Necesidad | Opción gratuita / local por defecto | Opción paga (cuando aporta un valor claro) |
|---|---|---|
| Modelos de chat y agentes | **Groq**: `openai/gpt-oss-20b`, `openai/gpt-oss-120b` · modelos locales con **Ollama** | Referencia de calidad con **OpenAI**: `gpt-6-luna` (económico), `gpt-6.1-sol` (techo de calidad). Alternativa de bajo costo: plan gratuito de **Gemini** ([comparación](docs/paid-benchmark-openai-vs-gemini.md)) |
| Búsqueda web | **Búsqueda integrada de Groq** (*browser search*, sin clave extra) | **Tavily** (1.000 créditos gratis al mes, luego pago) ([comparación](docs/web-search-groq-vs-tavily.md)) |
| Visión | `qwen/qwen3.8-27b` en Groq (*preview* ⚠️) · modelos de visión locales | Modelos multimodales de OpenAI / Gemini |
| Voz | **Whisper** (voz a texto) y **Orpheus** (texto a voz, *preview* ⚠️) en Groq, bajo costo por uso | Proveedores de voz especializados |
| Embeddings | Hugging Face / sentence-transformers locales, Ollama | APIs de embeddings alojadas |
| Base vectorial | `InMemoryVectorStore`, **Chroma** | pgvector (administrado), Pinecone, Qdrant Cloud |
| Observabilidad y evaluaciones | Plan gratuito de **LangSmith** | Planes pagos de LangSmith |
| Despliegue | **FastAPI + Docker + Postgres**, autoalojado (Módulo 12) | VM o contenedores en la nube, Postgres administrado, o LangSmith Cloud (lección opcional de referencia) |

⚠️ = modelo en *preview*: sirve para aprender, no para producción. Mira las [notas de producción](docs/production-notes.md).

Los IDs de los modelos cambian seguido. Groq dio de baja varios modelos populares durante 2026. El curso mantiene una [tabla verificada de modelos por defecto](COURSE_OUTLINE.md#default-model-stack-verified-october-11-2026) y cada módulo tiene un ***research checkpoint*** donde vuelves a verificarla.

## Puntos de partida oficiales

- LangChain: <https://docs.langchain.com/oss/python/langchain/overview>
- LangGraph: <https://docs.langchain.com/oss/python/langgraph/overview>
- Deep Agents: <https://docs.langchain.com/oss/python/deepagents/overview>
- Observabilidad en LangSmith: <https://docs.langchain.com/langsmith/observability> · Evaluación: <https://docs.langchain.com/langsmith/evaluation>
- Groq + LangChain: <https://docs.langchain.com/oss/python/integrations/chat/groq> · <https://console.groq.com/docs/langchain>
- Modelos de Groq (revísalos siempre primero): <https://console.groq.com/docs/models> · Deprecaciones: <https://console.groq.com/docs/deprecations>

Consulta [RESOURCES.md](RESOURCES.md) para la lista completa de recursos.

## Estructura del repositorio

```text
.
├── README.md / README.es.md  # Estás aquí (inglés / español)
├── COURSE_OUTLINE.md         # Temario completo: lecciones, lecturas, proyectos, rúbrica
├── RESOURCES.md              # Enlaces oficiales seleccionados y verificados
├── CONVENTIONS.md            # Convenciones del repo, notebooks, código, notas de producción y commits
├── requirements.txt          # Versiones mínimas de paquetes (verificadas en PyPI)
├── .env.example              # Plantilla de variables de entorno (sin claves reales)
├── setup/                    # Verificación del entorno, comparación de herramientas, (luego) instalación completa
├── docs/                     # Bitácoras de investigación y decisiones, notas de producción, guías comparativas
├── modules/                  # Una carpeta por módulo con los notebooks de cada lección
├── capstones/                # Especificaciones y proyectos finales
├── src/                      # El paquete reutilizable `mastery`, que crece módulo a módulo
├── tests/                    # Pruebas con pytest (unitarias y de integración)
└── data/                     # Datos de ejemplo (pequeños, versionados) y salidas (ignoradas por git)
```

## Estado del proyecto

| Hito | Estado |
|---|---|
| Temario del curso | ✅ Listo |
| Estructura del repositorio | ✅ Creada |
| Notebooks del Módulo 00 | 📝 Lo siguiente |
| Apéndice de instalación completa | 📝 Se escribe al final del curso |

## Licencia

Se definirá antes del lanzamiento público.

---

*Creado por [@diego28e](https://github.com/diego28e). Documentación verificada el 11 de octubre de 2026.*
