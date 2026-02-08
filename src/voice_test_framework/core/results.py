"""Test results data structures for collecting and querying outcomes."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssertionResult:
    """Outcome of a single assertion at a point in time."""

    timestamp: float
    passed: bool
    description: str = ""
    expected: Any = None
    actual: Any = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BargeInResult:
    """Metrics collected during a barge-in event."""

    was_handled: bool = False
    response_latency: float = 0.0  # ms
    system_stopped_speaking: bool = False
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class LatencyMetrics:
    """Latency-related metrics gathered during a test run."""

    first_byte_latencies: list[float] = field(default_factory=list)
    turn_gaps: list[float] = field(default_factory=list)

    @property
    def p50_first_byte(self) -> float:
        if not self.first_byte_latencies:
            return 0.0
        sorted_vals = sorted(self.first_byte_latencies)
        idx = int(len(sorted_vals) * 0.50)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]

    @property
    def p99_first_byte(self) -> float:
        if not self.first_byte_latencies:
            return 0.0
        sorted_vals = sorted(self.first_byte_latencies)
        idx = int(len(sorted_vals) * 0.99)
        return sorted_vals[min(idx, len(sorted_vals) - 1)]

    @property
    def turn_gap_avg(self) -> float:
        return statistics.mean(self.turn_gaps) if self.turn_gaps else 0.0


@dataclass
class AccuracyMetrics:
    """Accuracy-related metrics."""

    intent_recognition: float = 0.0
    entity_extraction: float = 0.0
    visual_grounding: float = 0.0
    overall: float = 0.0


@dataclass
class ToolCallRecord:
    """Single recorded tool invocation."""

    tool: str
    args: dict[str, Any]
    timestamp: float
    success: bool = True
    latency_ms: float = 0.0


@dataclass
class ToolCallResults:
    """Aggregated tool-call records for assertion convenience."""

    calls: list[ToolCallRecord] = field(default_factory=list)

    def assert_called(self, tool_name: str) -> bool:
        return any(c.tool == tool_name for c in self.calls)

    def assert_not_called(self, tool_name: str) -> bool:
        return not any(c.tool == tool_name for c in self.calls)

    def assert_call_order(self, *tool_names: str) -> bool:
        actual = [c.tool for c in self.calls]
        idx = 0
        for expected in tool_names:
            while idx < len(actual):
                if actual[idx] == expected:
                    break
                idx += 1
            else:
                return False
            idx += 1
        return True


@dataclass
class ResponseRecord:
    """A single captured response from the SUT."""

    text: str = ""
    audio: bytes = b""
    timestamp: float = 0.0


@dataclass
class TestResults:
    """
    Container for all results gathered during a single scenario run.

    Provides convenience accessors for assertions in pytest.
    """

    assertions: list[AssertionResult] = field(default_factory=list)
    latency: LatencyMetrics = field(default_factory=LatencyMetrics)
    accuracy: AccuracyMetrics = field(default_factory=AccuracyMetrics)
    tool_calls: ToolCallResults = field(default_factory=ToolCallResults)
    barge_in: BargeInResult = field(default_factory=BargeInResult)
    responses: list[ResponseRecord] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- convenience ---------------------------------------------------------

    def add(self, timestamp: float, result: AssertionResult | dict) -> None:
        if isinstance(result, dict):
            result = AssertionResult(
                timestamp=timestamp,
                passed=result.get("passed", True),
                description=result.get("description", ""),
                expected=result.get("expected"),
                actual=result.get("actual"),
            )
        self.assertions.append(result)

    def all_passed(self) -> bool:
        return all(a.passed for a in self.assertions)

    @property
    def passed(self) -> bool:
        return self.all_passed()

    @property
    def last_response(self) -> ResponseRecord:
        if self.responses:
            return self.responses[-1]
        return ResponseRecord()

    def tag(self, label: str) -> None:
        self.tags.append(label)

    def record_response(self, text: str = "", audio: bytes = b"", timestamp: float = 0.0) -> None:
        self.responses.append(ResponseRecord(text=text, audio=audio, timestamp=timestamp))

    def record_tool_call(
        self,
        tool: str,
        args: dict,
        timestamp: float,
        success: bool = True,
        latency_ms: float = 0.0,
    ) -> None:
        self.tool_calls.calls.append(
            ToolCallRecord(
                tool=tool,
                args=args,
                timestamp=timestamp,
                success=success,
                latency_ms=latency_ms,
            )
        )
