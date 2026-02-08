"""Simulated clock for deterministic test orchestration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field


@dataclass
class SimulatedClock:
    """
    A clock that can be advanced programmatically.

    In real-time mode the clock tracks wall-clock time.
    In simulated mode ``advance_to`` jumps instantly, enabling fast test runs.
    """

    _current: float = 0.0
    _realtime: bool = False
    _waiters: list[tuple[float, asyncio.Event]] = field(default_factory=list)

    # -- public API ----------------------------------------------------------

    def now(self) -> float:
        """Return the current simulated time in seconds."""
        return self._current

    async def advance_to(self, target: float) -> None:
        """Advance the clock to *target* seconds.

        If running in real-time mode this sleeps for the delta; otherwise the
        jump is instantaneous.
        """
        if target <= self._current:
            return

        delta = target - self._current

        if self._realtime:
            await asyncio.sleep(delta)

        self._current = target
        self._wake_waiters()

    async def advance_by(self, delta: float) -> None:
        """Advance the clock by *delta* seconds."""
        await self.advance_to(self._current + delta)

    async def wait_until(self, target: float) -> None:
        """Suspend the caller until the clock reaches *target*."""
        if self._current >= target:
            return
        event = asyncio.Event()
        self._waiters.append((target, event))
        await event.wait()

    def set_realtime(self, enabled: bool = True) -> None:
        self._realtime = enabled

    def reset(self) -> None:
        self._current = 0.0
        self._waiters.clear()

    # -- internals -----------------------------------------------------------

    def _wake_waiters(self) -> None:
        still_waiting: list[tuple[float, asyncio.Event]] = []
        for target, event in self._waiters:
            if self._current >= target:
                event.set()
            else:
                still_waiting.append((target, event))
        self._waiters = still_waiting
