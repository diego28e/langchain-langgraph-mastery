# Course changelog

What changed in the course, newest first. After you pull an update ([setup/LEARNER_WORKFLOW.md](setup/LEARNER_WORKFLOW.md)), skim the latest entry: it says which lessons changed and whether you need to re-run anything.

## 2026-10-16 · Project 06: chunk-level citations and a 72-question test set

**Re-run after pulling:** Project 06 (starter and solution). If you already started it, compare your Steps 3–6 with the new README; the lessons are unchanged.

- Project 06 answers now cite the exact chunk they quote (`ChunkCitedAnswer` / `ChunkCitation` with a `chunk_id`); a real sentence attributed to the wrong chunk counts as fabricated.
- The project is scored on a new held-out test set, `data/samples/rag/project06-test-set.jsonl`: 72 questions in 6 answerable strata plus 18 unanswerable or off-topic questions that must be declined. Results include a per-stratum table. The 20-question golden set stays the lessons' development set.
- LIVE mode runs a stratified sample of 24 questions by default (`LIVE_QUESTIONS`).
- New helpers in `mastery.rag`: `format_context(..., with_ids=True)`, `verify_citations(..., require_chunk_id=True)`, `stratified_sample`, `score_by_stratum`, `is_right`.

## 2026-10-16 · Rubrics for every project, a dev container, opt-in version pins

**Re-run after pulling:** nothing is required. Setup cells changed slightly in every module (comment labels, and the warning filter only applies to older `langchain-core`), so re-run a notebook from the top if you keep it open.

- Every project README now has a **Rubric (self-assessment)** table: what "meets" and what "exceeds" looks like.
- Module 07 notebooks send traces to one LangSmith project per lesson (`m07-<lesson>`, Project 07: `m07-project-content-pipeline`), unless your `.env` sets `LANGSMITH_PROJECT`.
- New: `.devcontainer/` (GitHub Codespaces or VS Code Dev Containers) and `constraints/constraints-2026-10-16.txt`, the versions the course last passed with. Opt in with `python -m pip install -e ".[dev]" -c constraints/constraints-2026-10-16.txt`.
- Setup-cell comments are labelled `Setup 1–4`, so they no longer clash with the projects' `Step` headings.
- Lesson 00.03 mentions autosave. The 00.02 guide explains that `nbstripout` cleans what you commit, not the file on disk.

## 2026-10-16 · Clearer wording, corrected details and small code fixes in Modules 00–09

**Re-run after pulling:** nothing is required. If you re-run, the changed code cells are in Lessons 01.04, 01.05, 01.07, 05.01, 05.03, 06.04, 06.06, 06.07, 06.09, 07.04, 07.07 and 08.06, and Projects 01, 03, 05 and 08. No new installs.

- Many small text fixes: cross-references to the right module or lesson, time estimates that match the lessons, error messages quoted as they really appear, and solutions that match their exercises.
- `mastery.pricing.get_price` also finds prices for dated model snapshots. `mastery.graphs.sql.check_sql` now wraps queries that already use `LIMIT ... OFFSET` or end in a comment, and `run_readonly_query` stops a query after 5 seconds.
- Lesson 05.03 picks the docs search tool by name, not by its position in the server's list. Lesson 07.04's parallel checks understand answers like "Yes." and "No, it isn't." Lesson 07.07's keyword router matches whole words only.
- Streaming cells in Module 08 use `.text`, which also works with providers that stream content blocks.

## 2026-10-16 · A 🔎 Docs drill in every lesson of Modules 00–08

**Re-run after pulling:** nothing; the new cells are Markdown only.

- Every lesson in Modules 00–08 now ends with a short **🔎 Docs drill** (5–15 minutes) before its research checkpoint, like Modules 09 and 10: a question you answer from the official docs, the API reference or the installed source, with a collapsed **Path to the answer** that names where to look and how to confirm it.
- The drills practise reading source (`??`, `inspect.getsource`), checking defaults in your installed version, following a docs redirect or a changelog entry, and spotting where two official sources disagree.

## 2026-10-16 · Measured agentic RAG in Project 06, safer retries in Project 08, a baseline arm in Project 09

**Re-run after pulling:** Projects 06, 08 and 09, and Lessons 06.05, 06.08, 08.02, 08.04 and 09.05 (no new installs). If you already started one of these starters, compare your TODOs with the new starter before you continue (your copy in `workspace/` is never touched by a pull). Project 06's Chroma collection has a new name (it now includes the splitter settings and the embedding model), so the first run re-indexes.

### Project 06 · Docs Q&A Bot

