# Web Search for Agents: Groq Browser Search vs Tavily

> Used in **Lesson 05.01** and every project that needs fresh information from the web.
> **Verified on October 11, 2026.** Re-check the linked pages at the Module 05 research checkpoint.

**Course default: Groq built-in browser search.** It needs no extra API key and runs on the same `openai/gpt-oss-*` models the course already uses. **Tavily** is taught next to it because it is the most common web-search tool in LangChain tutorials, works with *any* model, and gives you more control.

## 1. Groq built-in browser search (default)

Groq has **built-in (server-side) tools**: you list them in the `tools` parameter, and Groq's servers run the whole loop (search, read results, call the model again) and return one final answer. Your code never executes the search itself.

| Fact (Oct 11, 2026) | Detail |
|---|---|
| Tool identifier | `{"type": "browser_search"}` (the other built-in tool is `{"type": "code_interpreter"}`) |
| Supported models | `openai/gpt-oss-20b`, `openai/gpt-oss-120b`, `openai/gpt-oss-safeguard-20b` |
| How it searches | Interactive "browser" search that navigates pages, powered by **Exa** |
| Output | Final answer with inline citation markers, built from snippets of the pages visited |
| Big limitation | **Not compatible with structured outputs** on Groq |
| Cost tip | Use `reasoning_effort="low"`: higher effort means longer browsing sessions and many more tokens |
| Mixing tools | GPT-OSS models can combine built-in tools with your own (local) tools or remote MCP tools in one request |
| Not available | On regional/sovereign endpoints, and not HIPAA-covered |
| Pricing | See [Groq pricing](https://groq.com/pricing) and your console usage page. Browsing adds input tokens |

> **Gone:** `groq/compound` and `groq/compound-mini` (Groq's older "agentic system" models with web search) were **shut down on September 21, 2026**, with no replacement model ([Groq deprecations](https://console.groq.com/docs/deprecations)). Older tutorials that use them will fail.

Minimal call with the Groq SDK (from Groq's docs, shortened):

```python
from groq import Groq

client = Groq()  # reads GROQ_API_KEY
response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=[{"role": "user", "content": "What changed in LangGraph this month?"}],
    tools=[{"type": "browser_search"}],
    tool_choice="required",   # force a search for questions that need fresh data
    reasoning_effort="low",   # keeps browsing (and token use) short
)
print(response.choices[0].message.content)
```

Lesson 05.01 shows the LangChain version: `ChatGroq(...).bind(tools=[{"type": "browser_search"}], tool_choice="required")` (`bind_tools` can't convert built-in tools in `langchain-groq` 1.1.3, D-006), how the sources appear in `additional_kwargs["executed_tools"]`, and why a `.bind`-ed model can't also call your own tools: the course wraps the search in a normal `web_search` tool instead (`mastery.web_search`, D-016; checked 2026-10-12). LangChain treats this as **server-side tool use** ([Tools: server-side tool use](https://docs.langchain.com/oss/python/langchain/tools)).

## 2. Tavily (taught for comparison)

[Tavily](https://docs.tavily.com/) is a search API built for AI agents. Instead of a finished answer, it returns **clean, ranked results** (title, URL, content snippet, score), and your agent decides what to do with them. It has five capabilities: **Search**, **Extract** (read known URLs), **Map** and **Crawl** (explore a site), and **Research** (a cited report).

| Fact (Oct 11, 2026) | Detail |
|---|---|
| LangChain package | `langchain-tavily` (`TavilySearch`, `TavilyExtract`, `TavilyMap`, `TavilyCrawl`, research tools). The old `langchain_community` Tavily tool is deprecated |
| Free tier | **1,000 API credits per month, no credit card.** There is also a rate-limited **keyless** mode for quick tests |
| Credit cost | Basic search = 1 credit, advanced search = 2 credits. Extract: 1 credit per 5 URLs (basic) |
| Paid | Pay-as-you-go $0.008 per credit. Monthly plans from $30 for 4,000 credits |
| Rate limits | 100 requests/min (development key), 1,000 requests/min (production key). Returns `429` + `Retry-After` |
| Useful controls | `max_results`, `topic` (general / news / finance), `search_depth`, `time_range`, `start_date` / `end_date`, `include_domains` / `exclude_domains` |
| Works with | Any tool-calling model (Groq, OpenAI, Gemini, Ollama…) |

```python
from langchain_tavily import TavilySearch

search = TavilySearch(max_results=5, topic="general")  # reads TAVILY_API_KEY
results = search.invoke({"query": "LangGraph 1.2 release notes"})
```

## 3. Which one when?

| Situation | Better choice | Why |
|---|---|---|
| Learning, quick research answers on Groq | **Groq browser search** | No extra key, one call, citations included |
| You need **structured output** in the same call | **Tavily** (or two steps with Groq) | Groq browser search can't be combined with structured outputs |
| You must **see and filter the sources** (allow-lists, dates, domains) | **Tavily** | Raw results + domain/date filters |
| Model is **not GPT-OSS on Groq** (OpenAI, Gemini, local Ollama) | **Tavily** | Groq's tool only works on Groq's GPT-OSS models |
| Token budget is tight | **Tavily** with `max_results` small | Browsing at high reasoning effort can use many tokens |
| You want fewer moving parts and vendors | **Groq browser search** | One provider, one bill |

**Two-step pattern used in the course** when you need search *and* a strict schema: (1) call Groq with `browser_search` to get a cited answer, then (2) pass that text to a second call with structured output (for example a `ResearchNote` Pydantic model with `summary` and `sources: list[str]`).

> ⚠️ **Production note: web search is untrusted input.**
> Search results are text written by strangers, which makes them a prompt-injection channel (Lesson 04.05). In production: treat results as data, never as instructions; restrict domains where you can; keep side-effecting tools behind human approval; log which URLs fed each answer; set timeouts and per-request search limits; and keep a fallback provider (for example Tavily when Groq's built-in tool is unavailable, or the other way round). Built-in tools are not available on Groq's regional/sovereign endpoints, so check this before you promise data residency.

## Sources (fetched October 11, 2026)

- Groq: [Built-in tools](https://console.groq.com/docs/tool-use/built-in-tools) · [Browser search](https://console.groq.com/docs/tool-use/built-in-tools/browser-search) · [Code execution](https://console.groq.com/docs/tool-use/built-in-tools/code-execution) · [Tool use overview](https://console.groq.com/docs/tool-use/overview) · [Local tool calling](https://console.groq.com/docs/tool-use/local-tool-calling) · [Structured outputs](https://console.groq.com/docs/structured-outputs) · [Deprecations](https://console.groq.com/docs/deprecations) · [Exa](https://exa.ai/)
- Tavily: [Docs](https://docs.tavily.com/) · [Credits & pricing](https://docs.tavily.com/documentation/api-credits) · [Rate limits](https://docs.tavily.com/documentation/rate-limits) · [Keyless mode](https://docs.tavily.com/documentation/keyless) · [LangChain integration](https://docs.tavily.com/documentation/integrations/langchain) · [Search API reference](https://docs.tavily.com/documentation/api-reference/endpoint/search) · [`langchain-tavily` on PyPI](https://pypi.org/project/langchain-tavily/)
- LangChain: [Tavily search integration](https://docs.langchain.com/oss/python/integrations/tools/tavily_search) · [Tools](https://docs.langchain.com/oss/python/langchain/tools) · [Groq integrations](https://docs.langchain.com/oss/python/integrations/providers/groq)
