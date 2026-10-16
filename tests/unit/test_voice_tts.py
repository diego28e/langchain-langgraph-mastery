"""Module 13.03 helpers: speakable text, 200-character chunks, quotas, speakers and fallbacks (offline)."""
from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace

import pytest

from mastery.voice import (
    BudgetExceeded,
    FakeSpeaker,
    GeminiSpeaker,
    OrpheusSpeaker,
    TtsBudget,
    normalize_for_speech,
    read_wav,
    speak_with_fallback,
    split_for_tts,
    stitch_wavs,
    tone,
)


def test_normalize_for_speech() -> None:
    out = normalize_for_speech("**Plan** for `C-1002`: US$349.00, or $12.50; COP 47.600. https://x.example/a")
    assert out == "Plan for C-1-0-0-2: 349 dollars, or 12 dollars and 50 cents; 47600 pesos. the link in our message"


def test_split_respects_limit_and_repeats_direction() -> None:
    text = "One short sentence. " + "word " * 120 + "end."
    chunks = split_for_tts(text, direction="[warm]")
    assert all(len(c) <= 200 and c.startswith("[warm] ") for c in chunks)
    assert " ".join(c.removeprefix("[warm] ") for c in chunks).split() == text.split()
    assert split_for_tts("Hi. There.") == ["Hi. There."]
    with pytest.raises(ValueError):
        split_for_tts("x", max_chars=25, direction="[a very long direction here]")


def test_budget_minute_and_day_limits() -> None:
    now = [0.0]
    budget = TtsBudget(rpm=2, rpd=3, tpm=1000, tpd=10_000, clock=lambda: now[0])
    budget.check(["a", "b"])
    for c in ("a", "b"):
        budget.record(c)
    with pytest.raises(BudgetExceeded) as minute:
        budget.check(["c"])
    assert 0 < minute.value.wait_s <= 60
    now[0] = 61
    budget.record("c")
    with pytest.raises(BudgetExceeded, match="daily") as day:
        budget.check(["d"])
    assert day.value.wait_s == float("inf") and budget.remaining()["requests_today"] == 0
    with pytest.raises(BudgetExceeded, match="never fit"):
        TtsBudget(rpm=1).check(["a", "b"])


def test_orpheus_speaker_chunks_records_and_stitches() -> None:
    sent = []

    def create(**params):
        sent.append(params)
        return SimpleNamespace(read=lambda: tone(seconds=0.4, rate=24_000).to_wav())

    client = SimpleNamespace(audio=SimpleNamespace(speech=SimpleNamespace(create=create)))
    budget = TtsBudget()
    spk = OrpheusSpeaker("canopylabs/orpheus-v1-english", "troy", direction="[friendly]", budget=budget, client=client)
    result = spk.speak("Hello there. " * 30)
    assert result.chunks == len(sent) >= 2 and all(len(p["input"]) <= 200 for p in sent)
    assert sent[0]["response_format"] == "wav" and sent[0]["voice"] == "troy"
    assert budget.remaining()["requests_today"] == 100 - len(sent)
    assert read_wav(result.wav).seconds > 0.4 * len(sent) and result.cost_usd > 0
    with pytest.raises(ValueError):
        OrpheusSpeaker(voice="Kore", client=client)


def test_gemini_speaker_one_request() -> None:
    calls = []

    def create(**body):
        calls.append(body)
        return SimpleNamespace(output_audio=SimpleNamespace(data=base64.b64encode(tone(seconds=1).to_wav()).decode()))

    spk = GeminiSpeaker("gemini-3.8-flash-lite-tts", "Kore", style="calm", client=SimpleNamespace(interactions=SimpleNamespace(create=create)))
    result = spk.speak("Hola. " * 60)
    assert len(calls) == 1 and result.chunks == 1 and result.cost_usd == 0.0


def test_fallback_chain_and_cache(tmp_path: Path) -> None:
    broken, ok = FakeSpeaker("broken", fail="503 Service Unavailable"), FakeSpeaker("fake")
    result = speak_with_fallback("Your ticket is open.", [broken, ok], cache_dir=tmp_path)
    assert result.provider == "fake" and result.simulated and "503" in result.errors[0]
    text_only = speak_with_fallback("Your ticket is open.", [broken])
    assert text_only.wav is None and text_only.provider == "text-only" and text_only.text
    assert not list(tmp_path.iterdir())   # simulated audio is never cached


def test_stitch_resamples_to_first_rate() -> None:
    wav = stitch_wavs([tone(seconds=0.5, rate=24_000).to_wav(), tone(seconds=0.5, rate=16_000).to_wav()])
    clip = read_wav(wav)
    assert clip.rate == 24_000 and clip.seconds == pytest.approx(1.12, abs=0.01)


def test_orpheus_terms_not_accepted_is_a_clear_error_and_falls_through() -> None:
    from mastery.voice import ModelTermsRequired

    def create(**params):
        raise RuntimeError("Error code: 400 - {'error': {'message': 'The model canopylabs/orpheus-v1-english requires "
                           "terms acceptance.', 'code': 'model_terms_required'}}")

    client = SimpleNamespace(audio=SimpleNamespace(speech=SimpleNamespace(create=create)))
    spk = OrpheusSpeaker("canopylabs/orpheus-v1-english", "troy", client=client)
    with pytest.raises(ModelTermsRequired, match="console.groq.com/playground"):
        spk.speak("Hello.")
    out = speak_with_fallback("Hello.", [spk, FakeSpeaker("backup")])
    assert out.provider == "backup" and "model_terms_required" in out.errors[0]
