"""Multi-dimensional evaluation framework orchestrating all scorers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.results import TestResults
from .latency import LatencyScorer
from .accuracy import AccuracyScorer
from .naturalness import NaturalnessScorer
from .robustness import RobustnessScorer


@dataclass
class EvaluationReport:
    """Aggregated scores from all evaluation dimensions."""

    latency: dict[str, Any] = field(default_factory=dict)
    accuracy: dict[str, Any] = field(default_factory=dict)
    naturalness: dict[str, Any] = field(default_factory=dict)
    robustness: dict[str, Any] = field(default_factory=dict)
    tool_use: dict[str, Any] = field(default_factory=dict)
    overall_score: float = 0.0


class EvaluationFramework:
    """
    Multi-dimensional evaluation system.

    Each dimension has its own scorer; this framework orchestrates them
    and produces an aggregated report.
    """

    def __init__(self) -> None:
        self.scorers = {
            "latency": LatencyScorer(),
            "accuracy": AccuracyScorer(),
            "naturalness": NaturalnessScorer(),
            "robustness": RobustnessScorer(),
        }
        self._clock: Any = None

    def set_clock(self, clock: Any) -> None:
        self._clock = clock

    async def evaluate(self, results: TestResults) -> EvaluationReport:
        """Run all scorers against a ``TestResults`` and return a report."""
        report = EvaluationReport()

        report.latency = self.scorers["latency"].score(results)
        report.accuracy = self.scorers["accuracy"].score(results)
        report.tool_use = self._score_tool_use(results)

        # Naturalness uses LLM-as-judge (async)
        report.naturalness = await self.scorers["naturalness"].score(results)

        # Compute overall score (weighted average)
        scores = []
        for dim in [report.latency, report.accuracy, report.naturalness, report.tool_use]:
            s = dim.get("score", 0.0)
            if isinstance(s, (int, float)):
                scores.append(s)
        report.overall_score = sum(scores) / max(len(scores), 1)

        return report

    async def evaluate_robustness(
        self, clean: TestResults, noisy: TestResults
    ) -> dict[str, Any]:
        """Compare clean vs noisy results for robustness scoring."""
        return self.scorers["robustness"].score(clean, noisy)

    @staticmethod
    def _score_tool_use(results: TestResults) -> dict[str, Any]:
        """Evaluate tool-call correctness."""
        calls = results.tool_calls.calls
        if not calls:
            return {"score": 1.0, "total_calls": 0, "success_rate": 1.0}

        success_count = sum(1 for c in calls if c.success)
        avg_latency = sum(c.latency_ms for c in calls) / len(calls) if calls else 0

        return {
            "score": success_count / len(calls),
            "total_calls": len(calls),
            "success_rate": success_count / len(calls),
            "avg_latency_ms": avg_latency,
        }
