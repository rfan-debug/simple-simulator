"""
Generic WebSocket adapter for custom voice systems.

Provides a thin abstraction for systems that communicate over WebSocket
with a custom protocol.  Subclass and override the ``_encode_*`` and
``_decode_*`` methods to match your system's message format.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Any, AsyncIterator, Callable

from ..core.interfaces import (
    AudioChunk,
    ResponseEvent,
    ResponseEventType,
    SystemState,
    VideoFrame,
)

logger = logging.getLogger(__name__)


class CustomWebSocketAdapter:
    """
    Adapt an arbitrary WebSocket-based voice system to the framework's
    ``VoiceSystemInterface``.

    Override the ``_encode_*`` / ``_decode_*`` family of methods to match
    your system's wire format.
    """

    def __init__(
        self,
        ws_url: str,
        headers: dict[str, str] | None = None,
        audio_format: str = "pcm16",
        sample_rate: int = 16000,
    ):
        self.ws_url = ws_url
        self.headers = headers or {}
        self.audio_format = audio_format
        self.sample_rate = sample_rate

        self._ws: Any = None
        self._state = SystemState.IDLE
        self._response_queue: asyncio.Queue[ResponseEvent] = asyncio.Queue()
        self._listener_task: asyncio.Task | None = None
        self._tool_handlers: dict[str, Callable[..., Any]] = {}

    # -- connection ----------------------------------------------------------

    async def connect(self) -> None:
        try:
            import websockets
        except ImportError as exc:
            raise ImportError("pip install websockets") from exc

        self._ws = await websockets.connect(
            self.ws_url, additional_headers=self.headers
        )
        self._listener_task = asyncio.create_task(self._listen())

    async def disconnect(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._state = SystemState.IDLE

    # -- VoiceSystemInterface ------------------------------------------------

    async def push_audio(self, chunk: AudioChunk) -> None:
        msg = self._encode_audio(chunk)
        await self._send(msg)

    async def push_video(self, frame: VideoFrame) -> None:
        msg = self._encode_video(frame)
        await self._send(msg)

    async def commit_audio(self) -> None:
        await self._send(self._encode_commit())

    async def create_response(self) -> None:
        self._state = SystemState.THINKING
        await self._send(self._encode_response_request())

    async def get_response_stream(self) -> AsyncIterator[ResponseEvent]:
        while True:
            try:
                event = await asyncio.wait_for(
                    self._response_queue.get(), timeout=30
                )
                yield event
            except asyncio.TimeoutError:
                break

    async def register_tool_handler(self, name: str, handler: Any) -> None:
        self._tool_handlers[name] = handler

    async def configure_session(self, **kwargs: Any) -> None:
        msg = self._encode_session_config(kwargs)
        await self._send(msg)

    @property
    def state(self) -> SystemState:
        return self._state

    # -- encoding (override for custom protocols) ----------------------------

    def _encode_audio(self, chunk: AudioChunk) -> dict[str, Any]:
        return {
            "type": "audio",
            "data": base64.b64encode(chunk.data).decode(),
            "sample_rate": chunk.sample_rate,
        }

    def _encode_video(self, frame: VideoFrame) -> dict[str, Any]:
        return {
            "type": "video",
            "data": base64.b64encode(frame.data).decode(),
            "resolution": list(frame.resolution),
        }

    def _encode_commit(self) -> dict[str, Any]:
        return {"type": "commit"}

    def _encode_response_request(self) -> dict[str, Any]:
        return {"type": "request_response"}

    def _encode_session_config(self, config: dict[str, Any]) -> dict[str, Any]:
        return {"type": "session_config", **config}

    # -- decoding (override for custom protocols) ----------------------------

    def _decode_event(self, msg: dict[str, Any]) -> ResponseEvent | None:
        """Convert a raw server message to a ``ResponseEvent``."""
        msg_type = msg.get("type", "")

        if msg_type == "audio":
            audio = base64.b64decode(msg.get("data", ""))
            self._state = SystemState.SPEAKING
            return ResponseEvent(
                type=ResponseEventType.AUDIO, timestamp=0, audio=audio
            )
        elif msg_type == "text":
            self._state = SystemState.SPEAKING
            return ResponseEvent(
                type=ResponseEventType.TEXT, timestamp=0, text=msg.get("text", "")
            )
        elif msg_type == "tool_call":
            self._state = SystemState.TOOL_CALLING
            return ResponseEvent(
                type=ResponseEventType.TOOL_CALL,
                timestamp=0,
                tool_name=msg.get("name", ""),
                tool_args=msg.get("arguments", {}),
                tool_call_id=msg.get("call_id", ""),
            )
        elif msg_type == "error":
            return ResponseEvent(
                type=ResponseEventType.ERROR,
                timestamp=0,
                error=msg.get("message", "Unknown error"),
            )
        return None

    # -- internals -----------------------------------------------------------

    async def _send(self, message: dict[str, Any]) -> None:
        if self._ws is None:
            return
        await self._ws.send(json.dumps(message))

    async def _listen(self) -> None:
        if self._ws is None:
            return
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                event = self._decode_event(msg)
                if event is not None:
                    await self._response_queue.put(event)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Listener error")
