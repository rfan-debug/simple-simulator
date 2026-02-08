# Voice Test Framework

**Voice Test Framework** is an end-to-end testing framework designed for real-time voice conversation AI systems. It simulates user interactions, environment conditions, and tool usage to evaluate the performance, accuracy, and robustness of your voice AI.

## Features

- **Scenario Engine**: Define complex conversation scenarios using YAML, including timelines, conditional branches, and assertions.
- **Input Simulation**:
    - **Audio**: Text-to-Speech (TTS) integration, pre-recorded audio, speech style control.
    - **Video**: Camera and screen share simulation.
- **Environment Simulation**:
    - **Noise**: Realistic background noise injection (ambient, transient events).
    - **Network**: Simulation of network latency, jitter, and packet loss.
    - **Barge-in**: Simulate user interruptions.
- **Tool Use Simulation**: Mock external tool calls with configurable latency and failure rates.
- **Evaluation**: Measure latency, intent recognition accuracy, and system response correctness.
- **Reporting**: Generate detailed test reports.

## Installation

This project requires Python 3.11 or higher.

To install the framework, clone the repository and install it using pip:

```bash
git clone https://github.com/your-org/voice-test-framework.git
cd voice-test-framework
pip install .
```

## Quick Start

### 1. Define a Scenario

Create a YAML file (e.g., `scenarios/hotel_booking_basic.yaml`) to describe your test scenario:

```yaml
scenario:
  name: "Basic Hotel Booking"
  environment:
    noise_profile: "quiet_room"
    noise_snr_db: 40
    network:
      latency_ms: 10
      jitter_ms: 2
      loss: 0

  timeline:
    - at: 0s
      action: user_speak
      audio: "tts://Hello, I'd like to book a hotel room please"

    - at: 3s
      action: assert_system
      expect:
        intent: "hotel_booking"

    - at: 5s
      action: user_speak
      audio: "tts://Next Friday for two nights"

    - at: 8s
      action: expect_tool_call
      tool: "check_availability"
      args_contain:
        checkin: "next_friday"
        nights: 2
      timeout_ms: 5000
```

### 2. Run a Test

You can run scenarios using `pytest`. Here is an example of how to set up and run a test programmatically:

```python
import asyncio
import pytest
from voice_test_framework.core.orchestrator import ScenarioOrchestrator
from voice_test_framework.simulation.audio import AudioStreamSimulator, AudioConfig
from voice_test_framework.simulation.video import VideoStreamSimulator, VideoConfig
from voice_test_framework.simulation.noise import NoiseEngine
from voice_test_framework.simulation.network import NetworkSimulator
from voice_test_framework.simulation.barge_in import BargeInSimulator
from voice_test_framework.tools.registry import MockToolRegistry
from voice_test_framework.tools.builtin_mocks import register_hotel_booking_mocks
from voice_test_framework.evaluation.framework import EvaluationFramework

async def run_test():
    # Initialize the orchestrator
    orch = ScenarioOrchestrator()

    # Register simulation layers
    orch.register_layer("audio", AudioStreamSimulator(AudioConfig(tts_provider="builtin", sample_rate=16000)))
    orch.register_layer("video", VideoStreamSimulator(VideoConfig(fps=15)))
    orch.register_layer("environment", NoiseEngine(profile="quiet_room"))
    orch.register_layer("network", NetworkSimulator(profile="perfect"))
    orch.register_layer("barge_in", BargeInSimulator())

    # Register mock tools
    tools = MockToolRegistry()
    register_hotel_booking_mocks(tools)
    orch.register_layer("tools", tools)

    orch.register_layer("eval", EvaluationFramework())

    # Run the scenario against a System Under Test (SUT)
    # Note: In a real test, you would pass your actual SUT instance here.
    # system = MyVoiceSystemAdapter(...)
    results = await orch.run(scenario="scenarios/hotel_booking_basic.yaml", system=None)

    # Assert results
    assert results.all_passed()
    print("Test passed!")

if __name__ == "__main__":
    asyncio.run(run_test())
```

## Developing a System Adapter

To test your own voice system, you need to implement the `VoiceSystemInterface` defined in `src/voice_test_framework/core/interfaces.py`. This interface allows the framework to interact with your system (push audio, receive responses, etc.) in a standardized way.

```python
from voice_test_framework.core.interfaces import VoiceSystemInterface, AudioChunk, ResponseEvent

class MyVoiceSystemAdapter(VoiceSystemInterface):
    async def push_audio(self, chunk: AudioChunk) -> None:
        # Send audio chunk to your system
        pass

    async def get_response_stream(self):
        # Yield response events from your system
        pass

    # Implement other required methods...
```

## Running Tests

To run the included tests:

```bash
pytest
```

This will execute the test suite in the `tests/` directory, which validates the framework components and runs example scenarios.