- New TODO 5: an agentic variant (the model decides when to search) benchmarked next to the 2-step chain, with citations checked against the chunks it saw. A long-context variant (whole corpus in the prompt) is a reference column.
- Indexing is incremental: `mastery.rag.sync_index` adds, updates and deletes chunks per source file, and `collection_name` names the collection after the splitter and embedding settings. An edit check proves a changed file replaces its old chunks.
- The benchmark reports input tokens, $ per 1,000 questions and 95% intervals with a paired comparison against the 2-step chain. TODOs state the goal, with hints; a rubric is in the project README. Estimated time is now 7–9 hours.
- Lesson 06.08: corrected numbers for the hashing-embeddings fallback. Lesson 06.05 uses the shared `collection_name`.

### Project 08 · Research-and-Write Agent

- The web search retries only transient errors (`mastery.models.is_transient`, new) and its LIVE model has `max_retries=0`, so retries live in one layer; 400/401 errors are no longer retried.
- Stronger approval checks: nothing is final before the approval pause, each rejection runs the writer once more with that rejection's feedback, and giving up only counts after the rejection limit. Traces go to the `m08-project-research-agent` LangSmith project by default. TODOs state the goal, with hints.
- Lesson 08.02: why provider SDK errors need a classifier in `retry_on`. Lesson 08.04 sets its own `LANGSMITH_PROJECT`.

### Project 09 · Multi-Agent Support Desk

- The single-agent baseline is a third arm in the comparison, the ADR and the checks (10 checks now). The table adds $ per conversation and p50/p95 latency.
- LIVE runs 8 conversations that cover every route (`LIVE_IDS`; the first five were all billing) `TRIALS = 3` times and grades the worst trial (pass mark 7/8). Lesson 09.05 Exercise 4 uses the same conversations.
- The ADR is *proposed* and its recommendation is yours; the solution's is a labelled example. TODO descriptions state the goal; a pitfalls table covers the embedding-size collection error.

## 2026-10-16 · Measured comparisons in Projects 00 and 01, safer memory in Project 03, grounded Project 07

**Re-run after pulling:** Projects 00, 01, 03 and 07, and Lesson 01.03 (no new installs). If you already started one of these starters, compare your TODOs with the new starter before you continue (your copy in `workspace/` is never touched by a pull, see [setup/LEARNER_WORKFLOW.md](setup/LEARNER_WORKFLOW.md)). The Project 01 answer key changed (version `2026-10-16.1`): earlier Project 01 numbers aren't comparable.

### Project 00 · Groq Model Explorer

