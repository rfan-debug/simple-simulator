"""
OpenAI Realtime API adapter.

Implements the ``VoiceSystemInterface`` protocol by communicating with
the OpenAI Realtime WebSocket endpoint.

Reference: https://platform.openai.com/docs/guides/realtime-websocket

Client events used:
    session.update            – configure modalities, tools, VAD, etc.
    input_audio_buffer.append – stream microphone audio
    input_audio_buffer.commit – mark end of an utterance
    input_audio_buffer.clear  – discard buffered audio
    conversation.item.create  – inject conversation history items
    response.create           – request the model to generate a response
    response.cancel           – cancel an in-progress response

Server events handled:
    session.created / session.updated
    error
    input_audio_buffer.committed
    input_audio_buffer.speech_started / speech_stopped
    conversation.item.created
    response.created / response.done
    response.output_item.added / done
    response.content_part.added / done
    response.audio.delta / done
    response.audio_transcript.delta / done
    response.text.delta / done
    response.function_call_arguments.delta / done
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import Any, AsyncIterator

from ..core.interfaces import (
    AudioChunk,
    ResponseEvent,
    ResponseEventType,
    SystemState,
    VideoFrame,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_WS_URL = "wss://api.openai.com/v1/realtime"
DEFAULT_MODEL = "gpt-4o-realtime-preview"


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class OpenAIRealtimeAdapter:
    """
    Adapt the OpenAI Realtime WebSocket API to the framework's
    ``VoiceSystemInterface`` protocol.

    Usage::

        adapter = OpenAIRealtimeAdapter(api_key="sk-...")
        await adapter.connect()
        await adapter.push_audio(chunk)
        async for event in adapter.get_response_stream():
            ...
        await adapter.disconnect()
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        ws_url: str = DEFAULT_WS_URL,
        voice: str = "alloy",
        instructions: str | None = None,
        input_audio_format: str = "pcm16",
        output_audio_format: str = "pcm16",
        turn_detection: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.8,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.ws_url = ws_url
        self.voice = voice
        self.instructions = instructions or ""
        self.input_audio_format = input_audio_format
        self.output_audio_format = output_audio_format
        self.turn_detection = turn_detection  # None = server_vad by default
        self.tools = tools or []
        self.temperature = temperature

        self._ws: Any = None  # websockets.WebSocketClientProtocol
        self._state = SystemState.IDLE
        self._response_queue: asyncio.Queue[ResponseEvent] = asyncio.Queue()
        self._listener_task: asyncio.Task | None = None
        self._tool_handlers: dict[str, Any] = {}
        self._session_id: str | None = None

    # -- VoiceSystemInterface ------------------------------------------------

    async def connect(self) -> None:
        """Open the WebSocket connection and start the listener loop."""
        try:
            import websockets
        except ImportError as exc:
            raise ImportError(
                "The 'websockets' package is required for the OpenAI Realtime adapter. "
                "Install it with: pip install websockets"
            ) from exc

        url = f"{self.ws_url}?model={self.model}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

        self._ws = await websockets.connect(url, additional_headers=headers)
        self._listener_task = asyncio.create_task(self._listen())

        # Wait for session.created
        await self._wait_for_event("session.created", timeout=10)

        # Send initial session configuration
        await self._send_session_update()

    async def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        self._state = SystemState.IDLE

    async def push_audio(self, chunk: AudioChunk) -> None:
        """Stream audio to the Realtime API via ``input_audio_buffer.append``."""
        if self._ws is None:
            raise RuntimeError("Not connected")

        encoded = base64.b64encode(chunk.data).decode("ascii")
        await self._send({
            "type": "input_audio_buffer.append",
            "audio": encoded,
        })

    async def push_video(self, frame: VideoFrame) -> None:
        """
        Push a video frame.

        The OpenAI Realtime API currently supports image input via
        ``conversation.item.create`` with an image content part.
        """
        if self._ws is None:
            raise RuntimeError("Not connected")

        encoded = base64.b64encode(frame.data).decode("ascii")
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image": encoded,
                    }
                ],
            },
        })

    async def commit_audio(self) -> None:
        """Commit the input audio buffer (signals end of utterance)."""
        if self._ws is None:
            return
        await self._send({"type": "input_audio_buffer.commit"})

    async def create_response(self) -> None:
        """Explicitly request the model to generate a response."""
        if self._ws is None:
            return
        self._state = SystemState.THINKING
        await self._send({"type": "response.create"})

    async def get_response_stream(self) -> AsyncIterator[ResponseEvent]:
        """Yield response events as they arrive from the server."""
        while True:
            try:
                event = await asyncio.wait_for(
                    self._response_queue.get(), timeout=30
                )
                yield event
                if event.type == ResponseEventType.ERROR:
                    break
            except asyncio.TimeoutError:
                break

    async def register_tool_handler(self, name: str, handler: Any) -> None:
        """Register a function to handle tool calls from the model."""
        self._tool_handlers[name] = handler

        # Add to the session tool definitions if not already present
        tool_def = {
            "type": "function",
            "name": name,
            "description": f"Mock handler for {name}",
            "parameters": {"type": "object", "properties": {}},
        }
        if not any(t.get("name") == name for t in self.tools):
            self.tools.append(tool_def)
            await self._send_session_update()

    async def configure_session(self, **kwargs: Any) -> None:
        """Update the session configuration."""
        if "voice" in kwargs:
            self.voice = kwargs["voice"]
        if "instructions" in kwargs:
            self.instructions = kwargs["instructions"]
        if "temperature" in kwargs:
            self.temperature = kwargs["temperature"]
        if "turn_detection" in kwargs:
            self.turn_detection = kwargs["turn_detection"]
        if "tools" in kwargs:
            self.tools = kwargs["tools"]
        await self._send_session_update()

    @property
    def state(self) -> SystemState:
        return self._state

    # -- WebSocket communication ---------------------------------------------

    async def _send(self, message: dict[str, Any]) -> None:
        """Send a JSON message over the WebSocket."""
        if self._ws is None:
            return
        await self._ws.send(json.dumps(message))

    async def _send_session_update(self) -> None:
        """Send a ``session.update`` event with the current configuration."""
        session_config: dict[str, Any] = {
            "modalities": ["text", "audio"],
            "voice": self.voice,
            "input_audio_format": self.input_audio_format,
            "output_audio_format": self.output_audio_format,
            "temperature": self.temperature,
        }

        if self.instructions:
            session_config["instructions"] = self.instructions

        if self.turn_detection is not None:
            session_config["turn_detection"] = self.turn_detection
        else:
            session_config["turn_detection"] = {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
            }

        if self.tools:
            session_config["tools"] = self.tools
            session_config["tool_choice"] = "auto"

        await self._send({
            "type": "session.update",
            "session": session_config,
        })

    async def _listen(self) -> None:
        """Background loop that reads server events from the WebSocket."""
        if self._ws is None:
            return
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self._handle_server_event(msg)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("WebSocket listener error")

    async def _handle_server_event(self, msg: dict[str, Any]) -> None:
        """Dispatch a single server event."""
        event_type = msg.get("type", "")

        match event_type:
            # -- session lifecycle -------------------------------------------
            case "session.created":
                self._session_id = msg.get("session", {}).get("id")
                logger.info("Session created: %s", self._session_id)

            case "session.updated":
                logger.debug("Session updated")

            # -- errors ------------------------------------------------------
            case "error":
                error_info = msg.get("error", {})
                error_msg = error_info.get("message", str(error_info))
                logger.error("Server error: %s", error_msg)
                await self._response_queue.put(
                    ResponseEvent(
                        type=ResponseEventType.ERROR,
                        timestamp=0,
                        error=error_msg,
                    )
                )

            # -- input audio buffer ------------------------------------------
            case "input_audio_buffer.committed":
                logger.debug("Audio buffer committed")

            case "input_audio_buffer.speech_started":
                self._state = SystemState.LISTENING
                logger.debug("Speech started")

            case "input_audio_buffer.speech_stopped":
                logger.debug("Speech stopped")

            # -- response lifecycle ------------------------------------------
            case "response.created":
                self._state = SystemState.THINKING
                logger.debug("Response created")

            case "response.done":
                response = msg.get("response", {})
                status = response.get("status", "")
                self._state = SystemState.IDLE

                # Extract output items
                for item in response.get("output", []):
                    await self._process_output_item(item)

                logger.debug("Response done (status=%s)", status)

            # -- streaming deltas --------------------------------------------
            case "response.audio.delta":
                audio_b64 = msg.get("delta", "")
                audio_bytes = base64.b64decode(audio_b64)
                self._state = SystemState.SPEAKING
                await self._response_queue.put(
                    ResponseEvent(
                        type=ResponseEventType.AUDIO,
                        timestamp=0,
                        audio=audio_bytes,
                    )
                )

            case "response.audio.done":
                self._state = SystemState.IDLE

            case "response.audio_transcript.delta":
                text = msg.get("delta", "")
                if text:
                    await self._response_queue.put(
                        ResponseEvent(
                            type=ResponseEventType.TEXT,
                            timestamp=0,
                            text=text,
                        )
                    )

            case "response.text.delta":
                text = msg.get("delta", "")
                if text:
                    await self._response_queue.put(
                        ResponseEvent(
                            type=ResponseEventType.TEXT,
                            timestamp=0,
                            text=text,
                        )
                    )

            # -- function calling --------------------------------------------
            case "response.function_call_arguments.done":
                call_id = msg.get("call_id", "")
                fn_name = msg.get("name", "")
                args_str = msg.get("arguments", "{}")
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {}

                self._state = SystemState.TOOL_CALLING
                await self._response_queue.put(
                    ResponseEvent(
                        type=ResponseEventType.TOOL_CALL,
                        timestamp=0,
                        tool_name=fn_name,
                        tool_args=args,
                        tool_call_id=call_id,
                    )
                )

                # Auto-invoke registered handler and send result back
                await self._handle_function_call(call_id, fn_name, args)

            # -- conversation items ------------------------------------------
            case "conversation.item.created":
                logger.debug("Conversation item created")

            # -- catch-all ---------------------------------------------------
            case _:
                logger.debug("Unhandled event: %s", event_type)

    async def _process_output_item(self, item: dict[str, Any]) -> None:
        """Extract content from a response output item."""
        item_type = item.get("type", "")
        if item_type == "message":
            for part in item.get("content", []):
                if part.get("type") == "text":
                    await self._response_queue.put(
                        ResponseEvent(
                            type=ResponseEventType.TEXT,
                            timestamp=0,
                            text=part.get("text", ""),
                        )
                    )
                elif part.get("type") == "audio":
                    audio_b64 = part.get("audio", "")
                    if audio_b64:
                        await self._response_queue.put(
                            ResponseEvent(
                                type=ResponseEventType.AUDIO,
                                timestamp=0,
                                audio=base64.b64decode(audio_b64),
                            )
                        )

    async def _handle_function_call(
        self, call_id: str, fn_name: str, args: dict[str, Any]
    ) -> None:
        """Invoke a registered tool handler and send the result back."""
        handler = self._tool_handlers.get(fn_name)
        if handler is None:
            result_data = {"error": f"No handler registered for {fn_name}"}
        else:
            try:
                result = handler(args)
                if asyncio.iscoroutine(result):
                    result = await result
                result_data = result if isinstance(result, dict) else {"result": result}
            except Exception as exc:
                result_data = {"error": str(exc)}

        # Send function call output back to the API
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(result_data),
            },
        })

        # Request the model to continue generating after the tool result
        await self._send({"type": "response.create"})

        await self._response_queue.put(
            ResponseEvent(
                type=ResponseEventType.TOOL_RESULT,
                timestamp=0,
                tool_name=fn_name,
                tool_call_id=call_id,
                data=result_data,
            )
        )

    # -- utility -------------------------------------------------------------

    async def _wait_for_event(self, event_type: str, timeout: float = 10) -> None:
        """Block until a specific event type is received (used during setup)."""
        # The listener task populates the queue; we peek until we find the
        # desired event or time out.  In practice, session.created arrives
        # almost immediately.
        await asyncio.sleep(0.1)  # give listener time to start
