"""Network condition simulator: latency, jitter, packet loss, disconnects."""

from __future__ import annotations

import asyncio
import random
from typing import Any

from ..core.interfaces import AudioChunk


class NetworkSimulator:
    """
    Simulate realistic network conditions that affect audio streaming.

    Supports named profiles and manual configuration of latency, jitter,
    packet loss, and bandwidth limits.
    """

    PROFILES: dict[str, dict[str, Any]] = {
        "perfect":   {"latency": 10,  "jitter": 2,   "loss": 0.0},
        "good_4g":   {"latency": 50,  "jitter": 15,  "loss": 0.01},
        "poor_4g":   {"latency": 150, "jitter": 50,  "loss": 0.05},
        "bad_wifi":  {"latency": 200, "jitter": 100, "loss": 0.10},
        "elevator":  {"latency": 500, "jitter": 200, "loss": 0.30},
    }

    def __init__(
        self,
        profile: str = "perfect",
        latency_ms: float | None = None,
        jitter_ms: float | None = None,
        loss_rate: float | None = None,
        bandwidth_limit: int | None = None,
    ):
        p = self.PROFILES.get(profile, self.PROFILES["perfect"])
        self.base_latency = latency_ms if latency_ms is not None else p["latency"]
        self.jitter = jitter_ms if jitter_ms is not None else p["jitter"]
        self.loss_rate = loss_rate if loss_rate is not None else p["loss"]
        self.bandwidth_limit = bandwidth_limit
        self.is_connected = True
        self._clock: Any = None
        self._buffer: list[AudioChunk] = []

    def set_clock(self, clock: Any) -> None:
        self._clock = clock

    # -- configuration -------------------------------------------------------

    def set_profile(self, profile: str) -> None:
        p = self.PROFILES.get(profile, self.PROFILES["perfect"])
        self.configure(
            latency_ms=p["latency"],
            jitter_ms=p["jitter"],
            loss_rate=p["loss"],
        )

    def configure(
        self,
        latency_ms: float | None = None,
        jitter_ms: float | None = None,
        loss_rate: float | None = None,
    ) -> None:
        if latency_ms is not None:
            self.base_latency = latency_ms
        if jitter_ms is not None:
            self.jitter = jitter_ms
        if loss_rate is not None:
            self.loss_rate = loss_rate

    # -- main API ------------------------------------------------------------

    async def apply(self, chunk: AudioChunk) -> AudioChunk | None:
        """Apply network effects to a single audio chunk.

        Returns ``None`` when the chunk is "lost" due to simulated packet loss.
        """
        if not self.is_connected:
            self._buffer.append(chunk)
            return None

        # Packet loss
        if random.random() < self.loss_rate:
            return None

        # Latency + jitter
        delay = self.base_latency + random.gauss(0, self.jitter)
        delay = max(0, delay)
        await asyncio.sleep(delay / 1000)

        # Bandwidth-limited quality reduction (stub)
        if self.bandwidth_limit:
            chunk = self._compress_audio(chunk)

        return chunk

    async def simulate_disconnect(self, duration_s: float) -> None:
        """Simulate a network disconnection for *duration_s* seconds."""
        self.is_connected = False
        await asyncio.sleep(duration_s)
        self.is_connected = True
        self._flush_buffer()

    # -- internals -----------------------------------------------------------

    def _compress_audio(self, chunk: AudioChunk) -> AudioChunk:
        """Degrade audio quality to simulate bandwidth limits."""
        # Simple degradation: keep only every Nth sample byte pair
        data = chunk.data
        if self.bandwidth_limit and self.bandwidth_limit < 64000:
            # Drop every other sample (halves quality)
            pairs = [data[i : i + 2] for i in range(0, len(data), 2)]
            reduced = b"".join(pairs[::2]) * 2  # duplicate to keep length
            data = reduced[: len(chunk.data)]
        return AudioChunk(
            data=data,
            timestamp=chunk.timestamp,
            sample_rate=chunk.sample_rate,
        )

    def _flush_buffer(self) -> None:
        """Discard audio buffered during disconnection."""
        self._buffer.clear()
