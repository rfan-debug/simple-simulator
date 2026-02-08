"""Tests for the reporting layer."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from voice_test_framework.core.results import TestResults, AssertionResult
from voice_test_framework.reporting.html_report import HTMLReportGenerator
from voice_test_framework.reporting.junit import JUnitXMLWriter
from voice_test_framework.reporting.regression import RegressionDetector


class TestHTMLReport:

    def test_generate(self, tmp_path: Path):
        r = TestResults()
        r.add(0, AssertionResult(timestamp=0, passed=True, description="test1"))
        r.metadata["scenario_name"] = "basic_test"

        gen = HTMLReportGenerator(title="Test Report")
        out = gen.generate([r], output_path=tmp_path / "report.html")
        assert out.exists()
        content = out.read_text()
        assert "Test Report" in content
        assert "basic_test" in content

    def test_empty_results(self, tmp_path: Path):
        gen = HTMLReportGenerator()
        out = gen.generate([], output_path=tmp_path / "report.html")
        assert out.exists()


class TestJUnitXML:

    def test_write(self, tmp_path: Path):
        r = TestResults()
        r.add(0, AssertionResult(timestamp=0, passed=True, description="ok"))
        r.add(1, AssertionResult(timestamp=1, passed=False, description="fail"))
        r.metadata["scenario_name"] = "junit_test"

        writer = JUnitXMLWriter()
        out = writer.write([r], output_path=tmp_path / "results.xml")
        assert out.exists()
        content = out.read_text()
        assert "failures" in content
        assert "junit_test" in content

    def test_all_pass(self, tmp_path: Path):
        r = TestResults()
        r.add(0, AssertionResult(timestamp=0, passed=True, description="pass1"))
        writer = JUnitXMLWriter()
        out = writer.write([r], output_path=tmp_path / "results.xml")
        content = out.read_text()
        assert 'failures="0"' in content


class TestRegressionDetector:

    def test_no_baseline(self, tmp_path: Path):
        detector = RegressionDetector(baseline_dir=tmp_path / "baselines")
        r = TestResults()
        r.add(0, AssertionResult(timestamp=0, passed=True))
        result = detector.check([r], baseline_name="test_baseline")
        assert not result.has_regression
        # Baseline should have been created
        assert (tmp_path / "baselines" / "test_baseline.json").exists()

    def test_detect_regression(self, tmp_path: Path):
        baseline_dir = tmp_path / "baselines"
        baseline_dir.mkdir()
        # Baseline with 100% pass rate
        (baseline_dir / "test.json").write_text(json.dumps({"pass_rate": 1.0}))

        detector = RegressionDetector(baseline_dir=baseline_dir, threshold=0.05)

        # Current run has 50% pass rate (regression)
        r1 = TestResults()
        r1.add(0, AssertionResult(timestamp=0, passed=True))
        r1.add(1, AssertionResult(timestamp=1, passed=False))
        result = detector.check([r1], baseline_name="test")
        assert result.has_regression

    def test_no_regression(self, tmp_path: Path):
        baseline_dir = tmp_path / "baselines"
        baseline_dir.mkdir()
        (baseline_dir / "test.json").write_text(json.dumps({"pass_rate": 1.0}))

        detector = RegressionDetector(baseline_dir=baseline_dir)

        r = TestResults()
        r.add(0, AssertionResult(timestamp=0, passed=True))
        result = detector.check([r], baseline_name="test")
        assert not result.has_regression
