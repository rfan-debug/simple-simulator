"""Barge-in / interruption tests."""

from __future__ import annotations

import pytest

from voice_test_framework.core.orchestrator import ScenarioOrchestrator
from voice_test_framework.core.results import TestResults
from voice_test_framework.simulation.barge_in import BargeInSimulator, BARGE_IN_PATTERNS


SCENARIO = "scenarios/hotel_booking_interrupt.yaml"


class TestBargeIn:

    async def test_interrupt_scenario_runs(
        self, orchestrator: ScenarioOrchestrator
    ):
        """The interruption scenario should complete without errors."""
        results = await orchestrator.run(scenario=SCENARIO)
        assert isinstance(results, TestResults)

    def test_all_patterns_defined(self):
        """All standard barge-in patterns should be present."""
        expected = {"eager_interrupt", "correction", "impatient", "backchannel"}
        assert expected.issubset(set(BARGE_IN_PATTERNS.keys()))

    async def test_barge_in_simulator_standalone(self):
        """BargeInSimulator should work independently."""
        sim = BargeInSimulator()
        event = await sim.simulate(pattern="eager_interrupt")
        assert event.is_true_interrupt is True

    async def test_backchannel_not_interrupt(self):
        """Backchannel events should not be flagged as true interruptions."""
        sim = BargeInSimulator()
        event = await sim.simulate(pattern="backchannel")
        assert event.is_true_interrupt is False
