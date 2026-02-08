"""Accuracy scorer: intent recognition, entity extraction, visual grounding."""

from __future__ import annotations

from typing import Any

from ..core.results import TestResults


class AccuracyScorer:
    """
    Evaluate the SUT's accuracy across intent recognition, entity
    extraction, and (optionally) visual grounding.
    """

    def score(self, results: TestResults) -> dict[str, Any]:
        acc = results.accuracy

        # Fall back to assertion pass-rate when explicit accuracy metrics
        # are not populated.
        if acc.overall == 0.0 and results.assertions:
            passed = sum(1 for a in results.assertions if a.passed)
            acc.overall = passed / len(results.assertions)
            acc.intent_recognition = acc.overall
            acc.entity_extraction = acc.overall

        overall = (
            acc.intent_recognition * 0.4
            + acc.entity_extraction * 0.3
            + acc.visual_grounding * 0.1
            + acc.overall * 0.2
        )

        return {
            "score": overall,
            "intent_recognition": acc.intent_recognition,
            "entity_extraction": acc.entity_extraction,
            "visual_grounding": acc.visual_grounding,
            "overall_accuracy": acc.overall,
        }
