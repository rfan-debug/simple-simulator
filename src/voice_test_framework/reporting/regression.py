"""Regression detection: compare current results against a baseline."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.results import TestResults

logger = logging.getLogger(__name__)


@dataclass
class RegressionResult:
    """Outcome of a regression check."""

    has_regression: bool
    regressions: list[dict[str, Any]] = field(default_factory=list)
    improvements: list[dict[str, Any]] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)


class RegressionDetector:
    """
    Compare current test results against a stored baseline to detect
    regressions and improvements.

    Baselines are stored as JSON files so they can be committed to
    version control.
    """

    def __init__(
        self,
        baseline_dir: str | Path = ".baselines",
        threshold: float = 0.05,
    ):
        self.baseline_dir = Path(baseline_dir)
        self.threshold = threshold  # 5% degradation triggers regression

    def check(
        self,
        results: list[TestResults],
        baseline_name: str = "latest",
    ) -> RegressionResult:
        """Compare *results* against the stored baseline."""
        baseline = self._load_baseline(baseline_name)
        if baseline is None:
            logger.info("No baseline '%s' found — saving current as baseline", baseline_name)
            self._save_baseline(results, baseline_name)
            return RegressionResult(has_regression=False)

        current_metrics = self._extract_metrics(results)
        regressions: list[dict[str, Any]] = []
        improvements: list[dict[str, Any]] = []
        unchanged: list[str] = []

        for key, current_value in current_metrics.items():
            baseline_value = baseline.get(key)
            if baseline_value is None:
                continue

            if baseline_value == 0:
                unchanged.append(key)
                continue

            delta = (current_value - baseline_value) / abs(baseline_value)

            if delta < -self.threshold:
                regressions.append({
                    "metric": key,
                    "baseline": baseline_value,
                    "current": current_value,
                    "delta_pct": round(delta * 100, 2),
                })
            elif delta > self.threshold:
                improvements.append({
                    "metric": key,
                    "baseline": baseline_value,
                    "current": current_value,
                    "delta_pct": round(delta * 100, 2),
                })
            else:
                unchanged.append(key)

        return RegressionResult(
            has_regression=len(regressions) > 0,
            regressions=regressions,
            improvements=improvements,
            unchanged=unchanged,
        )

    def update_baseline(
        self,
        results: list[TestResults],
        baseline_name: str = "latest",
    ) -> Path:
        """Save current results as the new baseline."""
        return self._save_baseline(results, baseline_name)

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _extract_metrics(results: list[TestResults]) -> dict[str, float]:
        """Flatten results into a dict of scalar metrics."""
        metrics: dict[str, float] = {}
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        metrics["pass_rate"] = passed / total if total else 0

        latencies: list[float] = []
        for r in results:
            latencies.extend(r.latency.first_byte_latencies)
        if latencies:
            metrics["latency_p50"] = sorted(latencies)[len(latencies) // 2]

        accuracies = [r.accuracy.overall for r in results if r.accuracy.overall > 0]
        if accuracies:
            metrics["accuracy_avg"] = sum(accuracies) / len(accuracies)

        return metrics

    def _load_baseline(self, name: str) -> dict[str, float] | None:
        path = self.baseline_dir / f"{name}.json"
        if not path.exists():
            return None
        with open(path) as fh:
            return json.load(fh)

    def _save_baseline(self, results: list[TestResults], name: str) -> Path:
        self.baseline_dir.mkdir(parents=True, exist_ok=True)
        path = self.baseline_dir / f"{name}.json"
        metrics = self._extract_metrics(results)
        with open(path, "w") as fh:
            json.dump(metrics, fh, indent=2)
        return path
