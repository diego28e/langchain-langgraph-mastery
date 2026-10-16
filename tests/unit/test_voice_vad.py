"""Lesson 13.05: energy VAD, endpointing, partial transcripts, barge-in, latency budget."""

from mastery.voice import (
    EnergyVad,
    Endpointer,
    LatencyBudget,
    PartialTranscripts,
    Playback,
    frame_energy,
    frames,
    silence,
    speech_clip,
)


def test_frames_and_energy():
    clip = silence(1.0)
    assert len(list(frames(clip, 20))) == 50
    assert frame_energy(clip.samples[:320]) == -120.0


def test_endpointer_finds_one_turn_with_a_short_pause_inside():
    clip = speech_clip([("silence", 0.5), ("speech", 1.0), ("silence", 0.3), ("speech", 0.8), ("silence", 1.0)])
    events = Endpointer(silence_ms=600).run(clip)
    assert [e.kind for e in events] == ["speech_start", "end_of_turn"]
    assert 0.4 <= events[0].at_s <= 0.7
    assert 3.1 <= events[1].at_s <= 3.3  # speech ends at 2.6 s + 600 ms


def test_short_silence_setting_cuts_the_caller_in_two():
    clip = speech_clip([("silence", 0.5), ("speech", 1.0), ("silence", 0.3), ("speech", 0.8), ("silence", 1.0)])
    events = Endpointer(silence_ms=200).run(clip)
    assert [e.kind for e in events].count("end_of_turn") == 2


def test_click_is_not_speech():
    clip = speech_clip([("silence", 0.5), ("speech", 0.04), ("silence", 1.0)])
    assert Endpointer(min_speech_ms=100).run(clip) == []


def test_noise_floor_adapts():
    clip = speech_clip([("silence", 2.0)], noise_db=-40)
    vad = EnergyVad()
    decisions = [vad.is_speech(f) for f in frames(clip)]
    assert sum(decisions[-20:]) == 0


def test_partials_revise_and_final_is_exact():
    text = "please unlock account C-1001"
    out = list(PartialTranscripts(text, revise={"account": "a count"}).stream())
    assert out[-1] == (out[-1][0], text, True)
    assert any("a count" in p for _, p, final in out if not final)
    assert all(not final for _, _, final in out[:-1])


def test_barge_in_stops_playback():
    pb = Playback(["one", "two", "three", "four"], seconds_per_chunk=1.0)
    assert pb.play(interrupt_at_s=1.5) == ["one", "two"]
    assert pb.unheard == ["three", "four"]
    assert pb.cancelled_at_s == 2.0


def test_latency_budget_report():
    rows = LatencyBudget({"endpoint": 600, "stt": 300}).report({"endpoint": 600, "stt": 450})
    assert rows[1]["ok"] is False and rows[-1]["measured ms"] == 1050 and rows[-1]["ok"] is False


def test_speech_over_steady_noise_is_still_found():
    clip = speech_clip([("silence", 0.5), ("speech", 1.0), ("silence", 1.0)], noise_db=-40)
    assert [e.kind for e in Endpointer().run(clip)] == ["speech_start", "end_of_turn"]
