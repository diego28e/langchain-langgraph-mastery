# Module 13 — Local Models & Fine-Tuning (elective)

> **Part 2 — Pro (Modules 09–13)** · elective · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 13](../../COURSE_OUTLINE.md#module-13--local-models--fine-tuning-elective)

**Goals:** Run models locally for privacy/cost. Know when fine-tuning beats RAG + prompting (rarely) and how to do a small QLoRA experiment responsibly.

**Estimated time:** 1–1.5 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 13.01 | Local models with Ollama | `13-01-ollama-local-models.ipynb` | 📝 Planned |
| 13.02 | Hugging Face: Hub, Inference Providers, transformers | `13-02-hugging-face.ipynb` | 📝 Planned |
| 13.03 | When (and when not) to fine-tune | `13-03-when-to-fine-tune.ipynb` | 📝 Planned |
| 13.04 | QLoRA experiment on Colab + serving | `13-04-qlora-on-colab.ipynb` | 📝 Planned |

## Project

**Project 13 — Local-First Assistant + Fine-Tune Experiment**

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

← [Module 12](../12-production-and-deployment/) · [Course outline](../../COURSE_OUTLINE.md)
