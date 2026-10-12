# Paid Quality Benchmark: OpenAI vs Google Gemini

> Used in **Lesson 00.06** (provider decision framework) and every "paid contrast" stretch goal.
> **Prices and model IDs verified on October 11, 2026.** They change often: re-check the linked pages before you spend money, and log what you find in [decision-log.md](decision-log.md).

The course runs on **free Groq models** by default. A *paid benchmark* is a stronger model you run on the same prompts to answer one question: *"Is the free model good enough here, or am I leaving quality on the table?"* You only need it for comparisons, stretch goals, and LLM-as-judge evaluators. A few dollars cover the whole course if you keep prompts small.

## TL;DR

**Default: OpenAI.** Use `gpt-6-luna` as the cheap benchmark and `gpt-6.1-sol` when you want a quality ceiling. On paid tiers, `gpt-6-luna` costs **$0.10 input / $0.50 output per 1M tokens**, cheaper than any current stable Gemini text model. **Optional alternative: Gemini.** Its main advantage is a **free tier with no billing account** (`gemini-3.8-flash`, `gemini-3.5-flash-lite`). The catch: on the free tier, Google may use your prompts to improve its products, so never send private data there.

## Side-by-side

| | OpenAI | Google Gemini (Gemini Developer API) |
|---|---|---|
| **Cheap benchmark model** | `gpt-6-luna`: "optimize cost-sensitive, high-volume workloads" | `gemini-3.5-flash-lite` (stable) or `gemini-3.8-flash` (stable, "most intelligent Flash") |
| **Quality-ceiling model** | `gpt-6.1-sol` ("near-Astra performance at a lower cost"). Top tier: `gpt-6-astra` | `gemini-3.8-flash`. Pro tier is preview only (`gemini-3.1-pro-preview`) |
| **Price per 1M tokens (standard, ≤ 272K / ≤ 200K prompt)** | `gpt-6-luna` **$0.10 in / $0.50 out** · `gpt-6.1-sol` **$2.00 in / $10.00 out** · `gpt-6-astra` $10.00 / $50.00 | `gemini-3.5-flash-lite` **$0.30 in / $2.50 out** · `gemini-3.1-flash-lite` $0.25 / $1.50 · `gemini-3.8-flash` **$0.75 in / $3.75 out until Dec 31, 2026, then $1.50 / $7.50** · `gemini-3.1-pro-preview` $2.00 / $12.00 |
| **Cached input** | 10% of input price (Luna), 5% (6.1 Sol) | About 10% of input price, plus a storage fee per hour |
| **Batch / Flex** | 50% of standard | 50% of standard (Batch) |
| **Free tier** | "Free" usage tier exists in supported countries (usage cap $100/month), but the per-model rate-limit tables list only paid tiers. **Plan on buying $5 of credits** (Build tier) | **Yes, free of charge** for Flash and Flash-Lite models, up to the free-tier rate limits shown in AI Studio. No billing account needed. Free-tier content **may be used to improve Google products**. Pro preview is paid only |
| **Context window** | 1,050,000 tokens (Luna, 6.1 Sol, Astra), 128K max output | 1,048,576 input / 65,536 output (`gemini-3.8-flash`) |
| **Tool calling** | ✅ (Responses API; Chat Completions supports function calling on Luna only with `reasoning_effort="none"`) | ✅ Function calling |
| **Structured output** | ✅ `structured_outputs` listed for Luna | ✅ Structured outputs |
| **LangChain package** | `langchain-openai` (`ChatOpenAI`, 1.7.0 on PyPI). Tool calling ✅, structured output ✅, image input ✅. Set `use_responses_api=True` (or use a feature that routes there) | `langchain-google-genai` (`ChatGoogleGenerativeAI`, 4.4.1 on PyPI, released Oct 10, 2026). Tool calling ✅, structured output ✅, image/audio/video input ✅ |
| **API key env var** | `OPENAI_API_KEY` | `GOOGLE_API_KEY` (falls back to `GEMINI_API_KEY`) |
| **Built-in web search (optional)** | Web search tool: $10 per 1K calls + search content tokens at model rates (all models) | Grounding with Google Search: 5,000 free requests/month on the paid tier, then $14 per 1K. Not available on the free tier |

