"""Shared pytest fixtures for the voice test framework."""

from __future__ import annotations

import pytest

from voice_test_framework.core.orchestrator import ScenarioOrchestrator
from voice_test_framework.simulation.audio import AudioStreamSimulator, AudioConfig
from voice_test_framework.simulation.video import VideoStreamSimulator, VideoConfig
from voice_test_framework.simulation.noise import NoiseEngine
from voice_test_framework.simulation.network import NetworkSimulator
from voice_test_framework.simulation.barge_in import BargeInSimulator
from voice_test_framework.tools.registry import MockToolRegistry
from voice_test_framework.tools.builtin_mocks import (
    register_hotel_booking_mocks,
    register_general_mocks,
)
from voice_test_framework.evaluation.framework import EvaluationFramework


@pytest.fixture
def orchestrator() -> ScenarioOrchestrator:
    """Return a fully-wired orchestrator with all simulation layers."""
    orch = ScenarioOrchestrator()

    orch.register_layer(
        "audio",
        AudioStreamSimulator(AudioConfig(tts_provider="builtin", sample_rate=16000)),
    )
    orch.register_layer("video", VideoStreamSimulator(VideoConfig(fps=15)))
    orch.register_layer("environment", NoiseEngine(profile="quiet_room"))
    orch.register_layer("network", NetworkSimulator(profile="perfect"))
    orch.register_layer("barge_in", BargeInSimulator())

    tools = MockToolRegistry()
    register_hotel_booking_mocks(tools)
    register_general_mocks(tools)
    orch.register_layer("tools", tools)

    orch.register_layer("eval", EvaluationFramework())

    return orch


@pytest.fixture
def tool_registry() -> MockToolRegistry:
    """Return a standalone mock tool registry."""
    registry = MockToolRegistry()
    register_hotel_booking_mocks(registry)
    register_general_mocks(registry)
    return registry
