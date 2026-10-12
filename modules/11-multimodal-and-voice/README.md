# Module 11 — Multimodal & Voice

> **Part 2 — Pro (Modules 09–14)** · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 11](../../COURSE_OUTLINE.md#module-11--multimodal--voice)

**Goals:** Send images and PDFs to models, transcribe speech with Groq Whisper, synthesize speech with Groq Orpheus, and build the STT → agent → TTS "sandwich".

**Estimated time:** 1.5 weeks.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 11.01 | Multimodal input: images and PDFs | `11-01-multimodal-input.ipynb` | 📝 Planned |
| 11.02 | Speech-to-text with Groq Whisper | `11-02-speech-to-text.ipynb` | 📝 Planned |
| 11.03 | Text-to-speech with Orpheus | `11-03-text-to-speech.ipynb` | 📝 Planned |
| 11.04 | The voice agent "sandwich" | `11-04-voice-agent-sandwich.ipynb` | 📝 Planned |

## Production notes

> ⚠️ **Production note: this module uses two Groq preview models.**
> Vision (`qwen/qwen3.8-27b`) and TTS (`canopylabs/orpheus-v1-english`) are previews: evaluation only, no migration guarantee, and they can be retired at short notice. The course accepts that because they are cheap and fast to learn with, and each lesson has a fallback (vision → the paid benchmark model, which accepts image input; TTS → text-only answer). In production: choose GA vision and TTS models with an SLA, pin model IDs, cache generated audio, monitor errors and per-character cost, and test the fallback path in CI.

## Project

**Project 11 — Voice Q&A Agent**: Ask questions about your knowledge base by voice and hear the answer.

Project files go in `project/`.

## Jupyter skill

`IPython.display.Audio` and `ipywidgets` uploads.

## `src/mastery` increment

`mastery/voice/` (`transcribe()`, `speak()` with chunking, `VoicePipeline`).

## Research checkpoint

Re-check Groq's TTS model list and voices. Log whether Orpheus is still preview and whether any new voice/language exists. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

📝 Planned. No notebooks yet.

---

← [Module 10](../10-deep-agents/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 12](../12-testing-evaluation-observability/) →
