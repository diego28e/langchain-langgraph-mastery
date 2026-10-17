# Module 14 — Local Models & Fine-Tuning (elective)

> **Part 2 — Pro (Modules 09–14)** · elective · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 14](../../COURSE_OUTLINE.md#module-14--local-models--fine-tuning-elective)

**Goals:** Run models locally for privacy/cost. Know when fine-tuning beats RAG + prompting (rarely) and how to do a small QLoRA experiment responsibly.

**Estimated time:** 1–1.5 weeks.

**Hardware:** a CPU-only laptop is enough (integrated Intel/AMD graphics are fine): Ollama runs 4B models such as `qwen3:4b` on the CPU, slowly but usefully, and 32 GB of RAM fits up to `gpt-oss:20b` (a few tokens per second). Fine-tuning (14.04) runs on a free Google Colab GPU, never on your laptop. **Keys:** none required; `GROQ_API_KEY` for the comparisons, an optional `HF_TOKEN` for gated models.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 14.01 | Local models with Ollama | `14-01-ollama-local-models.ipynb` | ✅ Ready |
| 14.02 | Hugging Face: Hub, Inference Providers, transformers | `14-02-hugging-face.ipynb` | ✅ Ready |
| 14.03 | When (and when not) to fine-tune | `14-03-when-to-fine-tune.ipynb` | ✅ Ready |
| 14.04 | QLoRA experiment on Colab + serving | `14-04-qlora-on-colab.ipynb` | ✅ Ready |

## Project

**[Project 14 — Local-First Support Assistant and Ticket Router](project/README.md)**: Project 06's assistant on a local model vs the alternatives, and every ticket router from 14.03–14.04 (baselines, few-shot local and hosted, fine-tuned) on the same held-out tickets, with paired tests, a latency budget and a privacy column, ending in a recommendation. 8 acceptance checks; runs offline at $0.

## Jupyter skill

Colab and VS Code notebooks.

## `src/mastery` increment

`mastery/models.py` gains `provider="ollama"`; new `mastery/local/` (Ollama status, `measure`, `fits_in_memory`, Hub helpers) and `mastery/finetune/` (router dataset, numpy baselines, batched few-shot router, metrics, recorded runs).

## Research checkpoint

Check which current Ollama models support tool calling, and log the best one that fits your GPU/CPU. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

✅ Ready: Lessons 14.01–14.04 (14.04 trains on Colab: `colab/colab-qlora-router.ipynb`) and Project 14.

---

← [Module 13](../13-multimodal-and-voice/) · [Course outline](../../COURSE_OUTLINE.md)
