"""Audio stream simulator: TTS synthesis + speech style + chunked streaming."""

from __future__ import annotations

import asyncio
import struct
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import numpy as np

from ..core.interfaces import AudioChunk, SimulationLayer


@dataclass
class AudioConfig:
    """Configuration for the audio stream simulator."""

    sample_rate: int = 16000
    chunk_ms: int = 20
    sample_width: int = 2  # bytes per sample (16-bit PCM)
    tts_provider: str = "builtin"  # "azure", "google", "elevenlabs", "builtin"
    voice_profiles: dict[str, Any] = field(default_factory=dict)


class TTSEngine:
    """
    Text-to-speech engine abstraction.

    In test mode this generates synthetic sine-wave audio so that the
    framework can run without external TTS service credentials.
    """

    def __init__(self, provider: str = "builtin"):
        self.provider = provider

    async def synthesize(
        self,
        text: str,
        voice: str = "default",
        speed: float = 1.0,
        emotion: str = "neutral",
        sample_rate: int = 16000,
    ) -> bytes:
        """Synthesize speech from text, returning raw PCM bytes."""
        if self.provider == "builtin":
            return self._generate_synthetic(text, speed, sample_rate)
        # For real providers, delegate to their SDK (not implemented in test mode)
        return self._generate_synthetic(text, speed, sample_rate)

    @staticmethod
    def _generate_synthetic(
        text: str, speed: float, sample_rate: int
    ) -> bytes:
        """Generate a deterministic sine-wave standing in for real speech.

        Duration is proportional to text length (rough approximation of
        natural speech cadence).
        """
        chars = len(text)
        duration = max(0.5, chars * 0.08 / speed)  # ~80ms per character
        num_samples = int(sample_rate * duration)
        t = np.linspace(0, duration, num_samples, dtype=np.float32)
        # 440 Hz tone modulated by text hash for variety
        freq = 200 + (hash(text) % 300)
        signal = (np.sin(2 * np.pi * freq * t) * 16000).astype(np.int16)
        return signal.tobytes()


class VoiceBank:
    """Stores named voice profiles for multi-speaker simulation."""

    def __init__(self, profiles: dict[str, Any] | None = None):
        self.profiles = profiles or {}

    def get_voice(self, name: str) -> dict[str, Any]:
        return self.profiles.get(name, {})


class AudioStreamSimulator:
    """
    Simulate a real microphone input stream.

    - TTS synthesis and pre-recorded audio
    - Realistic speech characteristics: speed, pauses, fillers, accent
    - Chunked streaming at real sample-rate cadence
    """

    def __init__(self, config: AudioConfig | None = None, **kwargs: Any):
        if config is None:
            config = AudioConfig(**kwargs)
        self.sample_rate = config.sample_rate
        self.chunk_duration_ms = config.chunk_ms
        self.sample_width = config.sample_width
        self.tts_engine = TTSEngine(config.tts_provider)
        self.voice_bank = VoiceBank(config.voice_profiles)
        self._clock: Any = None

    def set_clock(self, clock: Any) -> None:
        self._clock = clock

    def _now(self) -> float:
        if self._clock is not None:
            return self._clock.now()
        return 0.0

    async def generate(
        self,
        text: str | None = None,
        audio_file: str | None = None,
        style: dict[str, Any] | None = None,
    ) -> AsyncIterator[AudioChunk]:
        """Generate an audio stream from text or a pre-recorded file."""
        style = style or {}

        if text and text.startswith("tts://"):
            raw_audio = await self.tts_engine.synthesize(
                text=text[6:],
                voice=style.get("voice", "default"),
                speed=style.get("speed", 1.0),
                emotion=style.get("emotion", "neutral"),
                sample_rate=self.sample_rate,
            )
        elif text:
            raw_audio = await self.tts_engine.synthesize(
                text=text,
                voice=style.get("voice", "default"),
                speed=style.get("speed", 1.0),
                emotion=style.get("emotion", "neutral"),
                sample_rate=self.sample_rate,
            )
        elif audio_file:
            raw_audio = _load_audio_file(audio_file, self.sample_rate)
        else:
            return

        # Apply speech style transformations
        if style:
            raw_audio = self._apply_speech_style(raw_audio, style)

        # Stream in chunks (simulate real microphone sampling)
        chunk_bytes = int(
            self.sample_rate * self.chunk_duration_ms / 1000
        ) * self.sample_width
        for i in range(0, len(raw_audio), chunk_bytes):
            chunk_data = raw_audio[i : i + chunk_bytes]
            yield AudioChunk(
                data=chunk_data,
                timestamp=self._now(),
                sample_rate=self.sample_rate,
            )
            await asyncio.sleep(self.chunk_duration_ms / 1000)

    # -- speech style transforms ---------------------------------------------

    def _apply_speech_style(self, audio: bytes, style: dict[str, Any]) -> bytes:
        """Apply simulated speech characteristics to raw PCM audio."""
        samples = np.frombuffer(audio, dtype=np.int16).copy()

        if style.get("speed") and style["speed"] != 1.0:
            samples = _resample(samples, style["speed"])

        if style.get("hesitation"):
            samples = _insert_fillers(samples, self.sample_rate)

        if style.get("interruption"):
            samples = _trim_leading_silence(samples, max_ms=50, sr=self.sample_rate)

        if style.get("volume"):
            factor = style["volume"]
            samples = np.clip(samples * factor, -32768, 32767).astype(np.int16)

        return samples.tobytes()


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _load_audio_file(path: str, target_sr: int) -> bytes:
    """Load a WAV file and return raw PCM bytes at the target sample rate."""
    import wave

    with wave.open(path, "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    return raw


def _resample(samples: np.ndarray, speed: float) -> np.ndarray:
    """Crude resampling to change speech speed."""
    indices = np.round(np.arange(0, len(samples), speed)).astype(int)
    indices = indices[indices < len(samples)]
    return samples[indices]


def _insert_fillers(samples: np.ndarray, sr: int) -> np.ndarray:
    """Insert small silence gaps to simulate hesitation."""
    filler_samples = int(sr * 0.15)  # 150ms silence
    filler = np.zeros(filler_samples, dtype=np.int16)
    # Insert a filler roughly every 2 seconds of audio
    chunk_size = sr * 2
    parts: list[np.ndarray] = []
    for i in range(0, len(samples), chunk_size):
        parts.append(samples[i : i + chunk_size])
        parts.append(filler)
    return np.concatenate(parts)


def _trim_leading_silence(
    samples: np.ndarray, max_ms: int, sr: int
) -> np.ndarray:
    """Remove leading silence so interrupted speech starts immediately."""
    threshold = 500  # amplitude threshold
    max_samples = int(sr * max_ms / 1000)
    for i in range(min(max_samples, len(samples))):
        if abs(samples[i]) > threshold:
            return samples[i:]
    return samples
