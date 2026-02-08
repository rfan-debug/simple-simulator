"""
Voice Test Framework
====================

End-to-end testing framework for real-time voice conversation AI systems.

Quick start::

    from voice_test_framework import (
        ScenarioOrchestrator,
        AudioStreamSimulator,
        NoiseEngine,
        MockToolRegistry,
        EvaluationFramework,
        OpenAIRealtimeAdapter,
    )
"""

from .core.interfaces import (
    AudioChunk,
    VideoFrame,
    ResponseEvent,
    ResponseEventType,
    SystemState,
    SimulationLayer,
    VoiceSystemInterface,
    ToolResult,
    InterruptEvent,
)
from .core.clock import SimulatedClock
from .core.results import TestResults, AssertionResult
from .core.orchestrator import ScenarioOrchestrator

from .simulation.audio import AudioStreamSimulator, AudioConfig
from .simulation.video import VideoStreamSimulator, VideoConfig
from .simulation.barge_in import BargeInSimulator
from .simulation.noise import NoiseEngine
from .simulation.network import NetworkSimulator
from .simulation.physical_world import PhysicalWorldSimulator

from .tools.registry import MockToolRegistry
from .tools.asserter import ToolCallAsserter
from .tools.builtin_mocks import register_hotel_booking_mocks, register_general_mocks

from .evaluation.framework import EvaluationFramework
from .evaluation.latency import LatencyScorer
from .evaluation.accuracy import AccuracyScorer
from .evaluation.naturalness import NaturalnessScorer
from .evaluation.robustness import RobustnessScorer

from .adapters.openai_realtime import OpenAIRealtimeAdapter
from .adapters.custom_websocket import CustomWebSocketAdapter

from .reporting.html_report import HTMLReportGenerator
from .reporting.junit import JUnitXMLWriter
from .reporting.regression import RegressionDetector

__version__ = "0.1.0"

__all__ = [
    # Core
    "AudioChunk",
    "VideoFrame",
    "ResponseEvent",
    "ResponseEventType",
    "SystemState",
    "SimulationLayer",
    "VoiceSystemInterface",
    "ToolResult",
    "InterruptEvent",
    "SimulatedClock",
    "TestResults",
    "AssertionResult",
    "ScenarioOrchestrator",
    # Simulation
    "AudioStreamSimulator",
    "AudioConfig",
    "VideoStreamSimulator",
    "VideoConfig",
    "BargeInSimulator",
    "NoiseEngine",
    "NetworkSimulator",
    "PhysicalWorldSimulator",
    # Tools
    "MockToolRegistry",
    "ToolCallAsserter",
    "register_hotel_booking_mocks",
    "register_general_mocks",
    # Evaluation
    "EvaluationFramework",
    "LatencyScorer",
    "AccuracyScorer",
    "NaturalnessScorer",
    "RobustnessScorer",
    # Adapters
    "OpenAIRealtimeAdapter",
    "CustomWebSocketAdapter",
    # Reporting
    "HTMLReportGenerator",
    "JUnitXMLWriter",
    "RegressionDetector",
]