- Each prompt runs 3 times (`REPEATS`) and is graded by a small programmatic grader (checked on canned answers first); the summary shows pass rate per model and task, median and worst latency, and server-side vs end-to-end tokens/second (Groq's `completion_time` and `queue_time`).
- Calls are paced by **tokens** per minute, the free-plan limit that binds first, not by requests.
- The decision draft only considers models that answered: a retired model that fails fast is reported as "not a candidate", never as the fastest.
- The table check also requires `chat_model` with real True/False values; offline results are labelled as coming from the sample. TODOs state the goal, with two-level hints; the rubric's "Exceeds" column asks for work the starter doesn't already do. Estimated time is now 2.5–3.5 hours.

### Project 01 · Multi-Model Comparison Lab

- Answer key `2026-10-16.1`: one skills rule (cloud provider once, practices aren't skills; JP-08 is now `azure, python`), seniority bands without overlap (midpoint for ranges), and `_aliases` for skill names. The solution prompt states the same rules, and its naming examples no longer come from the scored postings.
- New Step 6b: 95% intervals for valid rate and field accuracy and a paired comparison against the most accurate configuration; the decision draft says whether the gap is significant and, if not, applies a tie-break policy. `MASTERY_LAB_RUNS=3` repeats every posting.
- Configuration names come from the strict flag that is actually sent (a swapped model can't keep a wrong "strict" label); the preview model uses `reasoning_format="parsed"`; each row records the settings sent and the answer-key version. A lenient skills/company score (aliases, accents) sits next to the strict one.
- Stronger self-checks: the prompt check names any missing labelling rule and flags examples taken from the postings; the scorer check runs six cases. TODOs state the goal, with two-level hints. The batch tracing note is corrected (one trace per posting).
- Lesson 01.03: the edge-case rule's score on the 12 tickets is flagged as optimistic, and the research checkpoint asks for new tickets.

### Project 03 · Study Buddy with Memory

- Threads have an owner: a user can't continue another user's thread. The leakage suite adds a positive control (the user's own memory is used), a differential test with a fresh store and an ownership test.
- The token budget counts the tool schemas (~180 tokens), and Session 2 prints the estimate next to the real input tokens. Hints for the TODOs.

### Project 07 · Content Pipeline Graph

- The graph sets a tight `recursion_limit` (`content_recursion_limit` in `mastery.graphs.content`), so a bug loop fails fast.
- "Score improves" is replaced by **grounded citations**: every `[source: …]` must be a source the research returned (with a made-up-citation control); every section needs a source; the LIVE critic is the 120b model. Server checks show ⏭️ skipped (not passed) when the server is off or fails to start.
- The Functional API stretch has a starter TODO and puts model calls in `@task`s. Goal-style TODOs with hints; LIVE cost corrected to 35–70k tokens; module time estimate corrected.

## 2026-10-16 · Stronger checks in Projects 02, 04 and 05

**Re-run after pulling:** Projects 02, 04 and 05 (no new installs). If you already started one of these starters, the specs changed slightly: compare your TODOs with the new starter before you continue (your copy in `workspace/` is never touched by a pull, see [setup/LEARNER_WORKFLOW.md](setup/LEARNER_WORKFLOW.md)).

### Project 02 · Personal Finance Agent

- "No arithmetic by the LLM" now checks **where** a number came from: data tools back their values, `convert_currency` and the calculator back their results only when their inputs were backed. A bare `calculator("870400")` or a COP → COP "conversion" no longer launders a number, and numbers in the answer text are checked too. A new cell shows three gaming attempts being flagged.
- `convert_currency` takes `Literal` currencies, refuses the same currency on both sides, and no longer echoes `amount`.
- Tolerances follow the question's unit (COP ±0.5, USD/EUR ±0.01, counts exact), matching the README. `N_RUNS` repeats the evaluation; acceptance uses the worst run.

### Project 04 · Safe Email Triage

- Approval is bound to content: `draft_reply` returns a draft id that is a hash of the text, and `send_email(draft_id)` sends exactly that text. A model can no longer swap in new text in the same turn as an approved send.
- `send_email` sends at most one reply per email (atomic create), approve/reject only (no edit, so the audit log records what ran), and a per-thread tool limit (run limits restart on every resume). `recursion_limit` is derived from the agent's graph, so the graceful limit fires and a 4-step task isn't cut short.
- The retry → fallback order from 04.02, phone numbers in the PII checks, and the Prompt Guard stretch sees redacted text only. 12 acceptance checks (was 8); the injection check is described as a regression test, not a measurement.

### Project 05 · Docs Research Agent

- The docs server's tools are pinned with `tool_fingerprint` and refused on change (rug pull). `tool_fingerprint` now also covers MCP annotations and, optionally, server instructions; `poisoned_descriptions` can scan instructions.
- An egress gate blocks `web_search` once private notes were read in the thread (the "lethal trifecta", new row in 05.05's threat table).
- Tool limits continue instead of ending, so a run still answers; a run that never answers is a scored failure, and one failing question no longer stops the benchmark. 12 acceptance checks (was 8).

## 2026-10-16 · Fixes across Modules 02–09

**Re-run after pulling:** the lessons listed below if you finished them (no new installs).

### Fixes you'll notice

- **Calculator:** `1e300 ** 2` and similar overflows now return a tool error instead of crashing the agent; fractional powers of negative numbers get their own message.
- **Hand-written tool loop (02.02, `mastery.agents`):** a reply with only malformed tool calls no longer ends the loop silently (each malformed call gets an error answer, and the transcript shows it); unexpected exceptions inside a tool reach the model as "tool failed (ErrorType)" without their internal text.
- **Lesson 02.04:** the alerts state uses a reducer, so two alerts in one reply both land (new cell) instead of raising `InvalidUpdateError`.
- **Lesson 03.02:** `prune()` is not implemented by the course's checkpointers; the lesson now shows `delete_thread` / `trim_thread` for retention.
- **Lesson 04.05 / `fence_untrusted`:** the data markers carry a content-bound tag, so text inside can't forge the end marker.
- **Hybrid search (`mastery.rag.hybrid_search`):** a metadata `filter` now applies to the keyword leg as well as the vector leg (no other-tenant chunks through BM25). Chroma reports a clear error when a collection was built with another embedding size.
- **Module 09:** the custom desk (09.05, Project 09 Step 9) keeps the active agent and the agents' tool results between turns; `subagent_tool(context="history")` no longer silently keeps only the last 12 messages (new `history_limit`); the FAQ's Chroma collection is named per embedding size; a 09.05 pitfall row is corrected.

## 2026-10-15 · Module 10, part 2

**Re-run after pulling:** nothing new to install. Re-run Lesson 10.04 only if you want its updated closing links.

### New

- **Lessons 10.05–10.08 are built:** agent evals (trajectory match modes, side-effect checks, a trajectory judge, multi-turn simulation, pass@k vs pass^k), production monitoring (sampling, judge budgets, corrected rates, alerts on interval bounds, feedback, annotation queues, trace retention), prompt management (versions, tags, gated promotion; LangSmith Prompt Hub cells optional) and testing strategy and CI gates (test pyramid, lower-bound gates, a release baseline, the `release_gate` CLI).
- **Project 10 · Pre-release Gate for the Support Desk:** label 200 traces, validate two judges, fix the top two failures, prove it with paired numbers, gate the release (a known-bad build must be blocked) and write the release report. 9 acceptance checks; collapsed hints.
- **CI:** new `.github/workflows/eval-gate.yml` runs the Module 10 tests and the release gate on pull requests that touch the desk or the evals.
- **`mastery`:** `mastery.evals` gains `monitoring`, `prompts` and `release_gate`; `mastery.agents.release_suite` holds the frozen release suite and red team; `build_handoffs_desk` accepts a `triage_prompt`.

### Fixes you'll notice

- The trace labeller now accepts a correct refund of "my last invoice".

## 2026-10-15 · Module 10, part 1

**Re-run after pulling:** `python -m pip install -e ".[dev]"` (new `evals` extra: `langsmith[otel]`, OpenTelemetry SDK and OTLP exporter; openevals and agentevals move into it).

### New

- **Module 10 Lessons 10.01–10.04 are built:** error analysis (open and axial coding of 60 support-desk traces, a failure taxonomy ranked by frequency × severity, saturation), observability (`@traceable` with version metadata and threads, masking secrets, OpenTelemetry spans with GenAI attribute names, the LangSmith OTLP settings), datasets and experiments (three sources of examples, dedupe, leak-checked splits, content versions, repetitions, paired comparisons, minimum detectable difference, cost budgets) and evaluators and judges (code first, one binary judge per category, TPR/TNR on held-out labels, corrected failure rates, calibration, cost-based thresholds with an abstain band, pairwise comparisons in both orders). Every lesson runs offline; LangSmith and Groq cells are optional.
- **`mastery.evals`** gains `taxonomy`, `datasets`, `judges`, `gates` and `otel`; **`mastery.agents.support_traces`** generates the deterministic trace sets the lessons share.
- Lessons 10.05–10.08 and Project 10 follow in the next update.

## 2026-10-15 · Module 09 update

**Re-run after pulling:** Module 09 notebooks and Project 09 (the shared `mastery.agents` code changed; no new installs).

### Fixes you'll notice

- **Project 09 checks real work.** The acceptance checks now fail on the unfinished starter (0/9) and can't be passed with one-liners: Patterns A and B must be built with the handoff and subagent tools (not the reference builders), the manager policy is tested on extra probe payloads, and the ADR needs real sections and each pattern's own numbers. Steps 3, 4, 5 and 7 have collapsed hints (goal first, code if you're stuck).
- **Scoring checks outcomes.** `score()` compares the refunds actually issued (invoice, customer, amount, once each) and fails conversations that ran side-effect tools they didn't ask for. The test set gained `expect.refunds`.
- **Identity comes from the login.** New `SupportContext` runtime context: tools act only on the signed-in customer's account, whatever the chat says (new Lesson 09.02 Part 8; Exercise 2 rewritten; the custom refund workflow in 09.05 uses it too).
- **Parallel approvals are counted right:** two refunds reviewed in one pause now count as 2 reviews (`interrupts`) and 1 pause (`pauses`).
- **Lesson 09.03:** a loop guard (`max_handoffs`) hands a ping-ponging conversation to a human; the Exercise 4 solution is corrected.
- **Lesson 09.04:** new Part 4b on classifier confidence, thresholds and escalation to a human; Exercise 2's solution no longer shares one router thread between customers; Exercise 3's arithmetic is corrected (54 calls).
- **Lesson 09.05:** Exercise 3's arithmetic is corrected (38 calls).
- **All Module 09 lessons** end with a short docs drill.

## 2026-10-14 · v2026.10

**Re-run after pulling:** `python -m pip install -e ".[dev]"` (new optional `ci` extra and the `mastery.evals` package).

### Course order

- **Module 00:** your first model call now comes earlier. **00.05 First contact with Groq** (was 00.07), **00.06 Research skills** (was 00.05), **00.07 Provider decision framework** (was 00.06). The lessons were rewritten to read naturally in the new order.
- **Part 2:** evaluation now comes **before** Deep Agents, because building and judging deep agents needs evaluation skills. New order: **10 Testing, Evaluation & Observability** (was 12) → **11 Deep Agents** (was 10) → **12 Production & Deployment** (was 13) → electives **13 Multimodal & Voice** (was 11) and **14 Local Models & Fine-Tuning**. Lesson, lab and project numbers moved with their modules.
- **Part 2 plan upgraded** ([COURSE_OUTLINE.md](COURSE_OUTLINE.md)): Module 10 opens with error analysis and teaches statistics for small evals and judge calibration; Module 11 builds a mini-harness before `create_deep_agent`, separates evergreen lessons from dated "frontier briefings", and makes the labs "choose 1 of 3"; Module 12 runs agents as background jobs, adds OpenTelemetry, SLOs, an incident runbook, safe releases and a public deployment; Module 13 adds a voice-architecture lesson. **Capstones:** every capstone now needs a live URL or demo video, an error-analysis evaluation report, an ADR, a cost/latency budget and a write-up; new options **C7 Upstream contribution** and **C8 Bring your own problem**.

### Fixes you'll notice

- **Projects check real work.** Project 05's "no invented URLs" check and Project 06's acceptance checks no longer pass on an unfinished starter or on a system that always answers "I don't know" (Project 06 now scores runs with an independent reference scorer and requires real answers). Project 08's crash demo is labelled as a runtime demo and no longer counted as your work.
- **Project 06 / Lesson 06.06:** citations are checked more strictly (quotes of at least 12 characters, the right page, Markdown bold ignored), and the citation policy now fails closed: one fabricated citation turns the answer into "I don't know", because dropping only the bad citation let a false claim ship next to a valid one.
- **Project 01:** latency now measures the model, not the rate limiter's wait (`mastery.evals.timed_invoke`); the table reports the median and the maximum.
- **Lesson 02.03 + Project 02:** the `recursion_limit` rule is corrected (middleware hooks are graph nodes too); `mastery.agents.recursion_limit_for` computes the limit from the agent's graph, so the graceful `ModelCallLimitMiddleware` stop fires before `GraphRecursionError`.
- **Lessons 07.03 / 07.04:** parallel results are not merged "in completion order"; a new predict-then-run cell shows the difference between streamed order and final state, and the orchestrator now carries an index.
- **Lesson 08.03:** a resume value that makes a node raise "poisons" the thread; the exercise solution now shows the recovery and the `response_schema=` fix.
- **Project 08:** the clarify step is resume-safe (the model's verdict is computed once, in a task, so a resume can't drop your answer).
- **Module 09:** a manager's "edit" on a refund is validated like any other input (no more $1,990 refunds on a $199 invoice) and the audit log records what was actually refunded; a handoff requested in parallel with other tool calls is refused instead of leaving orphaned tool calls.
- **Lesson 04.01 / 04.03:** the async twin of every middleware hook, and why sync-only wrap hooks fail under `ainvoke`.
- **Lessons 00.03 and 00.07:** an exercise solution that crashed, and a provider-choice helper that skipped the data-terms check for sensitive data.
- **25 Markdown cells** that rendered as code blocks (headings missing from the table of contents) now render correctly.
- **Setup:** the install guide now describes what `.[dev]` really installs, gives honest time estimates, and tells `uv` users to create their env with `--seed` (otherwise `%pip` cells fail). Notebook setup cells always load **this** clone's `mastery` and warn if your env points at another copy.

### New

- `mastery.evals`: a small statistics kit (confidence intervals, paired comparisons, repeated runs, dev/test splits with leak checks), timing helpers and run metadata.
- [setup/LEARNER_WORKFLOW.md](setup/LEARNER_WORKFLOW.md): keep the course files pristine and work in a git-ignored `workspace/` folder, so updates never conflict with your notebooks.
- CI on every push: unit tests on Linux and Windows, then every notebook run with no keys.
- 🔎 **Docs drills** and goal-style hints (the goal is visible, the code is in a collapsed block) joined the lesson template in [CONVENTIONS.md](CONVENTIONS.md); lessons gain them as they are revised, starting with the Project 01, 02, 05, 06 and 08 hints changed in this update. The research log has a v2 template with a rubric ([docs/research-log.md](docs/research-log.md)).
- Honest time estimates in hours in the README.
