# Project 13 — Voice Support Line for Orbita Cloud

> **Module 13 · Multimodal & Voice** · elective · ⏱️ 4–6 hours · Docs verified 2026-10-16

**The job:** Orbita Cloud's support line takes voicemails all night. You build the service that answers them: transcribe the message, refuse to guess on a bad line, answer from the product documentation (the Project 06 corpus) with verified citations, reply in the caller's language with a voice that speaks it, survive a TTS outage, and file a ticket with the transcript, the answer, its sources and per-stage timings. Then you write the report your support lead reads before switching it on.

| File | What it is |
|---|---|
| [`13-project-voice-support-line.ipynb`](13-project-voice-support-line.ipynb) | **Starter.** Runs top to bottom from the start. Five `# TODO` blocks, each with a collapsed goal-style hint |
| [`solutions/13-project-voice-support-line-solution.ipynb`](solutions/13-project-voice-support-line-solution.ipynb) | **Reference solution.** Same cells, same order. Open it after you have tried |
| [`data/samples/multimodal/project13-calls.json`](../../../data/samples/multimodal/project13-calls.json) | Six synthetic calls: scripts (ground truth), voices, expected sources, and clearly labelled simulated Whisper responses for offline runs |
| [`src/mastery/voice/`](../../../src/mastery/voice/) · [`src/mastery/rag/`](../../../src/mastery/rag/) | Whisper, speakers and fallbacks, `for_voice`, `LatencyBudget` (Lessons 13.02–13.05); BM25, the extractive reader and `verify_citations` (Module 06) |

Outputs go to the git-ignored `data/outputs/m13/`: `project13-tickets.json`, `project13-report.md`, `project13-acceptance.json`, and the generated audio in `audio/`.

## Requirements

1. **Speech-to-text:** Groq `whisper-large-v3-turbo` with the hint terms; the language comes from Whisper.
2. **Bad lines:** flagged segments (Lesson 13.02) or no question heard → "please repeat", never an answer.
3. **Retrieval in the corpus language:** a Spanish call is translated to English with `whisper-large-v3` for retrieval, and answered in Spanish.
4. **Answers with evidence:** 5 chunks from the Project 06 corpus, a structured `CitedAnswer`, and only citations that `verify_citations` accepts. Unknown questions become a callback ticket.
5. **Speech:** a listenable reply (two sentences, no Markdown or file names), spoken by Gemini TTS with Orpheus as English-only backup and text as the last resort; Orpheus never speaks Spanish.
6. **Ticket and timings:** transcript, route, answer, citations, speaker, errors and `stt` / `answer` / `tts` / `first_audio` milliseconds.
7. **Report:** pipeline, calls, latency against a budget, production notes and privacy, as Markdown.

| TODO | Where | What |
|---|---|---|
| 1 | Step 2 | `needs_repeat(transcript)`: don't guess on a bad line |
| 2 | Step 2 | `answer_call(question, lang, call)`: retrieve, read, keep only verified citations |
| 3 | Step 2 | `spoken_reply(answer, lang)`: listenable text, callback when unknown |
| 4 | Step 2 | `speakers_for(lang)`: a voice that speaks the caller's language |
| 5 | Step 5 | `write_report(path, evidence)` |

## Acceptance checks

The notebook ends with 8 checks: the 5 answerable calls answered end to end with the right fact; TTS chunks within 200 characters that never cut a word; a per-stage latency table against the budget; a TTS outage that still returns the text answer; the noisy call routed to "ask to repeat"; the Spanish question answered in Spanish and not by an English-only voice; verified citations from the expected document and none of them spoken; and a report with the batch-pipeline, preview-model and privacy notes. The untouched starter passes 2/8 (chunking and the latency table come from the course library).

## Modes

Everything runs **offline** at $0: simulated transcripts from the JSON, the extractive reader, and simulated speakers, all labelled. With `GROQ_API_KEY` (and `GOOGLE_API_KEY` the first time, to synthesize the six calls with Gemini TTS; cached afterwards) the same notebook runs live: about 10–15K Groq tokens, a minute of Whisper audio, and 6 Gemini TTS requests. Orpheus needs its terms accepted once in the [Groq playground](https://console.groq.com/playground?model=canopylabs%2Forpheus-v1-english); until then the chain skips it.

> ⚠️ **Production note: a batch pipeline on preview models.**
> This line handles **voicemail**: whole recordings, then an answer. A live phone line needs streaming STT/TTS, endpointing and barge-in (Lesson 13.05). Orpheus and the Gemini TTS models are previews: pin the model IDs, keep the text fallback, and watch daily quotas.

> ⚠️ **Privacy note:** every call here is synthetic. Real calls are personal data: announce the assistant and the recording, keep transcripts rather than audio for a stated retention period, and don't send real customer audio to free tiers that may use it to improve their products.

## Rubric (self-assessment)

| Criterion | ✅ Meets | ⭐ Exceeds |
|---|---|---|
| Pipeline | All six calls routed correctly, offline and live | Your own recorded question (consented) through the line, with its WER |
| Safety | Bad lines and unknown questions never guessed | A confidence threshold tuned on 10 extra noisy clips, with the trade-off written down |
| Evidence | Only verified citations, none spoken | The ticket links each citation to the exact chunk (`ChunkCitedAnswer`) |
| Voice | Right language, listenable replies, outage drill passes | A/B of two voices with three listeners, result recorded |
| Report | Measured numbers, all five sections | A streaming estimate: which stages 13.05's architecture would cut, by how much |
| Hygiene | 8/8 checks; Restart & Run All passes without a key; outputs cleared | README with a privacy note and known limits |

## Use-case variants (pick one instead, same acceptance)

- **Meeting summarizer:** a 10-minute recording → `transcribe_long` → summary with timestamps → spoken digest.
- **Language tutor:** a learner speaks Spanish; Whisper translation checks meaning, Gemini TTS replies with corrections.
- **Accessibility reader:** a PDF from Lesson 13.01 read aloud in chunks, with "repeat" and "next" commands.

## Stretch

- Upload or record from the browser (a static page like Module 12's UI) and play the answer.
- Sentence streaming (Lesson 13.04) and the `Endpointer` from 13.05 on a live microphone recording.
- Answer with the Project 09 desk (tools, caller ID) when the question is about the caller's own account.
