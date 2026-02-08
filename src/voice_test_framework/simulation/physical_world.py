"""Physical world interaction simulator: device events, environment changes."""

from __future__ import annotations

import asyncio
from typing import Any

from .noise import NoiseEngine


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS: dict[str, dict[str, Any]] = {
    "multitasking": {
        "description": "User is doing other things while on the call",
        "events": [
            {"type": "typing", "affects": "background_noise"},
            {"type": "walking", "affects": "mic_movement"},
            {"type": "driving", "affects": "ambient_noise_change"},
        ],
    },
    "device_events": {
        "description": "Device-related events that affect audio",
        "events": [
            {
                "type": "switch_to_speaker",
                "affects": "audio_quality_change",
                "echo_introduced": True,
            },
            {
                "type": "bluetooth_switch",
                "affects": "brief_audio_gap",
                "gap_ms": 500,
            },
            {
                "type": "notification_sound",
                "affects": "transient_noise",
            },
            {
                "type": "app_switch",
                "affects": "screen_content_change",
            },
        ],
    },
    "environment_change": {
        "description": "Physical environment transitions",
        "events": [
            {
                "type": "enter_room",
                "transition": ("street", "quiet_room"),
                "transition_duration_s": 3,
                "affects": "ambient_noise_change",
            },
            {
                "type": "someone_enters",
                "introduces": "competing_speech",
                "affects": "competing_speech",
            },
            {
                "type": "door_closes",
                "noise_profile_change": "more_isolated",
                "affects": "ambient_noise_change",
            },
        ],
    },
}


class PhysicalWorldSimulator:
    """
    Simulate real-world physical events that affect voice conversations.

    Covers multitasking, device events, and environment transitions.
    """

    SCENARIOS = SCENARIOS

    def __init__(self) -> None:
        self._clock: Any = None

    def set_clock(self, clock: Any) -> None:
        self._clock = clock

    async def simulate_scenario(
        self,
        scenario_name: str,
        audio_sim: Any | None = None,
        noise_engine: NoiseEngine | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run through all events in a named scenario.

        Returns a log of actions taken.
        """
        scenario = self.SCENARIOS.get(scenario_name)
        if scenario is None:
            return []

        log: list[dict[str, Any]] = []

        for event in scenario["events"]:
            action = await self._apply_event(event, audio_sim, noise_engine)
            log.append({"event": event, "action": action})

        return log

    async def _apply_event(
        self,
        event: dict[str, Any],
        audio_sim: Any | None,
        noise_engine: NoiseEngine | None,
    ) -> str:
        affects = event.get("affects", "")

        match affects:
            case "audio_quality_change":
                # Switching to speaker introduces echo
                if audio_sim is not None and hasattr(audio_sim, "enable_echo"):
                    audio_sim.enable_echo(delay_ms=150, decay=0.3)
                return "echo_enabled"

            case "brief_audio_gap":
                gap_ms = event.get("gap_ms", 500)
                await asyncio.sleep(gap_ms / 1000)
                return f"audio_gap_{gap_ms}ms"

            case "ambient_noise_change":
                if noise_engine is not None:
                    transition = event.get("transition")
                    if transition:
                        from_profile, to_profile = transition
                        noise_engine.crossfade_profile(
                            from_profile,
                            to_profile,
                            duration=event.get("transition_duration_s", 3),
                        )
                    return "noise_profile_changed"
                return "no_noise_engine"

            case "transient_noise":
                if noise_engine is not None:
                    await noise_engine.inject("transient", event.get("type", "notification"))
                    return "transient_injected"
                return "no_noise_engine"

            case "competing_speech":
                if noise_engine is not None:
                    await noise_engine.inject("competing_speech")
                    return "competing_speech_injected"
                return "no_noise_engine"

            case "background_noise":
                if noise_engine is not None:
                    await noise_engine.inject("transient", "keyboard")
                    return "keyboard_noise_injected"
                return "no_noise_engine"

            case "mic_movement":
                # Simulate brief audio artefacts from physical movement
                return "mic_movement_simulated"

            case "screen_content_change":
                return "screen_content_changed"

            case _:
                return f"unknown_effect_{affects}"
