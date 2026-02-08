"""Noise engine: ambient noise, transient events, competing speech."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..core.interfaces import AudioChunk


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class TransientNoise:
    """An active transient noise event (phone ring, dog bark, …)."""

    source: str
    duration: float  # seconds
    peak_db: float
    _elapsed: float = 0.0
    _sr: int = 16000

    def is_active(self) -> bool:
        return self._elapsed < self.duration

    def next_chunk(self, chunk_samples: int) -> np.ndarray:
        """Generate the next chunk of transient noise."""
        if not self.is_active():
            return np.zeros(chunk_samples, dtype=np.int16)
        amplitude = int(10 ** (self.peak_db / 20) * 32767)
        freq = 800 + hash(self.source) % 400
        t = np.arange(chunk_samples) / self._sr + self._elapsed
        self._elapsed += chunk_samples / self._sr
        return (np.sin(2 * np.pi * freq * t) * amplitude).astype(np.int16)


@dataclass
class AmbientProfile:
    """Continuous ambient noise profile."""

    name: str
    snr_db: float
    _sr: int = 16000
    _phase: float = 0.0

    def next_chunk(self, chunk_samples: int) -> np.ndarray:
        """Generate continuous ambient noise."""
        amplitude = int(10 ** (-abs(self.snr_db) / 20) * 32767)
        noise = np.random.default_rng().integers(
            -amplitude, amplitude, size=chunk_samples, dtype=np.int16
        )
        return noise


# ---------------------------------------------------------------------------
# Noise engine
# ---------------------------------------------------------------------------

class NoiseEngine:
    """
    Realistic environment noise simulation.

    Three-layer noise model:
    1. Ambient  — continuous background noise (cafe, office, street)
    2. Transient — short noise events (doorbell, phone ring, dog bark)
    3. Competing speech — another person talking in the background
    """

    AMBIENT_PROFILES: dict[str, dict[str, Any]] = {
        "quiet_room":   {"snr_db": 40},
        "office":       {"snr_db": 25},
        "cafe":         {"snr_db": 15},
        "street":       {"snr_db": 10},
        "construction": {"snr_db": 5},
        "car_driving":  {"snr_db": 18},
    }

    TRANSIENT_EVENTS: dict[str, dict[str, Any]] = {
        "phone_ring":   {"duration": (2, 5),  "peak_db": -10},
        "door_knock":   {"duration": (1, 3),  "peak_db": -15},
        "dog_bark":     {"duration": (1, 4),  "peak_db": -8},
        "baby_cry":     {"duration": (3, 10), "peak_db": -5},
        "notification": {"duration": (0.5, 1), "peak_db": -20},
        "keyboard":     {"duration": (0.2, 1), "peak_db": -25},
        "siren":        {"duration": (5, 15), "peak_db": -3},
    }

    def __init__(
        self,
        profile: str = "quiet_room",
        snr_db: float | None = None,
        sample_rate: int = 16000,
    ):
        self.sample_rate = sample_rate
        self.active_transients: list[TransientNoise] = []
        self._clock: Any = None

        resolved_snr = snr_db if snr_db is not None else self.AMBIENT_PROFILES.get(
            profile, {}
        ).get("snr_db", 40)
        self.ambient = AmbientProfile(name=profile, snr_db=resolved_snr, _sr=sample_rate)

    def set_clock(self, clock: Any) -> None:
        self._clock = clock

    # -- public API ----------------------------------------------------------

    def set_profile(self, profile: str, snr_override: float | None = None) -> None:
        snr = snr_override if snr_override is not None else self.AMBIENT_PROFILES.get(
            profile, {}
        ).get("snr_db", 40)
        self.ambient = AmbientProfile(name=profile, snr_db=snr, _sr=self.sample_rate)

    def set_snr(self, snr_db: float) -> None:
        self.ambient.snr_db = snr_db

    def mix_with_speech(self, speech_chunk: AudioChunk) -> AudioChunk:
        """Mix noise into a speech audio chunk."""
        speech = np.frombuffer(speech_chunk.data, dtype=np.int16)
        num_samples = len(speech)

        ambient_noise = self.ambient.next_chunk(num_samples)

        layers: list[np.ndarray] = [speech.astype(np.float32), ambient_noise.astype(np.float32)]

        # Add active transient noises
        self.active_transients = [t for t in self.active_transients if t.is_active()]
        for transient in self.active_transients:
            layers.append(transient.next_chunk(num_samples).astype(np.float32))

        mixed = sum(layers)  # type: ignore[arg-type]
        mixed = np.clip(mixed, -32768, 32767).astype(np.int16)

        return AudioChunk(
            data=mixed.tobytes(),
            timestamp=speech_chunk.timestamp,
            sample_rate=speech_chunk.sample_rate,
        )

    async def inject(self, noise_type: str, source: str | None = None) -> None:
        """Inject a transient noise event or competing speech."""
        if noise_type == "transient" and source is not None:
            config = self.TRANSIENT_EVENTS.get(source, {"duration": (1, 3), "peak_db": -15})
            event = TransientNoise(
                source=source,
                duration=random.uniform(*config["duration"]),
                peak_db=config["peak_db"],
                _sr=self.sample_rate,
            )
            self.active_transients.append(event)
        elif noise_type == "competing_speech":
            # Simulate background speech as a mid-frequency transient
            event = TransientNoise(
                source=source or "background_speaker",
                duration=random.uniform(3, 8),
                peak_db=-10,
                _sr=self.sample_rate,
            )
            self.active_transients.append(event)

    def crossfade_profile(
        self, from_profile: str, to_profile: str, duration: float = 3.0
    ) -> None:
        """Transition from one ambient profile to another."""
        # For simplicity, snap to the target profile immediately.
        # A production implementation would interpolate SNR over *duration*.
        self.set_profile(to_profile)
