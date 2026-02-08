"""Mock tool registry: simulates external tool responses with latency/failures."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from ..core.interfaces import ToolResult
from ..core.results import AssertionResult


@dataclass
class ToolMock:
    """Configuration for a single mock tool."""

    handler: Callable[..., Any]
    latency: tuple[float, float] = (100, 500)  # ms range
    failure_rate: float = 0.0
    failure_error: str = "ServiceUnavailable"


class MockToolRegistry:
    """
    Mock all external tools a voice system might call.

    Key: simulates not only successes but also failures, latency, and
    partial results — the scenarios that matter most in production.
    """

    def __init__(self) -> None:
        self.tools: dict[str, ToolMock] = {}
        self.call_log: list[dict[str, Any]] = []
        self._clock: Any = None
        self._pending_expectations: list[_ToolExpectation] = []

    def set_clock(self, clock: Any) -> None:
        self._clock = clock

    def _now(self) -> float:
        if self._clock is not None:
            return self._clock.now()
        return 0.0

    # -- registration --------------------------------------------------------

    def register(
        self,
        name: str,
        handler: Callable[..., Any],
        latency_ms: tuple[float, float] = (100, 500),
        failure_rate: float = 0.0,
        failure_error: str = "ServiceUnavailable",
    ) -> None:
        self.tools[name] = ToolMock(
            handler=handler,
            latency=latency_ms,
            failure_rate=failure_rate,
            failure_error=failure_error,
        )

    # -- invocation (called by the SUT adapter) ------------------------------

    async def handle_call(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        """Handle a tool call from the system under test."""
        record = {
            "tool": tool_name,
            "args": args,
            "timestamp": self._now(),
        }
        self.call_log.append(record)

        # Notify any pending expectations
        for exp in self._pending_expectations:
            if exp.tool_name == tool_name:
                exp.received.set()

        mock = self.tools.get(tool_name)
        if mock is None:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}",
                latency_ms=0,
            )

        # Simulate network latency
        latency = random.uniform(*mock.latency) / 1000
        await asyncio.sleep(latency)

        # Simulate failure
        if random.random() < mock.failure_rate:
            return ToolResult(
                success=False,
                error=mock.failure_error,
                latency_ms=latency * 1000,
            )

        # Invoke the handler
        result = mock.handler(args)
        if asyncio.iscoroutine(result):
            result = await result

        return ToolResult(
            success=True,
            data=result,
            latency_ms=latency * 1000,
        )

    # -- test-side waiting ---------------------------------------------------

    async def wait_for_call(
        self,
        tool_name: str,
        expected_args: dict[str, Any] | None = None,
        timeout: float = 5.0,
    ) -> AssertionResult:
        """Wait until a specific tool is called, or timeout."""
        exp = _ToolExpectation(tool_name=tool_name)
        self._pending_expectations.append(exp)

        try:
            await asyncio.wait_for(exp.received.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return AssertionResult(
                timestamp=self._now(),
                passed=False,
                description=f"Timeout waiting for tool '{tool_name}'",
                expected={"tool": tool_name, "args": expected_args},
            )
        finally:
            self._pending_expectations.remove(exp)

        # Find the matching call
        calls = [c for c in self.call_log if c["tool"] == tool_name]
        if not calls:
            return AssertionResult(
                timestamp=self._now(),
                passed=False,
                description=f"Tool '{tool_name}' was never called",
            )

        last_call = calls[-1]
        if expected_args is not None:
            for key, value in expected_args.items():
                if key not in last_call["args"]:
                    return AssertionResult(
                        timestamp=self._now(),
                        passed=False,
                        description=f"Missing arg '{key}' in {tool_name} call",
                        expected=expected_args,
                        actual=last_call["args"],
                    )

        return AssertionResult(
            timestamp=self._now(),
            passed=True,
            description=f"Tool '{tool_name}' called successfully",
            actual=last_call["args"],
        )

    def reset(self) -> None:
        """Clear the call log."""
        self.call_log.clear()


@dataclass
class _ToolExpectation:
    tool_name: str
    received: asyncio.Event = field(default_factory=asyncio.Event)
