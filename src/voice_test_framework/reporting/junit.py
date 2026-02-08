"""JUnit XML report writer for CI/CD integration."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.results import TestResults


class JUnitXMLWriter:
    """
    Generate JUnit XML reports compatible with CI/CD systems
    (Jenkins, GitHub Actions, GitLab CI, etc.).
    """

    def __init__(self, suite_name: str = "voice-test-framework"):
        self.suite_name = suite_name

    def write(
        self,
        all_results: list[TestResults],
        output_path: str | Path = "results.xml",
    ) -> Path:
        testsuite = ET.Element("testsuite")
        testsuite.set("name", self.suite_name)
        testsuite.set("timestamp", datetime.now(timezone.utc).isoformat())

        total = 0
        failures = 0
        errors = 0
        total_time = 0.0

        for i, result in enumerate(all_results):
            scenario_name = result.metadata.get("scenario_name", f"scenario_{i}")

            for j, assertion in enumerate(result.assertions):
                total += 1
                testcase = ET.SubElement(testsuite, "testcase")
                testcase.set("classname", f"{self.suite_name}.{scenario_name}")
                testcase.set("name", assertion.description or f"assertion_{j}")
                testcase.set("time", f"{assertion.timestamp:.3f}")

                if not assertion.passed:
                    failures += 1
                    failure = ET.SubElement(testcase, "failure")
                    failure.set("message", assertion.description)
                    failure.text = (
                        f"Expected: {assertion.expected}\n"
                        f"Actual: {assertion.actual}"
                    )

            # If no assertions, create one testcase for the scenario
            if not result.assertions:
                total += 1
                testcase = ET.SubElement(testsuite, "testcase")
                testcase.set("classname", f"{self.suite_name}")
                testcase.set("name", scenario_name)
                if not result.passed:
                    failures += 1
                    failure = ET.SubElement(testcase, "failure")
                    failure.set("message", "Scenario did not pass")

        testsuite.set("tests", str(total))
        testsuite.set("failures", str(failures))
        testsuite.set("errors", str(errors))

        tree = ET.ElementTree(testsuite)
        output_path = Path(output_path)
        ET.indent(tree, space="  ")
        tree.write(output_path, encoding="unicode", xml_declaration=True)
        return output_path
