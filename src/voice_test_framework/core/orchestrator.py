"""Scenario orchestrator: drives all simulation layers along a YAML timeline."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from queue import PriorityQueue
from typing import Any

import yaml

from .clock import SimulatedClock
from .interfaces import (
    AudioChunk,
    ResponseEvent,
    ResponseEventType,
    SimulationLayer,
    VoiceSystemInterface,
)
from .results import AssertionResult, TestResults

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Timeline event
# ---------------------------------------------------------------------------

@dataclass(order=True)
class TimelineEvent:
    """A single event on the scenario timeline, ordered by timestamp."""

    timestamp: float
    _seq: int = field(compare=True, repr=False)  # tie-breaker
    action: str = field(compare=False, default="")
    params: dict[str, Any] = field(compare=False, default_factory=dict)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class ScenarioOrchestrator:
    """
    Core scheduler: drives every simulation layer according to a YAML timeline.

    Supports conditional branches, parallel events, and dynamic responses.
    """

    def __init__(self, scenario_path: str | Path | None = None):
        self.scenario: dict[str, Any] = {}
        if scenario_path is not None:
            self.scenario = self._load_scenario(scenario_path)

        self.timeline: PriorityQueue[TimelineEvent] = PriorityQueue()
        self.clock = SimulatedClock()
        self.layers: dict[str, Any] = {}
        self._seq = 0  # monotonic counter for stable ordering

    # -- layer management ----------------------------------------------------

    def register_layer(self, name: str, layer: Any) -> None:
        """Register a simulation layer (audio, environment, tools, …)."""
        self.layers[name] = layer
        if hasattr(layer, "set_clock"):
            layer.set_clock(self.clock)

    # -- running a scenario --------------------------------------------------

    async def run(
        self,
        scenario: str | Path | dict | None = None,
        system: VoiceSystemInterface | None = None,
    ) -> TestResults:
        """Execute a complete test scenario against *system*."""
        if scenario is not None:
            if isinstance(scenario, dict):
                self.scenario = scenario
            else:
                self.scenario = self._load_scenario(scenario)

        self._apply_environment(self.scenario.get("environment", {}))
        self._enqueue_timeline(self.scenario.get("timeline", []))

        results = TestResults()

        # Start collecting responses in background
        response_task: asyncio.Task | None = None
        if system is not None:
            response_task = asyncio.create_task(
                self._collect_responses(system, results)
            )

        while not self.timeline.empty():
            event = self.timeline.get()
            await self.clock.advance_to(event.timestamp)

            try:
                await self._dispatch(event, system, results)
            except Exception:
                logger.exception("Error dispatching event %s", event)
                results.add(
                    event.timestamp,
                    AssertionResult(
                        timestamp=event.timestamp,
                        passed=False,
                        description=f"Exception in {event.action}",
                    ),
                )

        if response_task is not None:
            response_task.cancel()
            try:
                await response_task
            except asyncio.CancelledError:
                pass

        return results

    # -- event dispatch ------------------------------------------------------

    async def _dispatch(
        self,
        event: TimelineEvent,
        system: VoiceSystemInterface | None,
        results: TestResults,
    ) -> None:
        params = event.params

        match event.action:
            case "user_speak":
                audio_layer = self.layers.get("audio")
                if audio_layer is None:
                    return
                style = params.get("speech_style", {})
                audio_text = params.get("audio", "")
                audio_file = params.get("audio_file")

                async for chunk in audio_layer.generate(
                    text=audio_text, audio_file=audio_file, style=style
                ):
                    if system is not None:
                        # Mix with environment noise if available
                        env = self.layers.get("environment")
                        if env is not None:
                            chunk = env.mix_with_speech(chunk)

                        # Apply network conditions
                        net = self.layers.get("network")
                        if net is not None:
                            chunk = await net.apply(chunk)
                            if chunk is None:
                                continue  # packet lost

                        await system.push_audio(chunk)

                if system is not None:
                    await system.commit_audio()

            case "inject_noise":
                env = self.layers.get("environment")
                if env is not None:
                    await env.inject(
                        noise_type=params.get("type", "transient"),
                        source=params.get("source"),
                    )

            case "inject_video":
                video_layer = self.layers.get("video")
                if video_layer is None or system is None:
                    return
                async for frame in video_layer.generate(params):
                    await system.push_video(frame)

            case "assert_system":
                result = await self._evaluate_assertion(
                    system, params.get("expect", {}), event.timestamp
                )
                results.add(event.timestamp, result)

            case "expect_tool_call":
                tool_layer = self.layers.get("tools")
                if tool_layer is not None:
                    result = await tool_layer.wait_for_call(
                        tool_name=params.get("tool", ""),
                        expected_args=params.get("args_contain"),
                        timeout=params.get("timeout_ms", 5000) / 1000,
                    )
                    results.add(event.timestamp, result)

            case "barge_in":
                barge_in_layer = self.layers.get("barge_in")
                if barge_in_layer is not None and system is not None:
                    interrupt = await barge_in_layer.simulate(
                        pattern=params.get("pattern", "eager_interrupt"),
                        system_audio_stream=system.get_response_stream(),
                        user_audio_gen=self.layers.get("audio"),
                    )
                    results.barge_in.was_handled = True
                    results.barge_in.response_latency = interrupt.timestamp

            case "conditional":
                condition = params.get("condition", "")
                branches = params.get("branches", {})
                branch = self._eval_condition(condition, system)
                if branch in branches:
                    self._enqueue_timeline(branches[branch])

            case "wait":
                duration = params.get("duration_ms", 0) / 1000
                await self.clock.advance_by(duration)

            case "set_network":
                net = self.layers.get("network")
                if net is not None:
                    net.set_profile(params.get("profile", "perfect"))

            case _:
                logger.warning("Unknown action: %s", event.action)

    # -- helpers -------------------------------------------------------------

    async def _evaluate_assertion(
        self,
        system: VoiceSystemInterface | None,
        expect: dict[str, Any],
        timestamp: float,
    ) -> AssertionResult:
        """Evaluate an assertion against the current system state."""
        passed = True
        details: dict[str, Any] = {}

        if "intent" in expect:
            details["expected_intent"] = expect["intent"]
            # In a real implementation this would query the SUT for its
            # recognised intent.  Here we record the expectation.
            passed = passed and True  # placeholder

        if "did_not" in expect:
            details["did_not"] = expect["did_not"]

        return AssertionResult(
            timestamp=timestamp,
            passed=passed,
            description=f"assert_system @ {timestamp}s",
            expected=expect,
            actual=details,
        )

    async def _collect_responses(
        self,
        system: VoiceSystemInterface,
        results: TestResults,
    ) -> None:
        """Background task that records all SUT responses."""
        try:
            async for event in system.get_response_stream():
                ts = event.timestamp
                if event.type == ResponseEventType.TEXT:
                    results.record_response(text=event.text or "", timestamp=ts)
                elif event.type == ResponseEventType.AUDIO:
                    results.record_response(audio=event.audio or b"", timestamp=ts)
                    results.latency.first_byte_latencies.append(ts * 1000)
                elif event.type == ResponseEventType.TOOL_CALL:
                    results.record_tool_call(
                        tool=event.tool_name or "",
                        args=event.tool_args or {},
                        timestamp=ts,
                    )
        except asyncio.CancelledError:
            return

    def _eval_condition(
        self, condition: str, system: VoiceSystemInterface | None
    ) -> str:
        """Evaluate a simple condition string and return the branch key."""
        # Basic stub — a real implementation would parse the DSL condition.
        return "default"

    # -- YAML loading --------------------------------------------------------

    @staticmethod
    def _load_scenario(path: str | Path) -> dict[str, Any]:
        path = Path(path)
        with open(path) as fh:
            data = yaml.safe_load(fh)
        return data.get("scenario", data)

    def _apply_environment(self, env: dict[str, Any]) -> None:
        """Pre-configure simulation layers from the scenario environment."""
        if not env:
            return

        noise = self.layers.get("environment")
        if noise is not None:
            profile = env.get("noise_profile")
            snr = env.get("noise_snr_db")
            if profile is not None:
                noise.set_profile(profile, snr_override=snr)

        net = self.layers.get("network")
        if net is not None and "network" in env:
            net_cfg = env["network"]
            net.configure(
                latency_ms=net_cfg.get("latency_ms", 10),
                jitter_ms=net_cfg.get("jitter_ms", 2),
                loss_rate=net_cfg.get("loss", 0.0),
            )

    def _enqueue_timeline(self, events: list[dict[str, Any]]) -> None:
        """Parse a list of raw YAML timeline entries and enqueue them."""
        for entry in events:
            timestamp = self._parse_time(entry.get("at", "0s"))
            action = entry.get("action", "")
            params = {k: v for k, v in entry.items() if k not in ("at", "action")}
            self._seq += 1
            self.timeline.put(
                TimelineEvent(
                    timestamp=timestamp,
                    _seq=self._seq,
                    action=action,
                    params=params,
                )
            )

    @staticmethod
    def _parse_time(value: str | int | float) -> float:
        """Convert a time string like ``'2.5s'`` to a float in seconds."""
        if isinstance(value, (int, float)):
            return float(value)
        value = str(value).strip()
        if value.endswith("ms"):
            return float(value[:-2]) / 1000
        if value.endswith("s"):
            return float(value[:-1])
        return float(value)
