"""Module 13.04: the batch voice sandwich, sentence streaming and the voice-reply cleanup (offline)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mastery.voice import fix_ids, FakeSpeaker, FakeTranscriber, GraphAgent, ScriptedAgent, VoicePipeline, for_voice, read_wav, sentences

VM = json.loads((Path(__file__).resolve().parents[2] / "data" / "samples" / "multimodal" / "voicemails.json").read_text(encoding="utf-8"))
STT = {v["id"]: v["simulated_whisper"] for v in VM["voicemails"]}
REPLY = "First sentence is here. Second one follows now! Third? Fourth sentence is not spoken."


def test_for_voice_drops_citations_headings_and_extra_sentences() -> None:
    raw = "[data/samples/support-desk/faq/technical.md] ## Exporting data\nRestart the agent. Then retry. Then call. Then wait."
    assert for_voice(raw) == "Restart the agent. Then retry. Then call."


def test_sentences_groups_a_token_stream() -> None:
    tokens = iter(["Hi", " there.", " This is", " a test.", " end"])
    assert list(sentences(tokens, min_chars=3)) == ["Hi there.", "This is a test.", "end"]


@pytest.mark.parametrize("mode", ["sequential", "sentences"])
def test_pipeline_runs_and_times_every_stage(mode: str) -> None:
    pipe = VoicePipeline(FakeTranscriber(STT), ScriptedAgent(REPLY, think_s=0, tokens_per_s=1e6), [FakeSpeaker(max_chars=2000)])
    turn = pipe.run(None, key="vm-01", mode=mode)
    assert turn.transcript.simulated and "Nimbus" in turn.transcript.text
    assert turn.spoken.count(".") + turn.spoken.count("!") + turn.spoken.count("?") == 3
    assert set(turn.timings) == {"stt", "agent", "tts", "first_audio", "total"}
    assert read_wav(turn.speech.wav).seconds > 0 and turn.first_audio_s <= turn.timings["total"] + 1e-6


def test_sentence_mode_reaches_first_audio_sooner() -> None:
    slow_agent = ScriptedAgent(REPLY, think_s=0.05, tokens_per_s=40)
    speaker = [FakeSpeaker(seconds_per_request=0.02, seconds_per_char=0.001, max_chars=2000)]
    seq = VoicePipeline(FakeTranscriber(STT), slow_agent, speaker).run(None, key="vm-01")
    stream = VoicePipeline(FakeTranscriber(STT), slow_agent, speaker).run(None, key="vm-01", mode="sentences")
    assert stream.first_audio_s < seq.first_audio_s


def test_all_speakers_down_still_answers_in_text() -> None:
    turn = VoicePipeline(FakeTranscriber(STT), ScriptedAgent(REPLY, think_s=0, tokens_per_s=1e6),
                         [FakeSpeaker(fail="503")]).run(None, key="vm-02")
    assert turn.speech.wav is None and turn.spoken and "503" in turn.speech.errors[0]
    with pytest.raises(ValueError):
        VoicePipeline(FakeTranscriber(STT), None, []).run(None, key="vm-01", mode="realtime")


def test_graph_agent_with_the_offline_support_desk() -> None:
    from langgraph.checkpoint.memory import InMemorySaver

    from mastery.agents.support import SupportDesk, build_single_agent_desk, make_support_tools, offline_model

    app = build_single_agent_desk(offline_model(), make_support_tools(SupportDesk.load()), checkpointer=InMemorySaver())
    agent = GraphAgent(app)
    reply = agent.invoke("Customer C-1002: our team is locked out since the password reset.")
    assert "C-1002" in reply
    assert "".join(agent.stream("Thanks."))   # the same thread keeps going


def test_fix_ids() -> None:
    assert fix_ids("customer C1002 and c 2042, invoice INV 88412, C-1001") == "customer C-1002 and C-2042, invoice INV-88412, C-1001"
