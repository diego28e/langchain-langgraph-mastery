# Research Log

> One entry per module (at least). The habit this builds: **never trust a tutorial, a model ID, or even this course without checking the current official page.**

## How to write an entry

```text
### Module NN · YYYY-MM-DD
- Page(s) checked:  <URL(s)>
- What I looked for: <the research checkpoint question>
- What I found:      <one thing that changed or is new>
- Impact:            <what to change in my code/notes/course, or "none">
- Follow-up:         <issue to open, lesson to update, or "none">
```

---

## Entries

### Example · Module 00 · 2026-10-11
- Page(s) checked: https://console.groq.com/docs/deprecations, https://console.groq.com/docs/models
- What I looked for: are the Groq model IDs used in popular LangChain tutorials still available?
- What I found: `qwen/qwen3-32b` (shut down 2026-07-17), `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` (2026-08-16), and `groq/compound` / `groq/compound-mini` (2026-09-21) no longer work. The current Qwen model is `qwen/qwen3.8-27b`, and it is a **preview** model. The LangChain ChatGroq page and Groq's LangChain page still show retired IDs in their examples.
- Impact: use `openai/gpt-oss-20b` / `openai/gpt-oss-120b` (production models) as defaults, and keep model IDs in one config place (`.env` → `mastery/models.py`).
- Follow-up: re-check at every module's research checkpoint.

> This is an example entry that shows the format. Replace it with your own, or keep it and add yours below.

<!-- Add your entries below this line -->
