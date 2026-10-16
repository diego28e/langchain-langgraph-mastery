# Course changelog

What changed in the course, newest first. After you pull an update ([setup/LEARNER_WORKFLOW.md](setup/LEARNER_WORKFLOW.md)), skim the latest entry: it says which lessons changed and whether you need to re-run anything.

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
