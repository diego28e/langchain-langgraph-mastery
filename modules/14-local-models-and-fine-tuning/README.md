# Module 14 — Local Models & Fine-Tuning (elective)

> **Part 2 — Pro (Modules 09–14)** · elective · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 14](../../COURSE_OUTLINE.md#module-14--local-models--fine-tuning-elective)

**Goals:** Run models locally for privacy/cost. Know when fine-tuning beats RAG + prompting (rarely) and how to do a small QLoRA experiment responsibly.

**Estimated time:** 1–1.5 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 14.01 | Local models with Ollama | `14-01-ollama-local-models.ipynb` | 📝 Planned |
| 14.02 | Hugging Face: Hub, Inference Providers, transformers | `14-02-hugging-face.ipynb` | 📝 Planned |
| 14.03 | When (and when not) to fine-tune | `14-03-when-to-fine-tune.ipynb` | 📝 Planned |
| 14.04 | QLoRA experiment on Colab + serving | `14-04-qlora-on-colab.ipynb` | 📝 Planned |

## Project

**Project 14 — Local-First Assistant + Fine-Tune Experiment**

Project files go in `project/`.

## Jupyter skill

Colab and VS Code notebooks.

## `src/mastery` increment

`mastery/models.py` gains `provider="ollama"` and `provider="hf"`.

## Research checkpoint

Check which current Ollama models support tool calling, and log the best one that fits your GPU/CPU. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 13](../13-production-and-deployment/) · [Course outline](../../COURSE_OUTLINE.md)