### What this means in practice

- **For benchmarking prompts, agents, and RAG answers:** `gpt-6-luna` is the cheapest strong paid baseline. One full course module of comparisons is usually a few cents.
- **For LLM-as-judge evaluators (Module 11):** use the quality ceiling (`gpt-6.1-sol`) on small datasets. Judges should be stronger than the model they grade.
- **If you cannot or will not add a card:** use Gemini's free tier with **public or synthetic data only**. Swap it in by changing one config value (see below).
- **Pricing gotcha:** Gemini 3.8 Flash's list price **doubles on January 1, 2027**. OpenAI prices go up 2× input / 1.5× output for prompts over 272K tokens. Neither matters for the course, but both matter in production.

## How the course switches providers

All model choices go through `mastery/models.py` and `.env` (see [.env.example](../.env.example)), so a benchmark is one line:

```python
# Illustrative. The real helper is built in Lesson 01.01.
from langchain.chat_models import init_chat_model

free_model = init_chat_model("groq:openai/gpt-oss-20b")        # course default
paid_benchmark = init_chat_model("openai:gpt-6-luna")          # needs OPENAI_API_KEY
optional_gemini = init_chat_model("google_genai:gemini-3.8-flash")  # needs GOOGLE_API_KEY
```

> ⚠️ **Production note: benchmark models are not a free pass.**
> The course pins one cheap paid model for comparisons. In production: pin exact model IDs (or dated snapshots where the provider offers them), read the provider's deprecation page, set a spend limit or budget alert in the provider console, track cost per request (Lesson 11.02), and keep a tested fallback provider (Lesson 04.02). Free tiers are for learning: they have no SLA, low rate limits, and (for Gemini) different data-use terms.

## Research checkpoint for this page

Open the four pricing/model pages below. Log in your decision log: (1) the current cheapest OpenAI and Gemini models with tool calling + structured output, (2) their price per 1M input/output tokens, (3) whether the free-tier terms changed.

## Sources (fetched October 11, 2026)

- OpenAI: [Models](https://developers.openai.com/api/docs/models) · [Pricing](https://developers.openai.com/api/docs/pricing) · [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) · [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) · [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) · [Rate limits and usage tiers](https://developers.openai.com/api/docs/guides/rate-limits) · [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) · [Function calling](https://developers.openai.com/api/docs/guides/function-calling) · [Deprecations](https://developers.openai.com/api/docs/deprecations)
- Gemini: [Models](https://ai.google.dev/gemini-api/docs/models) · [Pricing](https://ai.google.dev/gemini-api/docs/pricing) · [Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash) · [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) · [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) · [Billing](https://ai.google.dev/gemini-api/docs/billing) · [Structured output](https://ai.google.dev/gemini-api/docs/structured-output) · [Function calling](https://ai.google.dev/gemini-api/docs/function-calling) · [Deprecations](https://ai.google.dev/gemini-api/docs/deprecations) · [Terms](https://ai.google.dev/gemini-api/terms)
- LangChain: [ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai) · [ChatGoogleGenerativeAI](https://docs.langchain.com/oss/python/integrations/chat/google_generative_ai) · [Google integrations](https://docs.langchain.com/oss/python/integrations/providers/google) · [Structured output](https://docs.langchain.com/oss/python/langchain/structured-output) · [`langchain-openai` on PyPI](https://pypi.org/project/langchain-openai/) · [`langchain-google-genai` on PyPI](https://pypi.org/project/langchain-google-genai/)

> **Docs disagree sometimes.** On October 11, 2026, the LangChain Gemini page still used `gemini-3.7-flash` in its examples. Google deprecated that ID on August 13, 2026 and routes it to `gemini-3.8-flash` ([Gemini deprecations](https://ai.google.dev/gemini-api/docs/deprecations)). The provider's own model page wins.
