"""Noise robustness matrix tests.

Parametrised tests that run the same scenario at different SNR levels
to build a robustness profile.
"""

from __future__ import annotations

import pytest

from voice_test_framework.core.orchestrator import ScenarioOrchestrator
from voice_test_framework.core.results import TestResults
from voice_test_framework.simulation.noise import NoiseEngine


SCENARIO = "scenarios/hotel_booking_basic.yaml"


class TestNoiseRobustness:

    @pytest.mark.parametrize("snr_db", [40, 25, 15, 10, 5])
    async def test_noise_level(
        self, orchestrator: ScenarioOrchestrator, snr_db: int
    ):
        """Run the basic scenario at different noise levels."""
        env: NoiseEngine = orchestrator.layers["environment"]
        env.set_snr(snr_db)

        results = await orchestrator.run(scenario=SCENARIO)
        results.tag(f"snr_{snr_db}")

        assert isinstance(results, TestResults)
        # At very low SNR the framework should still execute without crashing
        assert len(results.assertions) > 0

    async def test_noise_profile_switching(
        self, orchestrator: ScenarioOrchestrator
    ):
        """Switching noise profiles mid-run should not crash."""
        env: NoiseEngine = orchestrator.layers["environment"]
        env.set_profile("cafe")
        results1 = await orchestrator.run(scenario=SCENARIO)

        env.set_profile("street")
        results2 = await orchestrator.run(scenario=SCENARIO)

        assert isinstance(results1, TestResults)
        assert isinstance(results2, TestResults)
