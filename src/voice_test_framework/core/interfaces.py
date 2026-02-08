"""Protocol definitions and core data types for the voice test framework."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Core data types
# ---------------------------------------------------------------------------

@dataclass
class AudioChunk:
    """A single chunk of audio data, as produced by a microphone or TTS."""

    data: bytes
    timestamp: float
    sample_rate: int = 16000
    channels: int = 1
    sample_width: int = 2  # 16-bit PCM


@dataclass
class VideoFrame:
    """A single video frame (raw bytes or encoded)."""

    data: bytes
    timestamp: float
    resolution: tuple[int, int] = (1280, 720)
    format: str = "rgb24"


class ResponseEventType(str, enum.Enum):
    AUDIO = "audio"
    TEXT = "text"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATE_CHANGE = "state_change"
    ERROR = "error"


@dataclass
class ResponseEvent:
    """An event emitted by the system under test."""

    type: ResponseEventType
    timestamp: float
    data: Any = None
    text: str | None = None
    audio: bytes | None = None
    tool_name: str | None = None
    tool_args: dict | None = None
    tool_call_id: str | None = None
    error: str | None = None


class SystemState(str, enum.Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    TOOL_CALLING = "tool_calling"


@dataclass
class ToolResult:
    """Result from a mock tool invocation."""

    success: bool
    data: Any = None
    error: str | None = None
    latency_ms: float = 0.0


@dataclass
class InterruptEvent:
    """Represents a barge-in / interruption event."""

    audio: bytes
    is_true_interrupt: bool = True
    timestamp: float = 0.0


# ---------------------------------------------------------------------------
# Abstract base / protocol definitions
# ---------------------------------------------------------------------------

@runtime_checkable
class SimulationLayer(Protocol):
    """Base protocol that all simulation layers must satisfy."""

    def set_clock(self, clock: Any) -> None:
        """Attach a simulated clock to this layer."""
        ...


@runtime_checkable
class VoiceSystemInterface(Protocol):
    """
    Interface that the system under test must implement.

    The test framework interacts with the SUT exclusively through this
    protocol, making the framework agnostic to the specific voice system.
    """

    async def connect(self) -> None:
        """Establish a connection to the voice system."""
        ...

    async def disconnect(self) -> None:
        """Tear down the connection."""
        ...

    async def push_audio(self, chunk: AudioChunk) -> None:
        """Push audio data (simulates microphone input)."""
        ...

    async def push_video(self, frame: VideoFrame) -> None:
        """Push a video frame (simulates camera / screen-share)."""
        ...

    async def commit_audio(self) -> None:
        """Signal the end of an audio segment (commit the buffer)."""
        ...

    async def create_response(self) -> None:
        """Request the system to generate a response."""
        ...

    def get_response_stream(self) -> AsyncIterator[ResponseEvent]:
        """Return an async iterator over response events."""
        ...

    async def register_tool_handler(
        self, name: str, handler: Callable[..., Any]
    ) -> None:
        """Register a mock tool handler on the system."""
        ...

    async def configure_session(self, **kwargs: Any) -> None:
        """Send session-level configuration to the system."""
        ...

    @property
    def state(self) -> SystemState:
        """Current system state."""
        ...
