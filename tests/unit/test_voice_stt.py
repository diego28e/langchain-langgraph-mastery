"""Module 13.02 helpers: WAV handling, chunking, Whisper parsing, WER, cost, fake transcriber (offline)."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from mastery.voice import (
    AudioClip,
    FakeTranscriber,
    GroqTranscriber,
    cached_audio,
    chunk,
    concat,
    flag_segments,
    gemini_tts,
    parse_verbose_json,
    read_wav,
    silence,
    tone,
    transcribe_long,
    wav_size_bytes,
    wer,
    whisper_cost,
    with_noise,
)

VOICEMAILS = json.loads(
    (Path(__file__).resolve().parents[2] / "data" / "samples" / "multimodal" / "voicemails.json").read_text(encoding="utf-8")
)


def test_wav_round_trip_resample_and_stereo_mixdown(tmp_path: Path) -> None:
    clip = tone(440, 1.0, rate=24_000)
    back = read_wav(clip.to_wav(16_000))
    assert back.rate == 16_000 and abs(back.seconds - 1.0) < 0.01
    assert abs(back.rms_db() - clip.rms_db()) < 1.0
    import wave

    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(8000)
        w.writeframes(np.zeros(1600, dtype="<i2").tobytes())
    assert read_wav(path).seconds == pytest.approx(0.1)
    assert silence(1).rms_db() == -120.0
    assert with_noise(silence(1), 10).rms_db() > -60


def test_size_math_and_chunks_overlap() -> None:
    assert wav_size_bytes(60) == 44 + 60 * 16_000 * 2
    long = concat(tone(seconds=5), silence(5), tone(seconds=5))
    parts = chunk(long, 6, 1)
    assert [s for s, _ in parts] == [0.0, 5.0, 10.0]
    assert all(p.seconds <= 6 for _, p in parts) and parts[-1][1].seconds == pytest.approx(5)
    with pytest.raises(ValueError):
        chunk(long, 1, 1)
    with pytest.raises(ValueError):
        concat(tone(rate=8000), tone())


def test_wer_ignores_case_punctuation_and_hyphens() -> None:
    assert wer("Customer C-1002, please.", "customer c 1002 please") == 0.0
    assert wer("a b c d", "a x c") == 0.5
    assert wer("", "") == 0.0


def test_cost_has_a_ten_second_minimum() -> None:
    assert whisper_cost(3) == whisper_cost(10) == pytest.approx(10 / 3600 * 0.04)
    assert whisper_cost(3600, "whisper-large-v3") == pytest.approx(0.111)


def test_flags_noise_hallucination_and_loops() -> None:
    t = parse_verbose_json(VOICEMAILS["simulated_noise_only"])
    ((seg, why),) = flag_segments(t)
    assert "no speech" in why and seg.text == "Thank you for watching."
    loop = parse_verbose_json({"text": "x", "segments": [{"start": 0, "end": 1, "text": "x", "compression_ratio": 3.1}]})
    assert "repetitive" in flag_segments(loop)[0][1]


def test_fake_transcriber_prompt_variant_lowers_wer() -> None:
    fake = FakeTranscriber({v["id"]: v["simulated_whisper"] for v in VOICEMAILS["voicemails"]})
    for vm in VOICEMAILS["voicemails"]:
        plain, hinted = fake.transcribe(key=vm["id"]), fake.transcribe(key=vm["id"], prompt="Orbita Cloud")
        assert plain.simulated and wer(vm["script"], hinted.text) < wer(vm["script"], plain.text)


def test_transcribe_long_shifts_and_deduplicates() -> None:
    def scripted(key: str) -> dict:
        i = int(key.split("#")[1])
        # Chunk i re-hears the previous chunk's tail in its first second (the overlap), then new words.
        segs = [{"start": 0.5, "end": 1.0, "text": f"tail {i - 1}"}] if i else []
        segs.append({"start": 1.2 if i else 0.0, "end": 4.0, "text": f"part {i}"})
        if i < 2:
            segs.append({"start": 4.5, "end": 6.0, "text": f"tail {i}"})
        return {"text": "", "segments": segs}

    long = concat(tone(seconds=5), silence(5), tone(seconds=5))
    t = transcribe_long(long, FakeTranscriber(scripted), max_seconds=6, overlap_seconds=1, key="x")
    assert [s.text for s in t.segments] == ["part 0", "tail 0", "part 1", "tail 1", "part 2"]
    assert t.segments[-1].start == pytest.approx(11.2) and t.simulated


def test_groq_transcriber_sends_verbose_json_with_a_fake_client() -> None:
    seen = {}

    def create(**params):
        seen.update(params)
        return SimpleNamespace(to_dict=lambda: {"text": " hi", "segments": [{"start": 0, "end": 1, "text": " hi"}]})

    client = SimpleNamespace(audio=SimpleNamespace(transcriptions=SimpleNamespace(create=create)))
    t = GroqTranscriber("whisper-large-v3-turbo", client=client).transcribe(tone(seconds=2), prompt="Orbita", language="en")
    assert t.text == "hi" and t.duration == pytest.approx(2.0)
    assert seen["response_format"] == "verbose_json" and seen["timestamp_granularities"] == ["word", "segment"]
    assert seen["file"][0] == "audio.wav" and seen["language"] == "en"
    with pytest.raises(ValueError, match="large-v3"):
        GroqTranscriber("whisper-large-v3-turbo", translate=True, client=client)


def test_gemini_tts_request_shape_and_cache(tmp_path: Path) -> None:
    import base64

    seen = {}

    def create(**body):
        seen.update(body)
        return SimpleNamespace(output_audio=SimpleNamespace(data=base64.b64encode(tone(seconds=0.5).to_wav()).decode()))

    client = SimpleNamespace(interactions=SimpleNamespace(create=create))
    make = lambda: gemini_tts("Hola", voice="Kore", style="friendly", sample_rate=16_000, client=client)  # noqa: E731
    data, cached = cached_audio(tmp_path / "a.wav", make)
    assert not cached and read_wav(data).rate == 16_000
    assert seen["response_format"]["sample_rate"] == 16_000
    assert seen["input"][0]["content"][0]["annotations"][0]["style"] == "friendly"
    assert seen["generation_config"] == {"speech_config": [{"voice": "Kore"}]}
    assert cached_audio(tmp_path / "a.wav", make)[1] is True
