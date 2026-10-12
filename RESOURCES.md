# Resources

> Curated official and high-quality references, grouped by topic.
> **Every link was checked (HTTP 200) on October 11, 2026.** If a link breaks, finding the replacement is part of the course's research practice. Log it in [`docs/research-log.md`](docs/research-log.md).

## Contents

1. [Staying current: indexes, changelogs, policies](#1-staying-current-indexes-changelogs-policies)
2. [LangChain core](#2-langchain-core)
3. [Agents, middleware, guardrails, HITL](#3-agents-middleware-guardrails-hitl)
4. [Memory and context](#4-memory-and-context)
5. [MCP and tools](#5-mcp-and-tools)
6. [Retrieval and RAG](#6-retrieval-and-rag)
7. [LangGraph](#7-langgraph)
8. [Multi-agent and Deep Agents](#8-multi-agent-and-deep-agents)
9. [Multimodal and voice](#9-multimodal-and-voice)
10. [LangSmith: observability, evaluation, prompts](#10-langsmith-observability-evaluation-prompts)
11. [Testing](#11-testing)
12. [Deployment and production](#12-deployment-and-production)
13. [Groq](#13-groq)
14. [Other providers and local models](#14-other-providers-and-local-models)
15. [Fine-tuning](#15-fine-tuning)
16. [Security](#16-security)
17. [Jupyter and the Python toolchain](#17-jupyter-and-the-python-toolchain)
18. [Engineering practices](#18-engineering-practices)
19. [Courses for inspiration](#19-courses-for-inspiration)
20. [Package versions verified on PyPI](#20-package-versions-verified-on-pypi)

---

## 1. Staying current: indexes, changelogs, policies

| Resource | Why |
|---|---|
| [LangChain docs `llms.txt`](https://docs.langchain.com/llms.txt) | Machine-readable index of all docs. Fastest way to find the current page |
| [Use docs programmatically (docs MCP server)](https://docs.langchain.com/use-these-docs) | Connect the docs to your IDE/agent |
| [LangChain Python changelog](https://docs.langchain.com/oss/python/releases/changelog) | What changed, release by release |
| [LangSmith changelog](https://docs.langchain.com/langsmith/changelog) | Platform changes |
| [What's new in LangChain v1](https://docs.langchain.com/oss/python/releases/langchain-v1) | `create_agent`, content blocks, `langchain-classic` |
| [What's new in LangGraph v1](https://docs.langchain.com/oss/python/releases/langgraph-v1) | Stability release, `create_react_agent` deprecation |
| [LangChain v1 migration guide](https://docs.langchain.com/oss/python/migrate/langchain-v1) | Reading/upgrading older code |
| [LangGraph v1 migration guide](https://docs.langchain.com/oss/python/migrate/langgraph-v1) | Same, for LangGraph |
| [Versioning](https://docs.langchain.com/oss/python/versioning) · [Release policy](https://docs.langchain.com/oss/python/release-policy) | How to read version numbers and support windows |
| [LangChain blog](https://www.langchain.com/blog) | Announcements and deep dives |
| [langchain GitHub](https://github.com/langchain-ai/langchain) · [releases](https://github.com/langchain-ai/langchain/releases) | Source, issues, release notes |
| [langgraph GitHub](https://github.com/langchain-ai/langgraph) · [releases](https://github.com/langchain-ai/langgraph/releases) | Source, issues, release notes |
| [Groq `llms.txt`](https://console.groq.com/llms.txt) | Groq docs index (may lag behind; cross-check with the models page) |
| [Groq deprecations](https://console.groq.com/docs/deprecations) | **Check before using any Groq model ID** |

## 2. LangChain core

- [LangChain overview](https://docs.langchain.com/oss/python/langchain/overview)
- [Install](https://docs.langchain.com/oss/python/langchain/install) · [Quickstart](https://docs.langchain.com/oss/python/langchain/quickstart) · [Philosophy](https://docs.langchain.com/oss/python/langchain/philosophy)
- [Runtimes, frameworks, and harnesses](https://docs.langchain.com/oss/python/concepts/products) (LangChain vs LangGraph vs Deep Agents)
- [Providers and models](https://docs.langchain.com/oss/python/concepts/providers-and-models)
- [Component architecture](https://docs.langchain.com/oss/python/langchain/component-architecture)
- [Models](https://docs.langchain.com/oss/python/langchain/models) (init, invoke/stream/batch, tool calling, structured output, multimodal, reasoning, rate limiting, token usage)
- [Messages](https://docs.langchain.com/oss/python/langchain/messages) (message types, standard content blocks, multimodal)
- [Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [Streaming](https://docs.langchain.com/oss/python/langchain/streaming) · [Event streaming](https://docs.langchain.com/oss/python/langchain/event-streaming)
- [Common errors](https://docs.langchain.com/oss/python/common-errors)
- API reference: [langchain](https://reference.langchain.com/python/langchain) · [langchain-core](https://reference.langchain.com/python/langchain-core) · [`create_agent`](https://reference.langchain.com/python/langchain/agents/factory/create_agent) · [`ChatPromptTemplate`](https://reference.langchain.com/python/langchain-core/prompts/chat/ChatPromptTemplate) · [`Runnable`](https://reference.langchain.com/python/langchain-core/runnables/base/Runnable) · [Runnables index](https://reference.langchain.com/python/langchain-core/runnables)

## 3. Agents, middleware, guardrails, HITL

- [Agents](https://docs.langchain.com/oss/python/langchain/agents)
- [Tools](https://docs.langchain.com/oss/python/langchain/tools) · [Runtime](https://docs.langchain.com/oss/python/langchain/runtime)
- [Middleware overview](https://docs.langchain.com/oss/python/langchain/middleware/overview) · [Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in) · [Custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom) · [Middleware integrations](https://docs.langchain.com/oss/python/integrations/middleware/index)
- [Guardrails](https://docs.langchain.com/oss/python/langchain/guardrails)
- [Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [LangSmith Studio (LangChain)](https://docs.langchain.com/oss/python/langchain/studio) · [Agent Chat UI](https://docs.langchain.com/oss/python/langchain/ui)
- [Frontend overview](https://docs.langchain.com/oss/python/langchain/frontend/overview)
- Tutorials: [SQL agent](https://docs.langchain.com/oss/python/langchain/sql-agent) · [Data analysis agent from scratch](https://docs.langchain.com/oss/python/langchain/deep-agent-from-scratch)

## 4. Memory and context

- [Memory overview](https://docs.langchain.com/oss/python/concepts/memory) · [Context overview](https://docs.langchain.com/oss/python/concepts/context)
- [Short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory) · [Long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory)
- [Context engineering in agents](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [Checkpointer integrations](https://docs.langchain.com/oss/python/integrations/checkpointers/index) · [Store integrations](https://docs.langchain.com/oss/python/integrations/long-term-memory/index)

## 5. MCP and tools

- [LangChain MCP (`langchain.mcp`, MCPAdapter)](https://docs.langchain.com/oss/python/langchain/mcp/index) · [MCP tools](https://docs.langchain.com/oss/python/langchain/mcp/tools) · [MCP connections](https://docs.langchain.com/oss/python/langchain/mcp/connections) · [MCP auth](https://docs.langchain.com/oss/python/langchain/mcp/auth)
- [Migrate from langchain-mcp-adapters](https://docs.langchain.com/oss/python/migrate/langchain-mcp-adapters) · legacy repo: [langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
- [Model Context Protocol](https://modelcontextprotocol.io/) · [FastMCP](https://gofastmcp.com/)
- [Tool integrations](https://docs.langchain.com/oss/python/integrations/tools/index) · [Tavily search integration](https://docs.langchain.com/oss/python/integrations/tools/tavily_search) · [Tavily docs](https://docs.tavily.com/)
- **Web search (course default: Groq built-in browser search)** → course guide: [Groq browser search vs Tavily](docs/web-search-groq-vs-tavily.md)
  - Groq: [Built-in tools](https://console.groq.com/docs/tool-use/built-in-tools) · [Browser search](https://console.groq.com/docs/tool-use/built-in-tools/browser-search) · [Code execution](https://console.groq.com/docs/tool-use/built-in-tools/code-execution) · [Local tool calling](https://console.groq.com/docs/tool-use/local-tool-calling)
  - Tavily: [Credits & pricing](https://docs.tavily.com/documentation/api-credits) · [Rate limits](https://docs.tavily.com/documentation/rate-limits) · [Keyless mode](https://docs.tavily.com/documentation/keyless) · [LangChain integration (Tavily docs)](https://docs.tavily.com/documentation/integrations/langchain) · [Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search)

## 6. Retrieval and RAG

- [Retrieval (2-step, agentic, hybrid RAG)](https://docs.langchain.com/oss/python/deepagents/retrieval)
- [Build a semantic search engine](https://docs.langchain.com/oss/python/langchain/knowledge-base)
- [Build a custom RAG agent with LangGraph](https://docs.langchain.com/oss/python/langgraph/agentic-rag)
- [Multi-source knowledge base with routing](https://docs.langchain.com/oss/python/langchain/multi-agent/router-knowledge-base)
- [RAG with Deep Agents](https://docs.langchain.com/oss/python/deepagents/rag)
- Integrations: [Document loaders](https://docs.langchain.com/oss/python/integrations/document_loaders/index) ([Docling](https://docs.langchain.com/oss/python/integrations/document_loaders/docling), [Unstructured](https://docs.langchain.com/oss/python/integrations/document_loaders/unstructured_file)) · [Text splitters](https://docs.langchain.com/oss/python/integrations/splitters/index) · [Embeddings](https://docs.langchain.com/oss/python/integrations/embeddings/index) ([Hugging Face](https://docs.langchain.com/oss/python/integrations/embeddings/huggingfacehub), [Ollama](https://docs.langchain.com/oss/python/integrations/embeddings/ollama)) · [Vector stores](https://docs.langchain.com/oss/python/integrations/vectorstores/index) ([Chroma](https://docs.langchain.com/oss/python/integrations/vectorstores/chroma), [PGVector](https://docs.langchain.com/oss/python/integrations/vectorstores/pgvector), [Qdrant](https://docs.langchain.com/oss/python/integrations/vectorstores/qdrant), [Pinecone](https://docs.langchain.com/oss/python/integrations/vectorstores/pinecone)) · [Retrievers](https://docs.langchain.com/oss/python/integrations/retrievers/index)
- Vendor docs: [Chroma](https://docs.trychroma.com/) · [Pinecone](https://docs.pinecone.io/) · [FAISS](https://github.com/facebookresearch/faiss) · [Sentence Transformers](https://www.sbert.net/) · [Cohere rerank](https://docs.cohere.com/docs/rerank-overview)

## 7. LangGraph

- [Overview](https://docs.langchain.com/oss/python/langgraph/overview) · [Install](https://docs.langchain.com/oss/python/langgraph/install) · [Quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart)
- [Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph) · [Workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- APIs: [Graph API overview](https://docs.langchain.com/oss/python/langgraph/graph-api) · [Use the Graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api) · [Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api) · [Use the Functional API](https://docs.langchain.com/oss/python/langgraph/use-functional-api) · [Choosing APIs](https://docs.langchain.com/oss/python/langgraph/choosing-apis) · [Runtime (Pregel)](https://docs.langchain.com/oss/python/langgraph/pregel)
- Capabilities: [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) · [Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) · [Stores](https://docs.langchain.com/oss/python/langgraph/stores) · [Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance) · [Streaming](https://docs.langchain.com/oss/python/langgraph/streaming) · [Event streaming](https://docs.langchain.com/oss/python/langgraph/event-streaming) · [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) · [Time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel) · [Memory](https://docs.langchain.com/oss/python/langgraph/add-memory) · [Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- Production: [Application structure](https://docs.langchain.com/oss/python/langgraph/application-structure) · [Local server](https://docs.langchain.com/oss/python/langgraph/local-server) · [Test](https://docs.langchain.com/oss/python/langgraph/test) · [Backward compatibility](https://docs.langchain.com/oss/python/langgraph/backward-compatibility) · [Deployment](https://docs.langchain.com/oss/python/langgraph/deploy) · [Observability](https://docs.langchain.com/oss/python/langgraph/observability)
- [Case studies](https://docs.langchain.com/oss/python/langgraph/case-studies) · [SQL agent (LangGraph)](https://docs.langchain.com/oss/python/langgraph/sql-agent)
- [LangGraph API reference](https://reference.langchain.com/python/langgraph)

## 8. Multi-agent and Deep Agents

- [Multi-agent overview](https://docs.langchain.com/oss/python/langchain/multi-agent/index): [Subagents](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents) · [Handoffs](https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs) · [Skills](https://docs.langchain.com/oss/python/langchain/multi-agent/skills) · [Router](https://docs.langchain.com/oss/python/langchain/multi-agent/router) · [Custom workflow](https://docs.langchain.com/oss/python/langchain/multi-agent/custom-workflow)
- Tutorials: [Personal assistant with subagents](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents-personal-assistant) · [Customer support with handoffs](https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs-customer-support)
- [Migrate from langgraph-supervisor](https://docs.langchain.com/oss/python/migrate/langgraph-supervisor) (legacy repo: [langgraph-supervisor-py](https://github.com/langchain-ai/langgraph-supervisor-py))
- Deep Agents: [Overview](https://docs.langchain.com/oss/python/deepagents/overview) · [Quickstart](https://docs.langchain.com/oss/python/deepagents/quickstart) · [Customization](https://docs.langchain.com/oss/python/deepagents/customization) · [Subagents](https://docs.langchain.com/oss/python/deepagents/subagents) · [Backends](https://docs.langchain.com/oss/python/deepagents/backends) · [Skills](https://docs.langchain.com/oss/python/deepagents/skills) · [Memory](https://docs.langchain.com/oss/python/deepagents/memory) · [HITL](https://docs.langchain.com/oss/python/deepagents/human-in-the-loop) · [Going to production](https://docs.langchain.com/oss/python/deepagents/going-to-production) · [Deep research tutorial](https://docs.langchain.com/oss/python/deepagents/deep-research) · [Changelog](https://docs.langchain.com/oss/python/deepagents/changelog-py) · [GitHub](https://github.com/langchain-ai/deepagents)

## 9. Multimodal and voice

- [Messages: multimodal](https://docs.langchain.com/oss/python/langchain/messages)
- [Build a voice agent with LangChain](https://docs.langchain.com/oss/python/langchain/voice-agent)
- [Voice tracing fundamentals (LangSmith)](https://docs.langchain.com/langsmith/trace-voice-fundamentals)
- Groq: [Vision](https://console.groq.com/docs/vision) · [Speech to text](https://console.groq.com/docs/speech-to-text) · [Text to speech](https://console.groq.com/docs/text-to-speech) · [Orpheus](https://console.groq.com/docs/text-to-speech/orpheus)

## 10. LangSmith: observability, evaluation, prompts

- **Observability:** [Overview](https://docs.langchain.com/langsmith/observability) · [Tracing quickstart](https://docs.langchain.com/langsmith/observability-quickstart) · [Concepts](https://docs.langchain.com/langsmith/observability-concepts) · [Trace with LangChain](https://docs.langchain.com/langsmith/trace-with-langchain) · [Custom instrumentation](https://docs.langchain.com/langsmith/annotate-code) · [Metadata and tags](https://docs.langchain.com/langsmith/add-metadata-tags) · [Threads](https://docs.langchain.com/langsmith/threads) · [Cost tracking](https://docs.langchain.com/langsmith/cost-tracking) · [Log retriever traces](https://docs.langchain.com/langsmith/log-retriever-trace) · [Mask inputs/outputs](https://docs.langchain.com/langsmith/mask-inputs-outputs) · [Redact secrets](https://docs.langchain.com/langsmith/redact-secrets) · [Query traces (SDK)](https://docs.langchain.com/langsmith/export-traces)
- **Evaluation:** [Overview](https://docs.langchain.com/langsmith/evaluation) · [Quickstart](https://docs.langchain.com/langsmith/evaluation-quickstart) · [Concepts](https://docs.langchain.com/langsmith/evaluation-concepts) · [Approaches](https://docs.langchain.com/langsmith/evaluation-approaches) · [Datasets (SDK)](https://docs.langchain.com/langsmith/manage-datasets-programmatically) · [Evaluate agents](https://docs.langchain.com/langsmith/evaluate-llm-application) · [LLM-as-judge (SDK)](https://docs.langchain.com/langsmith/llm-as-judge-sdk) · [Code evaluators (SDK)](https://docs.langchain.com/langsmith/code-evaluator-sdk) · [Pairwise](https://docs.langchain.com/langsmith/evaluate-pairwise) · [Trajectory evals](https://docs.langchain.com/langsmith/trajectory-evals) · [openevals](https://docs.langchain.com/langsmith/openevals) · [Rate limits in evals](https://docs.langchain.com/langsmith/handle-model-rate-limiting)
- **Tutorials:** [Evaluate a chatbot](https://docs.langchain.com/langsmith/evaluate-chatbot-tutorial) · [Evaluate a RAG app](https://docs.langchain.com/langsmith/evaluate-rag-tutorial) · [Evaluate a complex agent](https://docs.langchain.com/langsmith/evaluate-complex-agent) · [Test a ReAct agent with pytest](https://docs.langchain.com/langsmith/test-react-agent-pytest)
- **Production monitoring:** [Online LLM-as-judge](https://docs.langchain.com/langsmith/online-evaluations-llm-as-judge) · [User feedback](https://docs.langchain.com/langsmith/attach-user-feedback) · [Annotation queues](https://docs.langchain.com/langsmith/annotation-queues) · [Dashboards](https://docs.langchain.com/langsmith/dashboards) · [Alerts](https://docs.langchain.com/langsmith/alerts) · [Insights](https://docs.langchain.com/langsmith/insights) · [LangSmith Engine](https://docs.langchain.com/langsmith/engine)
- **Prompts:** [Prompt & Context Hub](https://docs.langchain.com/langsmith/prompt-context-hub) · [Prompt engineering quickstart](https://docs.langchain.com/langsmith/prompt-engineering-quickstart) · [Manage prompts programmatically](https://docs.langchain.com/langsmith/manage-prompts-programmatically)
- **Studio:** [Studio](https://docs.langchain.com/langsmith/studio) · [Get started](https://docs.langchain.com/langsmith/quick-start-studio) · [How to use Studio](https://docs.langchain.com/langsmith/use-studio)
- **Account and limits:** [LangSmith app](https://smith.langchain.com/) · [Usage and billing](https://docs.langchain.com/langsmith/usage-and-billing)
- **Libraries:** [openevals](https://github.com/langchain-ai/openevals) · [agentevals](https://github.com/langchain-ai/agentevals)

## 11. Testing

- [Test (LangChain overview)](https://docs.langchain.com/oss/python/langchain/test/index) · [Unit testing](https://docs.langchain.com/oss/python/langchain/test/unit-testing) · [Integration testing](https://docs.langchain.com/oss/python/langchain/test/integration-testing) · [Agent evals](https://docs.langchain.com/oss/python/langchain/test/evals)
- [Test (LangGraph)](https://docs.langchain.com/oss/python/langgraph/test)
- [LangSmith + pytest](https://docs.langchain.com/langsmith/pytest)
- [pytest docs](https://docs.pytest.org/en/stable/)

## 12. Deployment and production

- [LangChain deployment](https://docs.langchain.com/oss/python/langchain/deploy) · [LangChain observability](https://docs.langchain.com/oss/python/langchain/observability)
- LangSmith Deployment (optional reference, Lesson 12.08): [Components](https://docs.langchain.com/langsmith/components) · [Agent Server](https://docs.langchain.com/langsmith/agent-server) · [Agent Server overview](https://docs.langchain.com/langsmith/agent-server-overview) · [Application structure](https://docs.langchain.com/langsmith/application-structure) · [Local dev & testing](https://docs.langchain.com/langsmith/local-dev-testing) · [Deploy to cloud quickstart](https://docs.langchain.com/langsmith/deployment-quickstart) · [Standalone servers](https://docs.langchain.com/langsmith/deploy-standalone-server) · [RemoteGraph](https://docs.langchain.com/langsmith/use-remote-graph) · [MCP endpoint](https://docs.langchain.com/langsmith/server-mcp) · [Auth](https://docs.langchain.com/langsmith/auth) · [Custom auth](https://docs.langchain.com/langsmith/custom-auth) · [CI/CD example](https://docs.langchain.com/langsmith/cicd-pipeline-example)
- [Agent Chat UI repo](https://github.com/langchain-ai/agent-chat-ui)
- **Self-hosted path (Module 12 default)**
  - FastAPI: [Docs](https://fastapi.tiangolo.com/) · [Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/) · [Custom responses / StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/) · [Bigger applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/) · [Settings](https://fastapi.tiangolo.com/advanced/settings/) · [Lifespan events](https://fastapi.tiangolo.com/advanced/events/) · [Security](https://fastapi.tiangolo.com/tutorial/security/) · [Testing](https://fastapi.tiangolo.com/tutorial/testing/) · [Deployment concepts](https://fastapi.tiangolo.com/deployment/concepts/) · [FastAPI in containers](https://fastapi.tiangolo.com/deployment/docker/)
  - Docker: [Get started](https://docs.docker.com/get-started/) · [Docker Desktop on Windows](https://docs.docker.com/desktop/setup/install/windows-install/) · [Python guide](https://docs.docker.com/guides/python/) · [Multi-stage builds](https://docs.docker.com/build/building/multi-stage/) · [Build best practices](https://docs.docker.com/build/building/best-practices/) · [Compose](https://docs.docker.com/compose/) · [Postgres image](https://hub.docker.com/_/postgres)
  - uv in containers: [uv + Docker](https://docs.astral.sh/uv/guides/integration/docker/) · [uv + FastAPI](https://docs.astral.sh/uv/guides/integration/fastapi/)
  - Config & persistence: [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) · [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) · [`langgraph-checkpoint-postgres`](https://pypi.org/project/langgraph-checkpoint-postgres/)
- Web UIs: [Streamlit](https://docs.streamlit.io/) · [Gradio](https://www.gradio.app/docs)
- **Production notes** for every course shortcut: [docs/production-notes.md](docs/production-notes.md)

## 13. Groq

| Topic | Link |
|---|---|
| Overview / quickstart | [Overview](https://console.groq.com/docs/overview) · [Quickstart](https://console.groq.com/docs/quickstart) · [API keys](https://console.groq.com/keys) |
| **Models (check first)** | [Supported models](https://console.groq.com/docs/models) · [Deprecations](https://console.groq.com/docs/deprecations) |
| Model cards used in the course | [gpt-oss-20b](https://console.groq.com/docs/model/openai/gpt-oss-20b) · [gpt-oss-120b](https://console.groq.com/docs/model/openai/gpt-oss-120b) · [gpt-oss-safeguard-20b](https://console.groq.com/docs/model/openai/gpt-oss-safeguard-20b) · [qwen3.8-27b](https://console.groq.com/docs/model/qwen/qwen3.8-27b) · [Prompt Guard 2 86M](https://console.groq.com/docs/model/meta-llama/llama-prompt-guard-2-86m) · [Whisper Large V3](https://console.groq.com/docs/model/whisper-large-v3) · [Whisper Large V3 Turbo](https://console.groq.com/docs/model/whisper-large-v3-turbo) · [Orpheus V1 English](https://console.groq.com/docs/model/canopylabs/orpheus-v1-english) |
| LangChain | [ChatGroq (LangChain docs)](https://docs.langchain.com/oss/python/integrations/chat/groq) · [Groq provider page](https://docs.langchain.com/oss/python/integrations/providers/groq) · [LangChain + Groq (Groq docs)](https://console.groq.com/docs/langchain) · [ChatGroq reference](https://reference.langchain.com/python/langchain-groq/chat_models/ChatGroq) |
| Capabilities | [Text generation](https://console.groq.com/docs/text-chat) · [Structured outputs](https://console.groq.com/docs/structured-outputs) · [Tool use](https://console.groq.com/docs/tool-use/overview) · [Built-in tools](https://console.groq.com/docs/tool-use/built-in-tools) · [Browser search](https://console.groq.com/docs/tool-use/built-in-tools/browser-search) · [Remote MCP](https://console.groq.com/docs/tool-use/remote-mcp) · [Reasoning](https://console.groq.com/docs/reasoning) · [Vision](https://console.groq.com/docs/vision) · [Responses API](https://console.groq.com/docs/responses-api) · [Content moderation](https://console.groq.com/docs/content-moderation) · [Prompting](https://console.groq.com/docs/prompting) |
| Speech | [Speech to text](https://console.groq.com/docs/speech-to-text) · [Text to speech](https://console.groq.com/docs/text-to-speech) · [Orpheus](https://console.groq.com/docs/text-to-speech/orpheus) |
| Production | [Rate limits](https://console.groq.com/docs/rate-limits) · [Errors](https://console.groq.com/docs/errors) · [Batch](https://console.groq.com/docs/batch) · [Production checklist](https://console.groq.com/docs/production-readiness/production-ready-checklist) · [Optimizing latency](https://console.groq.com/docs/production-readiness/optimizing-latency) · [LoRA inference](https://console.groq.com/docs/lora) |

## 14. Other providers and local models

- [All LangChain integrations](https://docs.langchain.com/oss/python/integrations/providers/overview) · [Chat model integrations](https://docs.langchain.com/oss/python/integrations/chat/index)
- **Paid benchmark (course default: OpenAI; optional: Gemini)** → course guide: [OpenAI vs Gemini](docs/paid-benchmark-openai-vs-gemini.md)
- OpenAI: [LangChain integration](https://docs.langchain.com/oss/python/integrations/providers/openai) · [ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai) · [Models](https://developers.openai.com/api/docs/models) · [Pricing](https://developers.openai.com/api/docs/pricing) · [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) · [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) · [Rate limits & usage tiers](https://developers.openai.com/api/docs/guides/rate-limits) · [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) · [Function calling](https://developers.openai.com/api/docs/guides/function-calling) · [Deprecations](https://developers.openai.com/api/docs/deprecations)
- Google Gemini: [LangChain Google integrations](https://docs.langchain.com/oss/python/integrations/providers/google) · [ChatGoogleGenerativeAI](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai) · [Models](https://ai.google.dev/gemini-api/docs/models) · [Pricing](https://ai.google.dev/gemini-api/docs/pricing) · [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) · [Billing & free tier](https://ai.google.dev/gemini-api/docs/billing) · [API keys](https://ai.google.dev/gemini-api/docs/api-key) · [Structured output](https://ai.google.dev/gemini-api/docs/structured-output) · [Function calling](https://ai.google.dev/gemini-api/docs/function-calling) · [Deprecations](https://ai.google.dev/gemini-api/docs/deprecations) · [Terms](https://ai.google.dev/gemini-api/terms)
- Anthropic: [LangChain integration](https://docs.langchain.com/oss/python/integrations/providers/anthropic) · [Models](https://platform.claude.com/docs/en/models/overview)
- Hugging Face: [LangChain integration](https://docs.langchain.com/oss/python/integrations/providers/huggingface) · [Inference Providers](https://huggingface.co/docs/inference-providers/index) · [Transformers](https://huggingface.co/docs/transformers/index) · [Model cards](https://huggingface.co/docs/hub/model-cards)
- Ollama: [LangChain integration](https://docs.langchain.com/oss/python/integrations/providers/ollama) · [ChatOllama](https://docs.langchain.com/oss/python/integrations/chat/ollama) · [Quickstart](https://docs.ollama.com/quickstart) · [Windows](https://docs.ollama.com/windows) · [API](https://docs.ollama.com/api/introduction) · [Tool calling](https://docs.ollama.com/capabilities/tool-calling) · [Model library](https://ollama.com/library)
- [vLLM](https://docs.vllm.ai/)

## 15. Fine-tuning

- [Unsloth docs](https://unsloth.ai/docs) · [PEFT](https://huggingface.co/docs/peft/index) · [Smithtune (LangSmith)](https://docs.langchain.com/langsmith/smithtune) · [Groq LoRA inference](https://console.groq.com/docs/lora) · [Google Colab](https://colab.research.google.com/)

## 16. Security

- [OWASP Top 10 for LLM Applications](https://genai.owasp.org/llm-top-10/) · [LLM01: Prompt Injection](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)
- [LangChain security policy](https://docs.langchain.com/oss/python/security-policy)
- [Guardrails](https://docs.langchain.com/oss/python/langchain/guardrails) · [MCP auth](https://docs.langchain.com/oss/python/langchain/mcp/auth)
- [The Twelve-Factor App: Config](https://12factor.net/config)

## 17. Jupyter and the Python toolchain

- Jupyter: [Docs home](https://docs.jupyter.org/en/latest/) · [Running the Notebook](https://docs.jupyter.org/en/latest/running.html) · [Jupyter Notebook](https://jupyter-notebook.readthedocs.io/en/stable/) · [Notebook UI](https://jupyter-notebook.readthedocs.io/en/stable/notebook.html) · [JupyterLab](https://jupyterlab.readthedocs.io/en/stable/) · [JupyterLab notebooks](https://jupyterlab.readthedocs.io/en/stable/user/notebook.html) · [Kernels](https://docs.jupyter.org/en/latest/install/kernels.html) · [Kernel spec (jupyter_client)](https://jupyter-client.readthedocs.io/en/stable/kernels.html)
- IPython: [Tutorial](https://ipython.readthedocs.io/en/stable/interactive/tutorial.html) · [Magics](https://ipython.readthedocs.io/en/stable/interactive/magics.html) · [Installing kernels per env](https://ipython.readthedocs.io/en/stable/install/kernel_install.html) · [autoreload](https://ipython.readthedocs.io/en/stable/config/extensions/autoreload.html) · [Autoawait](https://ipython.readthedocs.io/en/stable/interactive/autoawait.html) · [IPython.display](https://ipython.readthedocs.io/en/stable/api/generated/IPython.display.html)
- Notebook tooling: [nbstripout](https://github.com/kynan/nbstripout) · [Jupytext](https://jupytext.readthedocs.io/en/latest/) · [nbconvert](https://nbconvert.readthedocs.io/en/latest/) · [ipywidgets](https://ipywidgets.readthedocs.io/en/stable/) · [VS Code Jupyter](https://code.visualstudio.com/docs/datascience/jupyter-notebooks)
- Environments (plain-English comparison: [setup/PYTHON_ENVIRONMENTS_COMPARED.md](setup/PYTHON_ENVIRONMENTS_COMPARED.md)): [Anaconda docs](https://www.anaconda.com/docs/main) · [Conda environments (Anaconda)](https://www.anaconda.com/docs/getting-started/working-with-conda/environments) · [Managing environments (conda)](https://docs.conda.io/projects/conda/en/stable/user-guide/tasks/manage-environments.html) · [conda-forge](https://conda-forge.org/docs/) · [Miniforge](https://conda-forge.org/download/) · [mamba](https://mamba.readthedocs.io/en/latest/) · [pip](https://pip.pypa.io/en/stable/) · [venv](https://docs.python.org/3/library/venv.html) · [virtualenv](https://virtualenv.pypa.io/en/latest/) · [uv](https://docs.astral.sh/uv/) · [uv + Jupyter](https://docs.astral.sh/uv/guides/integration/jupyter/) · [Poetry](https://python-poetry.org/docs/) · [pipx](https://pipx.pypa.io/stable/) · [pyenv](https://github.com/pyenv/pyenv) · [pyenv-win](https://github.com/pyenv-win/pyenv-win) · [pixi](https://pixi.sh/latest/) · [Packaging tool recommendations](https://packaging.python.org/en/latest/guides/tool-recommendations/) · [VS Code Python environments](https://code.visualstudio.com/docs/python/environments)
- Python: [Version status](https://devguide.python.org/versions/) · [asyncio](https://docs.python.org/3/library/asyncio.html) · [Pydantic](https://docs.pydantic.dev/latest/) · [python-dotenv](https://pypi.org/project/python-dotenv/)

## 18. Engineering practices

- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/)
- [GitHub Actions](https://docs.github.com/en/actions) · [Building and testing Python](https://docs.github.com/en/actions/tutorials/build-and-test-code/python)
- [pre-commit](https://pre-commit.com/) · [pytest](https://docs.pytest.org/en/stable/)
- [Git docs](https://git-scm.com/docs)

## 19. Courses for inspiration

- LangChain Academy (free): [All courses](https://academy.langchain.com/) · [Introduction to LangChain (Python)](https://academy.langchain.com/courses/foundation-introduction-to-langchain-python) · [Introduction to LangGraph](https://academy.langchain.com/courses/intro-to-langgraph) · [Introduction to Deep Agents](https://academy.langchain.com/courses/foundation-introduction-to-deepagents) · [LangSmith Essentials](https://academy.langchain.com/courses/quickstart-langsmith-essentials) · [Production Monitoring](https://academy.langchain.com/courses/production-monitoring) · [LangSmith Deployment](https://academy.langchain.com/courses/langsmith-deployment)
- DeepLearning.AI: [Course catalog](https://www.deeplearning.ai/short-courses/) · [AI Agents in LangGraph](https://www.deeplearning.ai/short-courses/ai-agents-in-langgraph/) · [Long-Term Agentic Memory with LangGraph](https://www.deeplearning.ai/short-courses/long-term-agentic-memory-with-langgraph/) · [MCP: Build Rich-Context AI Apps with Anthropic](https://www.deeplearning.ai/short-courses/mcp-build-rich-context-ai-apps-with-anthropic/) (some courses predate v1, so check their APIs against the current docs)

## 20. Package versions verified on PyPI

Latest versions on **October 11, 2026** (for reference; `requirements.txt` uses these as minimums):

| Package | Latest | Requires Python |
|---|---|---|
| langchain | 1.4.4 | ≥ 3.10 |
| langchain-core | 1.6.9 | ≥ 3.10 |
| langgraph | 1.2.14 | ≥ 3.10 |
| langchain-groq | 1.1.3 | ≥ 3.10 |
| langsmith | 0.14.7 | ≥ 3.10 |
| deepagents | 0.7.23 | **≥ 3.11** |
| langchain-text-splitters | 1.1.3 | ≥ 3.10 |
| langchain-chroma | 1.1.0 | ≥ 3.10 |
| langchain-ollama | 1.1.0 | ≥ 3.10 |
| langchain-huggingface | 1.2.3 | ≥ 3.10 |
| langchain-openai | 1.7.0 | ≥ 3.10 |
| langchain-google-genai | 4.4.1 | ≥ 3.10 |
| langchain-anthropic | 1.7.5 | ≥ 3.10 |
| langchain-tavily | 0.2.18 | ≥ 3.10 |
| langchain-community | 0.4.2 | ≥ 3.10 |
| langchain-classic | 1.0.8 | ≥ 3.10 (legacy code only) |
| langgraph-checkpoint-sqlite | 3.1.1 | ≥ 3.10 |
| langgraph-checkpoint-postgres | 3.1.2 | ≥ 3.10 |
| fastapi | 0.143.0 | ≥ 3.10 |
| uvicorn | 0.54.0 | ≥ 3.10 |
| pydantic-settings | 2.15.0 | ≥ 3.10 |
| psycopg | 3.3.6 | ≥ 3.10 |
| uv (tool) | 0.13.0 | ≥ 3.8 |
| langgraph-cli | 0.4.33 | ≥ 3.10 |
| fastmcp | 4.1.0 | ≥ 3.10 |
| openevals | 0.2.0 | ≥ 3.10 |
| agentevals | 0.0.9 | ≥ 3.9 |
| groq (SDK) | 1.7.0 | ≥ 3.10 |
| chromadb | 1.5.9 | ≥ 3.9 |
| python-dotenv | 1.2.4 | ≥ 3.10 |
| ipykernel | 7.4.0 | **≥ 3.11** |
| notebook | 7.6.3 | ≥ 3.10 |
| jupyterlab | 4.6.4 | ≥ 3.10 |
| nbstripout | 0.9.1 | ≥ 3.10 |
| jupytext | 1.19.6 | ≥ 3.9 |
| langchain-mcp-adapters | 0.3.2 | legacy, superseded by `langchain[mcp]` |
| langgraph-supervisor | 0.0.31 | legacy, no longer actively maintained |
