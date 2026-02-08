"""Video / screen-share stream simulator."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import numpy as np

from ..core.interfaces import VideoFrame


@dataclass
class VideoConfig:
    """Configuration for the video stream simulator."""

    fps: int = 30
    resolution: tuple[int, int] = (1280, 720)


class CameraSimGenerator:
    """Generate synthetic camera frames (solid colour with metadata overlay)."""

    def render(
        self,
        scene: str = "office_desk",
        face_expression: str | None = None,
        gesture: str | None = None,
        objects_in_view: list[str] | None = None,
        lighting: str = "normal",
        resolution: tuple[int, int] = (1280, 720),
        num_frames: int = 1,
    ) -> list[bytes]:
        w, h = resolution
        frames: list[bytes] = []
        for _ in range(num_frames):
            # Generate a deterministic colour based on scene name
            colour_seed = hash(scene) % 256
            frame = np.full((h, w, 3), colour_seed, dtype=np.uint8)
            frames.append(frame.tobytes())
        return frames


class ScreenShareGenerator:
    """Generate synthetic screen-share frames."""

    def render(
        self,
        app: str = "browser",
        content: str = "",
        cursor_path: list[tuple[int, int]] | None = None,
        highlight: dict | None = None,
        resolution: tuple[int, int] = (1280, 720),
        num_frames: int = 1,
    ) -> list[bytes]:
        w, h = resolution
        frames: list[bytes] = []
        for _ in range(num_frames):
            frame = np.full((h, w, 3), 40, dtype=np.uint8)  # dark background
            frames.append(frame.tobytes())
        return frames


class DocumentScanGenerator:
    """Generate synthetic document scan frames."""

    def render(
        self,
        document_type: str = "pdf",
        resolution: tuple[int, int] = (1280, 720),
        num_frames: int = 1,
    ) -> list[bytes]:
        w, h = resolution
        frames: list[bytes] = []
        for _ in range(num_frames):
            frame = np.full((h, w, 3), 240, dtype=np.uint8)  # white page
            frames.append(frame.tobytes())
        return frames


class VideoStreamSimulator:
    """
    Simulate visual input channels.

    - Camera: face, gestures, environment
    - Screen share: application UIs, documents, web pages
    - Static images / document scans
    """

    def __init__(self, config: VideoConfig | None = None, **kwargs: Any):
        if config is None:
            config = VideoConfig(**{k: v for k, v in kwargs.items() if k in ("fps", "resolution")})
        self.fps = config.fps
        self.resolution = config.resolution
        self.generators = {
            "camera": CameraSimGenerator(),
            "screen": ScreenShareGenerator(),
            "document": DocumentScanGenerator(),
        }
        self._clock: Any = None

    def set_clock(self, clock: Any) -> None:
        self._clock = clock

    def _now(self) -> float:
        if self._clock is not None:
            return self._clock.now()
        return 0.0

    async def generate(self, event: dict[str, Any]) -> AsyncIterator[VideoFrame]:
        """Generate video frames according to *event* parameters."""
        source = event.get("source", "camera")
        duration = event.get("duration", 1)
        num_frames = int(self.fps * duration)

        match source:
            case "camera":
                raw_frames = self.generators["camera"].render(
                    scene=event.get("scene", "office_desk"),
                    face_expression=event.get("expression"),
                    gesture=event.get("gesture"),
                    objects_in_view=event.get("objects", []),
                    lighting=event.get("lighting", "normal"),
                    resolution=self.resolution,
                    num_frames=num_frames,
                )
            case "screen":
                raw_frames = self.generators["screen"].render(
                    app=event.get("app", "browser"),
                    content=event.get("content", ""),
                    cursor_path=event.get("cursor_path"),
                    highlight=event.get("highlight"),
                    resolution=self.resolution,
                    num_frames=num_frames,
                )
            case "image_file":
                raw_frames = _static_frames(
                    event.get("path", ""),
                    duration=duration,
                    fps=self.fps,
                    resolution=self.resolution,
                )
            case _:
                raw_frames = self.generators["camera"].render(
                    resolution=self.resolution, num_frames=num_frames
                )

        for raw in raw_frames:
            yield VideoFrame(
                data=raw,
                timestamp=self._now(),
                resolution=self.resolution,
            )
            await asyncio.sleep(1.0 / self.fps)


def _static_frames(
    path: str,
    duration: float,
    fps: int,
    resolution: tuple[int, int],
) -> list[bytes]:
    """Load an image file and repeat it as static video frames."""
    w, h = resolution
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        # For simplicity, use the raw bytes repeated per-frame
        return [data] * int(fps * duration)
    except FileNotFoundError:
        placeholder = np.full((h, w, 3), 128, dtype=np.uint8).tobytes()
        return [placeholder] * int(fps * duration)
