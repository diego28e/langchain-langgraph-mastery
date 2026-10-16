"""Voice helpers for Module 13: audio basics, speech-to-text, text-to-speech. Introduced in Lesson 13.02; text-to-speech in 13.03; the pipeline in 13.04; turn-taking (VAD, barge-in) in 13.05.

Nothing here calls a provider on import; Groq and Google SDKs are imported only when you create a
real transcriber or synthesize speech.
"""
from mastery.voice.audio import AudioClip, chunk, concat, read_wav, silence, tone, wav_size_bytes, with_noise
from mastery.voice.pipeline import GraphAgent, ScriptedAgent, VoicePipeline, VoiceTurn, fix_ids, for_voice, sentences
from mastery.voice.stt import (
    WHISPER_PRICE_PER_HOUR,
    FakeTranscriber,
    GroqTranscriber,
    Segment,
    Transcriber,
    Transcript,
    flag_segments,
    normalize_words,
    parse_verbose_json,
    transcribe_long,
    wer,
    whisper_cost,
)
from mastery.voice.vad import (
    EnergyVad,
    Endpointer,
    LatencyBudget,
    PartialTranscripts,
    Playback,
    TurnEvent,
    frame_energy,
    frames,
    speech_clip,
)
from mastery.voice.tts import (
    ORPHEUS_VOICES,
    BudgetExceeded,
    FakeSpeaker,
    GeminiSpeaker,
    ModelTermsRequired,
    OrpheusSpeaker,
    Speaker,
    SpeechResult,
    TtsBudget,
    cached_audio,
    gemini_tts,
    normalize_for_speech,
    speak_with_fallback,
    split_for_tts,
    stitch_wavs,
)

__all__ = [
    "ORPHEUS_VOICES", "BudgetExceeded", "FakeSpeaker", "GeminiSpeaker", "ModelTermsRequired", "OrpheusSpeaker", "Speaker", "SpeechResult",
    "TtsBudget", "normalize_for_speech", "speak_with_fallback", "split_for_tts", "stitch_wavs",
    "GraphAgent", "ScriptedAgent", "VoicePipeline", "VoiceTurn", "fix_ids", "for_voice", "sentences",
    "AudioClip", "FakeTranscriber", "GroqTranscriber", "Segment", "Transcriber", "Transcript",
    "WHISPER_PRICE_PER_HOUR", "cached_audio", "chunk", "concat", "flag_segments", "gemini_tts",
    "normalize_words", "parse_verbose_json", "read_wav", "silence", "tone", "transcribe_long",
    "wav_size_bytes", "wer", "whisper_cost", "with_noise",
    "EnergyVad", "Endpointer", "LatencyBudget", "PartialTranscripts", "Playback", "TurnEvent", "frame_energy",
    "frames", "speech_clip",
]
