"""Robustness scorer: compares clean vs degraded conditions."""

from __future__ import annotations

from typing import Any

from ..core.results import TestResults


class RobustnessScorer:
    """
    Evaluate how well the SUT degrades under adverse conditions.

    Compares metrics from a clean run to those from a noisy / degraded
    run and produces degradation ratios (closer to 1.0 = more robust).
    """

    def score(
        self, clean: TestResults, noisy: TestResults | None = None
    ) -> dict[str, Any]:
        if noisy is None:
            return {
                "score": 1.0,
                "note": "No noisy results provided for comparison",
            }

        clean_accuracy = self._compute_accuracy(clean)
        noisy_accuracy = self._compute_accuracy(noisy)

        noise_degradation = (
            noisy_accuracy / clean_accuracy if clean_accuracy > 0 else 0.0
        )

        clean_latency = clean.latency.p50_first_byte or 1
        noisy_latency = noisy.latency.p50_first_byte or 1
        latency_ratio = clean_latency / noisy_latency if noisy_latency > 0 else 0.0

        barge_in_score = 1.0 if noisy.barge_in.was_handled else 0.0

        overall = (
            noise_degradation * 0.4
            + min(1.0, latency_ratio) * 0.3
            + barge_in_score * 0.3
        )

        return {
            "score": overall,
            "noise_degradation": noise_degradation,
            "latency_ratio": latency_ratio,
            "barge_in_handling": barge_in_score,
            "clean_accuracy": clean_accuracy,
            "noisy_accuracy": noisy_accuracy,
        }

    @staticmethod
    def _compute_accuracy(results: TestResults) -> float:
        if results.accuracy.overall > 0:
            return results.accuracy.overall
        if results.assertions:
            passed = sum(1 for a in results.assertions if a.passed)
            return passed / len(results.assertions)
        return 1.0
