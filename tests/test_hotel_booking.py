"""Hotel booking scenario tests.

These tests exercise the framework itself using YAML scenarios.
They do NOT connect to a real SUT — instead they validate the
orchestrator, simulation layers, and assertion machinery.
"""

from __future__ import annotations

import pytest

from voice_test_framework.core.orchestrator import ScenarioOrchestrator
from voice_test_framework.core.results import TestResults


SCENARIO_DIR = "scenarios"


class TestHotelBookingBasic:
    """Basic hotel booking flow — quiet environment."""

    async def test_scenario_loads(self, orchestrator: ScenarioOrchestrator):
        """The basic scenario YAML should load without errors."""
        results = await orchestrator.run(
            scenario=f"{SCENARIO_DIR}/hotel_booking_basic.yaml"
        )
        assert isinstance(results, TestResults)

    async def test_assertions_are_recorded(self, orchestrator: ScenarioOrchestrator):
        results = await orchestrator.run(
            scenario=f"{SCENARIO_DIR}/hotel_booking_basic.yaml"
        )
        # The scenario has assert_system and expect_tool_call steps
        assert len(results.assertions) > 0


class TestHotelBookingNoisy:
    """Hotel booking under noisy conditions."""

    async def test_noisy_scenario_loads(self, orchestrator: ScenarioOrchestrator):
        results = await orchestrator.run(
            scenario=f"{SCENARIO_DIR}/hotel_booking_noisy.yaml"
        )
        assert isinstance(results, TestResults)

    async def test_noise_does_not_crash(self, orchestrator: ScenarioOrchestrator):
        """Noise injection should not cause runtime errors."""
        results = await orchestrator.run(
            scenario=f"{SCENARIO_DIR}/hotel_booking_noisy.yaml"
        )
        # All assertions should still be evaluated
        assert len(results.assertions) >= 1


class TestHotelBookingInterrupt:
    """Hotel booking with barge-in interruption."""

    async def test_interrupt_scenario_loads(self, orchestrator: ScenarioOrchestrator):
        results = await orchestrator.run(
            scenario=f"{SCENARIO_DIR}/hotel_booking_interrupt.yaml"
        )
        assert isinstance(results, TestResults)
