"""Tests for the evaluation layer."""

from __future__ import annotations

import pytest

from voice_test_framework.core.results import TestResults, AssertionResult
from voice_test_framework.evaluation.framework import EvaluationFramework
from voice_test_framework.evaluation.latency import LatencyScorer
from voice_test_framework.evaluation.accuracy import AccuracyScorer
from voice_test_framework.evaluation.naturalness import NaturalnessScorer
from voice_test_framework.evaluation.robustness import RobustnessScorer


class TestLatencyScorer:

    def test_perfect_latency(self):
        r = TestResults()
        r.latency.first_byte_latencies = [100, 150, 200]
        r.latency.turn_gaps = [200, 300]
        score = LatencyScorer().score(r)
        assert 0 <= score["score"] <= 1
        assert score["p50_pass"]

    def test_no_data(self):
        r = TestResults()
        score = LatencyScorer().score(r)
        assert score["score"] == 1.0  # no data = assume ok


class TestAccuracyScorer:

    def test_from_assertions(self):
        r = TestResults()
        r.add(0, AssertionResult(timestamp=0, passed=True))
        r.add(1, AssertionResult(timestamp=1, passed=True))
        r.add(2, AssertionResult(timestamp=2, passed=False))
        score = AccuracyScorer().score(r)
        assert 0 < score["score"] < 1

    def test_explicit_accuracy(self):
        r = TestResults()
        r.accuracy.intent_recognition = 0.95
        r.accuracy.entity_extraction = 0.90
        r.accuracy.overall = 0.92
        score = AccuracyScorer().score(r)
        assert score["score"] > 0.8


class TestNaturalnessScorer:

    async def test_heuristic_fallback(self):
        """Without an API key, the scorer should use the heuristic."""
        r = TestResults()
        r.record_response(text="Hello, how can I help you?", timestamp=1)
        r.record_response(text="Sure, I can help with that.", timestamp=2)
        score = await NaturalnessScorer().score(r)
        assert score["method"] == "heuristic"
        assert 0 <= score["score"] <= 1

    async def test_empty_results(self):
        r = TestResults()
        score = await NaturalnessScorer().score(r)
        assert score["score"] == 0.5


class TestRobustnessScorer:

    def test_no_noisy_results(self):
        clean = TestResults()
        score = RobustnessScorer().score(clean)
        assert score["score"] == 1.0

    def test_with_noisy(self):
        clean = TestResults()
        clean.accuracy.overall = 0.95
        noisy = TestResults()
        noisy.accuracy.overall = 0.80
        score = RobustnessScorer().score(clean, noisy)
        assert 0 < score["score"] < 1
        assert score["noise_degradation"] < 1.0


class TestEvaluationFramework:

    async def test_evaluate(self):
        fw = EvaluationFramework()
        r = TestResults()
        r.latency.first_byte_latencies = [200, 250]
        r.record_response(text="Hello", timestamp=1)
        r.add(0, AssertionResult(timestamp=0, passed=True))
        report = await fw.evaluate(r)
        assert 0 <= report.overall_score <= 1
