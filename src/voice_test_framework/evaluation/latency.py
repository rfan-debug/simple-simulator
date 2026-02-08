"""Latency scorer: first-byte latency, turn-taking gaps, filler timing."""

from __future__ import annotations

import statistics
from typing import Any

from ..core.results import TestResults


class LatencyScorer:
    """
    Evaluate response latency across multiple dimensions.

    Thresholds reflect industry expectations for real-time voice systems.
    """

    THRESHOLDS = {
        "p50_first_byte_ms": 300,
        "p99_first_byte_ms": 1000,
        "turn_taking_gap_ms": 500,
        "interrupt_response_ms": 200,
        "tool_call_filler_ms": 2000,  # if tool call >2s, system should fill
    }

    def score(self, results: TestResults) -> dict[str, Any]:
        latency = results.latency
        p50 = latency.p50_first_byte
        p99 = latency.p99_first_byte
        turn_gap = latency.turn_gap_avg

        # Score: 1.0 = perfect, 0.0 = terrible
        p50_score = max(0.0, 1.0 - p50 / (self.THRESHOLDS["p50_first_byte_ms"] * 2))
        p99_score = max(0.0, 1.0 - p99 / (self.THRESHOLDS["p99_first_byte_ms"] * 2))
        gap_score = max(0.0, 1.0 - turn_gap / (self.THRESHOLDS["turn_taking_gap_ms"] * 2))

        overall = statistics.mean([p50_score, p99_score, gap_score]) if any(
            [p50, p99, turn_gap]
        ) else 1.0

        return {
            "score": overall,
            "first_byte_p50_ms": p50,
            "first_byte_p99_ms": p99,
            "turn_gap_avg_ms": turn_gap,
            "p50_pass": p50 <= self.THRESHOLDS["p50_first_byte_ms"],
            "p99_pass": p99 <= self.THRESHOLDS["p99_first_byte_ms"],
            "turn_gap_pass": turn_gap <= self.THRESHOLDS["turn_taking_gap_ms"],
        }
