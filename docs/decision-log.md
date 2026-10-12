# Model & Provider Decision Log

> Every non-trivial choice of model, provider, vector store, or hosting option gets an entry. Future you (and your students) will want to know **why**.

## Template

```text
### D-NNN · <short title> · YYYY-MM-DD
- Context:    <task, constraints (cost, latency, privacy, rate limits)>
- Options:    <A, B, C with one line each>
- Decision:   <chosen option>
- Evidence:   <benchmarks from your notebooks, links to official docs/pricing pages, trace links>
- Trade-offs: <what you give up>
- Revisit:    <date or trigger, e.g. "if Groq deprecates model X">
```

---

## Decisions

> The entries below are **examples** that show the format and explain the course defaults. Add your own decisions below them.

### D-001 · Default chat/agent models for the course · 2026-10-11
- Context: Free-first learning on Groq, with tool calling and structured output required from Module 02.
- Options: (A) `openai/gpt-oss-20b` production, fastest/cheapest; (B) `openai/gpt-oss-120b` production, stronger reasoning; (C) `qwen/qwen3.8-27b` preview, multimodal.
- Decision: A as the "fast" default, B as the "reasoning" default, C only for vision lessons.
- Evidence: https://console.groq.com/docs/models (production vs preview), https://console.groq.com/docs/deprecations.
- Trade-offs: Preview models can be retired at short notice. Open-weight models may trail paid frontier models on hard tool-use tasks.
- Revisit: at every research checkpoint, or when Groq announces a deprecation.

### D-002 · Paid quality benchmark · 2026-10-11
- Context: Need a stronger paid model to check whether free Groq models are "good enough", and to act as an LLM-as-judge. Budget: a few dollars for the whole course.
- Options: (A) OpenAI `gpt-6-luna` ($0.10 in / $0.50 out per 1M tokens) with `gpt-6.1-sol` ($2 / $10) as the ceiling; (B) Gemini `gemini-3.8-flash` ($0.75 / $3.75 until 2026-12-31) or `gemini-3.5-flash-lite` ($0.30 / $2.50), with a free tier; (C) Anthropic.
- Decision: A by default. B when you want a free tier and only use public or synthetic data.
- Evidence: [docs/paid-benchmark-openai-vs-gemini.md](paid-benchmark-openai-vs-gemini.md) (OpenAI and Gemini pricing and model pages).
- Trade-offs: OpenAI needs about $5 of credits. Gemini's free tier may use your prompts to improve Google products.
- Revisit: 2027-01-01 (Gemini 3.8 Flash price change) or when either provider releases a new cheap model.

### D-003 · Default web search provider · 2026-10-11
- Context: Agents in Modules 05, 07, and 08 need fresh web information.
- Options: (A) Groq built-in `browser_search` on GPT-OSS models (no extra key); (B) Tavily via `langchain-tavily` (1,000 free credits/month, works with any model).
- Decision: A by default. B when you need structured output in the same call, raw sources with domain/date filters, or a non-Groq model.
- Evidence: [docs/web-search-groq-vs-tavily.md](web-search-groq-vs-tavily.md).
- Trade-offs: Groq browser search is not compatible with structured outputs and only works on GPT-OSS models.
- Revisit: when Groq changes its built-in tools (check the Groq built-in tools page).

### D-004 · Model for deep agents (Module 10) · 2026-10-11
- Context: Deep agents make many model calls per task and spawn subagents. They need a model that handles long tool-calling loops well, and enough free quota to finish a run.
- Options: (A) Groq `openai/gpt-oss-120b` + `openai/gpt-oss-20b` (course default elsewhere, free tier 8K tokens/min and 200K tokens/day, not in the official Deep Agents eval matrix); (B) Gemini `gemini-3.6-flash` (stable, on the official Deep Agents suggested list, free tier with no billing account); (C) OpenAI `gpt-6-luna` (paid).
- Decision: B by default for Module 10, A as a documented option, C as the paid benchmark.
- Evidence: https://docs.langchain.com/oss/python/deepagents/models (suggested models), https://ai.google.dev/gemini-api/docs/pricing (free tier), https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash (stable ID), https://console.groq.com/docs/rate-limits.
- Trade-offs: Gemini's free tier may use prompts for product improvement and human reviewers may read them, so only public or synthetic data. Free-tier limits are not published as fixed numbers (check AI Studio). Web search stays a tool (Groq or Tavily) because Google Search grounding is paid only.
- Revisit: when `gemini-3.6-flash` gets a shutdown date, when the Deep Agents suggested list changes, or on 2027-01-01 (price change).

<!-- Add your decisions below this line -->
