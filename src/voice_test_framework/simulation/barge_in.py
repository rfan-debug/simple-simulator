"""Barge-in / interruption simulator for testing speech overlap handling."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from ..core.interfaces import AudioChunk, InterruptEvent


# ---------------------------------------------------------------------------
# Barge-in patterns
# ---------------------------------------------------------------------------

BARGE_IN_PATTERNS: dict[str, dict[str, Any]] = {
    "eager_interrupt": {
        # User interrupts as soon as they hear a keyword
        "trigger": "keyword_detected",
        "delay_ms": (100, 300),
        "overlap_duration_ms": (500, 2000),
    },
    "correction": {
        # System said something wrong, user jumps in to correct
        "trigger": "incorrect_info",
        "delay_ms": (200, 500),
        "user_says": "No no, I meant {correction}",
    },
    "impatient": {
        # System response is too long, user cuts in
        "trigger": "response_duration > 5s",
        "delay_ms": (0, 100),
        "user_says": "OK OK I got it, just tell me {question}",
    },
    "backchannel": {
        # Not a real interruption — acknowledgement tokens
        "trigger": "periodic",
        "interval_ms": (2000, 4000),
        "audio_texts": ["mm-hmm", "right", "OK", "yeah"],
        "is_true_interrupt": False,
    },
}


class BargeInSimulator:
    """
    Simulate realistic barge-in / interruption behaviour.

    This is one of the hardest scenarios to handle correctly in voice AI
    systems, making it especially valuable to test.
    """

    PATTERNS = BARGE_IN_PATTERNS

    def __init__(self) -> None:
        self._clock: Any = None

    def set_clock(self, clock: Any) -> None:
        self._clock = clock

    def _now(self) -> float:
        if self._clock is not None:
            return self._clock.now()
        return 0.0

    async def simulate(
        self,
        pattern: str,
        system_audio_stream: AsyncIterator[Any] | None = None,
        user_audio_gen: Any | None = None,
        correction: str = "",
        question: str = "",
    ) -> InterruptEvent:
        """
        Execute a barge-in pattern.

        Parameters
        ----------
        pattern:
            One of the keys in ``PATTERNS``.
        system_audio_stream:
            Async iterator over the system's response audio (used to detect
            the right moment to interrupt).
        user_audio_gen:
            An ``AudioStreamSimulator`` instance for generating the
            interruption audio.
        correction / question:
            Template variables for the interruption text.
        """
        config = self.PATTERNS.get(pattern, self.PATTERNS["eager_interrupt"])

        # Wait for the trigger condition
        await self._wait_trigger(config.get("trigger", "immediate"), system_audio_stream)

        # Simulate human reaction time
        delay_range = config.get("delay_ms", (100, 300))
        delay = random.uniform(*delay_range) / 1000
        await asyncio.sleep(delay)

        # Generate interruption audio
        user_text = config.get("user_says", config.get("audio_texts", [""])[0])
        if isinstance(user_text, str):
            user_text = user_text.format(correction=correction, question=question)

        interrupt_audio = b""
        if user_audio_gen is not None:
            chunks: list[bytes] = []
            async for chunk in user_audio_gen.generate(text=user_text):
                chunks.append(chunk.data)
            interrupt_audio = b"".join(chunks)

        return InterruptEvent(
            audio=interrupt_audio,
            is_true_interrupt=config.get("is_true_interrupt", True),
            timestamp=self._now(),
        )

    # -- trigger helpers -----------------------------------------------------

    async def _wait_trigger(
        self, trigger: str, stream: AsyncIterator[Any] | None
    ) -> None:
        """Wait until the trigger condition is met."""
        match trigger:
            case "immediate":
                return
            case "keyword_detected":
                # In a real impl, this would monitor the stream for a keyword
                if stream is not None:
                    try:
                        await asyncio.wait_for(self._consume_one(stream), timeout=5)
                    except (asyncio.TimeoutError, StopAsyncIteration):
                        pass
            case "periodic":
                await asyncio.sleep(random.uniform(2, 4))
            case _:
                # For expression-based triggers like "response_duration > 5s"
                if ">" in trigger:
                    parts = trigger.split(">")
                    try:
                        seconds = float(parts[1].strip().rstrip("s"))
                        await asyncio.sleep(seconds)
                    except (ValueError, IndexError):
                        pass

    @staticmethod
    async def _consume_one(stream: AsyncIterator[Any]) -> None:
        async for _ in stream:
            return
