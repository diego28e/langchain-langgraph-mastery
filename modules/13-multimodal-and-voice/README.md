# Module 13 — Multimodal & Voice (elective)

> **Part 2 — Pro (Modules 09–14)** · elective (take it any time after Module 02; capstone C2 requires it) · Full lesson specs, reading lists, and project acceptance criteria: [COURSE_OUTLINE.md → Module 13](../../COURSE_OUTLINE.md#module-13--multimodal--voice-elective)

**Keys:** `GROQ_API_KEY` (vision, Whisper, Orpheus) and, recommended, a free `GOOGLE_API_KEY` from [AI Studio](https://aistudio.google.com/apikey) (native PDF, audio and video input, multilingual TTS). Every lesson runs offline without them. **Orpheus (13.03–13.04) needs one extra step:** an org admin must accept its terms once in the [Groq playground](https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english); until then Groq answers `400 model_terms_required` and the lessons fall back to Gemini.

**Goals:** Go beyond the image basics of Lesson 01.02: send documents, audio, and video to multimodal models and decide when vision beats text extraction; transcribe speech with Groq Whisper; synthesize speech with Groq Orpheus; build a simplified, batch STT → agent → TTS "sandwich"; and learn the architecture of real-time voice agents (latency budgets, streaming, turn-taking, barge-in, speech-to-speech models, telephony), so you know exactly what the course pipeline leaves out.

**Estimated time:** about 16–21 h (≈ 2–2.5 weeks at 8 h/week).

> **Be clear about what you build here:** the course's voice pipeline is a **simplified batch version** (record a whole question, transcribe it, answer, then speak). Production voice agents stream every stage and handle interruptions; Lesson 13.05 teaches that architecture and has you measure how far the batch version is from it.

## Lessons

| Lesson | Title | Notebook | Status |
|---|---|---|---|
| 13.01 | Documents and vision: PDFs, scans and receipts | `13-01-documents-and-vision.ipynb` | ✅ Ready |
| 13.02 | Speech-to-text with Groq Whisper: voicemails to tickets | `13-02-speech-to-text.ipynb` | ✅ Ready |
| 13.03 | Text-to-speech: Orpheus and Gemini TTS for a support line | `13-03-text-to-speech.ipynb` | ✅ Ready |
| 13.04 | The voice agent sandwich: STT → support agent → TTS (batch version) | `13-04-voice-agent-sandwich.ipynb` | ✅ Ready |
| 13.05 | Voice architecture: latency budgets, streaming, turn-taking, and telephony | `13-05-voice-architecture.ipynb` | ✅ Ready |

## Production notes

> ⚠️ **Production note: this module uses two Groq preview models.**
> Vision (`qwen/qwen3.8-27b`) and TTS (`canopylabs/orpheus-v1-english`) are previews: evaluation only, no migration guarantee, and they can be retired at short notice. The course accepts that because they are cheap and fast to learn with, and each lesson has a fallback (vision and documents → Gemini on the free tier; TTS → Gemini TTS or a text-only answer).

> ⚠️ **Production note: free tiers are for synthetic data.**
> This module uses Gemini's free tier (`GOOGLE_API_KEY`) for PDFs, audio and speech. Google may use free-tier content to improve its products, so the course only sends the synthetic samples in `data/samples/multimodal/`. Real invoices, receipts and customer calls need a paid tier or another provider with a data agreement. In production: choose GA vision and TTS models with an SLA, pin model IDs, cache generated audio, monitor errors and per-character cost, and test the fallback path in CI.

## Project

**[Project 13 — Voice Support Line for Orbita Cloud](project/README.md)**: voicemails transcribed, answered from the Project 06 documentation with verified citations, spoken back in the caller's language, and filed as tickets with per-stage timings. 8 acceptance checks; runs offline at $0.

## Jupyter skill

`IPython.display.Audio` and `ipywidgets` uploads.

## `src/mastery` increment

`mastery/voice/` (`transcribe()`, `speak()` with chunking, `VoicePipeline`).

## Research checkpoint

Re-check Groq's TTS model list and voices. Log whether Orpheus is still preview and whether any new voice/language exists. Log your findings in [`docs/research-log.md`](../../docs/research-log.md).

## Status

✅ Ready: Lessons 13.01–13.05 and Project 13.

---

← [Module 12](../12-production-and-deployment/) · [Course outline](../../COURSE_OUTLINE.md) · [Module 14](../14-local-models-and-fine-tuning/) →
