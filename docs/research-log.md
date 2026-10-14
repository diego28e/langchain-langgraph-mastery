# Research Log

> One entry per research checkpoint (at least one per module). The habit this builds: **never trust a tutorial, a model ID, or even this course without checking the current official page.**

## How to write an entry

A research checkpoint is a small investigation, not a reading task: ask one question, answer it in 150 words or fewer, back the answer with two primary sources, check it yourself, and write down what it changes in your code.

```text
### <Module NN or Lesson NN.LL> · YYYY-MM-DD · <short title>
- Question:    <one question with a checkable answer: yes/no, a name, a value, a short list>
- Answer:      <150 words or fewer>
- Sources:     best first, primary sources only
  1. <URL or file> · checked YYYY-MM-DD · <package>==<version>
  2. <URL or file> · checked YYYY-MM-DD · <package>==<version>
- Evidence:    <a short quote from a source, or the output of code you ran>
- Verified by: ran code | read source | found a test   (say which cell, file or test)
- Confidence:  high | medium | low, because <why>
- Action:      <what changes in my code or notes, or "none, because ...">
```

**What goes in each field**
- **Sources.** Primary sources are the official docs, the API reference, the source code, the changelog or release notes, and the package's own tests. A blog post, a forum answer or a chatbot reply can tell you where to look, but it is not a source. Put the source that settles the question first.
- **Package version.** The version the source applies to, from *your* environment: `python -m pip show langchain`, or `importlib.metadata.version("langchain")` in a notebook. Docs pages change without notice, so the date you checked matters too.
- **Verified by.** *Ran code*: a cell in the course environment printed the answer. *Read source*: you found it in the installed code (`??` in Jupyter, or the file under `site-packages`). *Found a test*: a test in the package's repository pins the behaviour.
- **Confidence.** High when two sources and your own check agree. Medium when you have one source, or no check of your own. Low when sources disagree, or they are older than your installed version.

## Rubric

Score each criterion 0, 1 or 2. An entry is finished when no criterion scores 0; aim for 2 on all four.

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| **Source quality** | No source, or only a blog post, forum answer or chatbot reply | One primary source | Two primary sources, ranked, each with the date checked and the package version |
| **Evidence** | "The docs say so" | A link to the exact section | A quoted line or a code output that shows the answer |
| **Verification** | Not checked yourself | Read the source or found a test | Ran code in your environment, and read the source or found a test |
| **Actionability** | No action, or "interesting" | A vague action ("update my code") | A concrete change (which file, setting or habit), or "none" with the reason |

---

## Entries

### Example · Module 02 · 2026-10-14 · `create_react_agent` → `create_agent`
- Question: Does tutorial code built on `create_react_agent` still run on my versions, and what must I change to move it to `create_agent`?
- Answer: It still runs, but it is deprecated since LangGraph 1.0, emits a deprecation warning when called, and is scheduled for removal in 2.0. The replacement is `create_agent` from `langchain.agents`. Three changes break copied tutorial code: the import (`from langchain.agents import create_agent`), `prompt=` is now `system_prompt=`, and `pre_model_hook=` / `post_model_hook=` are gone: that logic moves to middleware (`before_model`, `after_model`).
- Sources:
  1. https://docs.langchain.com/oss/python/migrate/langchain-v1 (section "Migrate to `create_agent`") · checked 2026-10-14 · langchain==1.4.5
  2. Installed source `langgraph/prebuilt/chat_agent_executor.py`, the `@deprecated` decorator on `create_react_agent` · checked 2026-10-14 · langgraph==1.2.15, langgraph-prebuilt==1.1.0
- Evidence: calling `create_react_agent(...)` emitted `LangGraphDeprecatedSinceV10`: "create_react_agent has been moved to `langchain.agents`. [...] Deprecated in LangGraph V1.0 to be removed in V2.0." And `list(inspect.signature(create_agent).parameters)` contains `system_prompt` and `middleware`, but no `prompt`, `pre_model_hook` or `post_model_hook`.
- Verified by: ran code (both checks, in the course environment) and read source (the decorator).
- Confidence: high, because the migration guide, the installed source and my own run agree on these versions. Re-check when LangGraph 2.0 ships.
- Action: use `create_agent(..., system_prompt=...)` everywhere; before copying a tutorial, search it for `create_react_agent`, `prompt=` and `_model_hook`.

> This is an example entry that shows the format. Replace it with your own, or keep it and add yours below.

<!-- Add your entries below this line -->
