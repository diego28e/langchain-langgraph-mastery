# Capstones

Capstones come after **Part 2 — Pro**. C1 and C3 can be started after **Part 1 — Core** in a simpler form and upgraded later.

Choose **2 of 8**. Full specs, "must have" requirements, and the 100-point rubric are in [COURSE_OUTLINE.md → Capstones](../COURSE_OUTLINE.md#capstones-choose-2-of-8).

A capstone is a problem statement, not a tutorial: before you build, write a short spec, the acceptance tests that define "done", and which artifact earns each rubric line. **Every capstone must have:** a live URL (Lesson 12.09) or a 3-minute demo video; an evaluation report that tells an error-analysis story (failure taxonomy from real traces → fixes → before vs after on a held-out set, with intervals); an ADR for the main design choice; a cost/latency budget with measured values; and a public write-up.

| ID | Capstone | Builds on modules | Status |
|---|---|---|---|
| C1 | Knowledge Assistant for a real document set | 03, 06, 08, 10, 12 | 📝 Planned |
| C2 | Voice Customer-Support Prototype | 04, 09, 10 + elective 13 | 📝 Planned |
| C3 | Research & Writing Agent (LangGraph) | 05, 07, 08, 09, 10 | 📝 Planned |
| C4 | Internal Tool with structured output and monitoring | 01, 02, 04, 10, 12 | 📝 Planned |
| C5 | MCP-powered Personal Ops Agent | 04, 05, 08, 12 | 📝 Planned |
| C6 | Long-Horizon Deep Agent for a real workflow (due-diligence pack, repo maintainer, or content pipeline) | 04, 05, 08, 10, 11, 12 | 📝 Planned |
| C7 | Upstream contribution (a merged or reviewed PR to LangChain / LangGraph / Deep Agents, or a published, tested MCP server) | 00, 05, 10 + the research skills from every module | 📝 Planned |
| C8 | Bring your own problem (you write the spec, acceptance tests, and rubric mapping first) | Your choice, justified in an ADR | 📝 Planned |

Folder convention: `capstones/cN-<slug>/` containing `README.md` (problem, architecture diagram, how to run), notebooks, app code, and `evals/`.
