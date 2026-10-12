# Modern LangChain & LangGraph Mastery

**🌐 Language:** **English** · [Español](README.es.md)

> Modern LangChain & LangGraph course materials. Build production-ready agents, RAG systems, and LLM applications with practical projects and official-docs-driven learning.

![Status](https://img.shields.io/badge/status-in%20development-orange)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![LangChain](https://img.shields.io/badge/LangChain-v1-green)
![LangGraph](https://img.shields.io/badge/LangGraph-v1-green)
![Docs verified](https://img.shields.io/badge/docs%20verified-2026--10--11-informational)

---

## Why this course

Most LangChain tutorials online were written for the pre-v1 API (LCEL chains, memory classes, `create_react_agent`) and use model IDs that providers have since shut down. This course is built on **the current official docs** and teaches you to keep it that way yourself.

You will learn to:

- build agents with **LangChain v1 `create_agent`** and shape them with **middleware** (guardrails, human-in-the-loop, retries, summarization);
- orchestrate durable, stateful workflows with **LangGraph** (persistence, interrupts, time travel, subgraphs, streaming);
- design **RAG** systems that cite their sources and are measured, not guessed;
- connect agents to the world through **tools, web search, and MCP**;
- coordinate **multi-agent systems**;
- build long-running agents with **Deep Agents** (a full module): planning, virtual filesystems and backends, subagents, context engineering, skills and memory, sandboxed code execution, and trajectory evals;
- add **voice and multimodal** input/output with Groq Whisper and Orpheus;
- **test, evaluate, and trace** with pytest and LangSmith, then **deploy a self-hosted service** with FastAPI and Docker;
- use **Jupyter** like a professional, not just as a scratchpad.

Every shortcut the course takes (free tiers, preview models, local storage) comes with a **⚠️ Production note** that explains what to do in a real system ([all production notes](docs/production-notes.md)).

## Two parts

| Part | Modules | What you can do at the end | Est. time (part-time) |
|---|---|---|---|
| **Part 1 — Core** | 00–08 | Design, build, and debug agents, RAG systems, and LangGraph workflows with memory, guardrails, MCP tools, and human approval | ~14–16.5 weeks |
| **Part 2 — Pro** | 09–14 | Build multi-agent systems and long-running **deep agents**, add voice, prove quality with evals, and run agents as a self-hosted production service (plus an optional local-models/fine-tuning elective) | ~11–12.5 weeks + capstones |

## Who it's for

- Python developers who want to become **AI engineers** building reliable LLM applications.
- Data scientists moving from notebooks to production agent systems.
- Anyone who learned "old LangChain" and wants a clean, current mental model.

### Prerequisites

- Comfortable with Python (functions, classes, type hints, virtual environments, `pip`).
- Basic git and command line.
- No prior LangChain, LangGraph, or ML background required.
- Machine: Windows, macOS, or Linux. The course is developed on **Windows + Anaconda + Jupyter Notebook**.

## How to use this repo

1. **Verify your environment** with [setup/VERIFY_ENVIRONMENT.md](setup/VERIFY_ENVIRONMENT.md). Nothing gets installed at this step; you only check what you have. New to environments? Read [Python environments, compared](setup/PYTHON_ENVIRONMENTS_COMPARED.md) (pip, venv, conda, uv, Poetry, and more, in plain English). Full setup instructions will come later in [setup/FULL_SETUP_APPENDIX.md](setup/FULL_SETUP_APPENDIX.md).
2. Copy `.env.example` to `.env` and add the keys you need for the current module (Module 00 only needs `GROQ_API_KEY`).
3. Read the [Course Outline](COURSE_OUTLINE.md). It lists every lesson, notebook, reading list, and project spec.
4. Work through `modules/` in order. Each module folder has a README listing its lessons.
5. Follow [CONVENTIONS.md](CONVENTIONS.md) for notebook structure, comments, production notes, and commits.
6. Log your research checkpoints in [docs/research-log.md](docs/research-log.md) and model choices in [docs/decision-log.md](docs/decision-log.md).

## Modules

### Part 1 — Core

| # | Module | Status |
|---|---|---|
| 00 | [Foundations, Tooling & Research Skills](modules/00-foundations/) | ✅ Built |
| 01 | [Models, Messages & Prompts](modules/01-models-messages-prompts/) | ✅ Built |
| 02 | [Tools & Your First Agents](modules/02-tools-and-agents/) | ✅ Built |
| 03 | [Memory & Context Engineering](modules/03-memory-and-context/) | ✅ Built |
| 04 | [Middleware, Guardrails & Human-in-the-Loop](modules/04-middleware-guardrails-hitl/) | ✅ Built |
| 05 | [MCP & External Tools](modules/05-mcp-and-external-tools/) | ✅ Built |
| 06 | [Documents, Embeddings & RAG](modules/06-rag/) | ✅ Built |
| 07 | [LangGraph Fundamentals](modules/07-langgraph-fundamentals/) | 📝 Planned |
| 08 | [LangGraph Production Features](modules/08-langgraph-production-features/) | 📝 Planned |

### Part 2 — Pro

| # | Module | Status |
|---|---|---|
| 09 | [Multi-Agent Systems](modules/09-multi-agent-systems/) | 📝 Planned |
| 10 | [Deep Agents](modules/10-deep-agents/) | 📝 Planned |
| 11 | [Multimodal & Voice](modules/11-multimodal-and-voice/) | 📝 Planned |
| 12 | [Testing, Evaluation & Observability](modules/12-testing-evaluation-observability/) | 📝 Planned |
| 13 | [Production & Deployment (self-hosted FastAPI + Docker)](modules/13-production-and-deployment/) | 📝 Planned |
| 14 | [Local Models & Fine-Tuning (elective)](modules/14-local-models-and-fine-tuning/) | 📝 Planned |
| — | [Capstones](capstones/) | 📝 Planned |

Status legend: 📝 Planned · 🚧 In progress · ✅ Complete · 🔍 Reviewed (verified end to end)

## Tooling philosophy: free first, paid where it clearly helps

| Need | Free / local default | Paid option (when it adds clear value) |
|---|---|---|
| Chat & agent models | **Groq**: `openai/gpt-oss-20b`, `openai/gpt-oss-120b` · **Ollama** local models | **OpenAI** benchmark: `gpt-6-luna` (cheap), `gpt-6.1-sol` (quality ceiling). Low-cost option: **Gemini** free tier ([comparison](docs/paid-benchmark-openai-vs-gemini.md)) |
| Web search | **Groq built-in browser search** (no extra key) | **Tavily** (1,000 free credits/month, then paid) ([comparison](docs/web-search-groq-vs-tavily.md)) |
| Long-running agents (Module 10) | **Deep Agents** (open source) on the **Gemini free tier** by default (`gemini-3.6-flash`, an officially suggested Deep Agents model; public/synthetic data only) · Groq as the documented option · local Docker sandbox | Managed sandboxes (LangSmith, Daytona, Modal, …) · OpenAI benchmark |
| Vision | Groq `qwen/qwen3.8-27b` (preview ⚠️) · local vision models | OpenAI / Gemini multimodal models |
| Speech | Groq **Whisper** (STT) and **Orpheus** (TTS, preview ⚠️), low per-use cost | Specialized voice providers |
| Embeddings | Local Hugging Face / sentence-transformers, Ollama | Hosted embedding APIs |
| Vector store | `InMemoryVectorStore`, **Chroma** | pgvector (managed), Pinecone, Qdrant Cloud |
| Observability & evals | **LangSmith** free tier | LangSmith paid plans |
| Deployment | **FastAPI + Docker + Postgres**, self-hosted (Module 13) | Cloud VM/containers, managed Postgres, or LangSmith Cloud (optional reference lesson) |

⚠️ = preview model: fine for learning, not for production. See [production notes](docs/production-notes.md).

Model IDs change often. Groq shut down several popular models during 2026. The course keeps a [verified default model table](COURSE_OUTLINE.md#default-model-stack-verified-october-11-2026), and every module has a **research checkpoint** where you re-verify it.

## Official starting points

- LangChain: <https://docs.langchain.com/oss/python/langchain/overview>
- LangGraph: <https://docs.langchain.com/oss/python/langgraph/overview>
- Deep Agents: <https://docs.langchain.com/oss/python/deepagents/overview>
- LangSmith Observability: <https://docs.langchain.com/langsmith/observability> · Evaluation: <https://docs.langchain.com/langsmith/evaluation>
- Groq + LangChain: <https://docs.langchain.com/oss/python/integrations/chat/groq> · <https://console.groq.com/docs/langchain>
- Groq models (always check first): <https://console.groq.com/docs/models> · Deprecations: <https://console.groq.com/docs/deprecations>

See [RESOURCES.md](RESOURCES.md) for the full curated list.

## Repository layout

```text
.
├── README.md / README.es.md  # You are here (English / Spanish)
├── COURSE_OUTLINE.md         # Full syllabus: lessons, reading lists, projects, rubric
├── RESOURCES.md              # Curated, verified official links
├── CONVENTIONS.md            # Repo, notebook, code, production-note, and commit conventions
├── requirements.txt          # Minimum package versions (verified on PyPI)
├── .env.example              # Environment variable template (no real keys)
├── setup/                    # Environment verification, tool comparison, (later) full setup
├── docs/                     # Research log, decision log, production notes, comparison guides
├── modules/                  # One folder per module with lesson notebooks
├── capstones/                # Capstone specs and projects
├── src/                      # The reusable `mastery` package grown across modules
├── tests/                    # pytest suites (unit and integration)
└── data/                     # Sample data (small, committed) and outputs (gitignored)
```

## Project status

| Milestone | Status |
|---|---|
| Course outline | ✅ Done |
| Repository skeleton | ✅ Created |
| Module 00 notebooks | 📝 Next |
| Full setup appendix | 📝 Written at the end of the course |

## License

To be decided before the public release.

---

*Built by [@diego28e](https://github.com/diego28e). Docs verified on October 11, 2026.*
