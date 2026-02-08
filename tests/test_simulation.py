"""Tests for simulation layer components."""

from __future__ import annotations

import pytest

from voice_test_framework.core.clock import SimulatedClock
from voice_test_framework.core.interfaces import AudioChunk
from voice_test_framework.simulation.audio import AudioStreamSimulator, AudioConfig, TTSEngine
from voice_test_framework.simulation.noise import NoiseEngine, AmbientProfile, TransientNoise
from voice_test_framework.simulation.network import NetworkSimulator
from voice_test_framework.simulation.video import VideoStreamSimulator, VideoConfig
from voice_test_framework.simulation.physical_world import PhysicalWorldSimulator


class TestAudioStreamSimulator:

    async def test_generate_from_tts(self):
        sim = AudioStreamSimulator(AudioConfig(tts_provider="builtin"))
        chunks = []
        async for chunk in sim.generate(text="tts://Hello world"):
            chunks.append(chunk)
        assert len(chunks) > 0
        assert all(isinstance(c, AudioChunk) for c in chunks)

    async def test_generate_plain_text(self):
        sim = AudioStreamSimulator(AudioConfig(tts_provider="builtin"))
        chunks = []
        async for chunk in sim.generate(text="Hello world"):
            chunks.append(chunk)
        assert len(chunks) > 0

    async def test_empty_input(self):
        sim = AudioStreamSimulator()
        chunks = []
        async for chunk in sim.generate():
            chunks.append(chunk)
        assert len(chunks) == 0

    async def test_speech_style_speed(self):
        sim = AudioStreamSimulator()
        slow_chunks = []
        async for c in sim.generate(text="Test", style={"speed": 0.5}):
            slow_chunks.append(c)
        fast_chunks = []
        async for c in sim.generate(text="Test", style={"speed": 2.0}):
            fast_chunks.append(c)
        # Slower speech = more chunks
        assert len(slow_chunks) >= len(fast_chunks)


class TestTTSEngine:

    async def test_builtin_synthesis(self):
        engine = TTSEngine("builtin")
        audio = await engine.synthesize("Hello", sample_rate=16000)
        assert isinstance(audio, bytes)
        assert len(audio) > 0


class TestNoiseEngine:

    def test_default_profile(self):
        engine = NoiseEngine(profile="quiet_room")
        assert engine.ambient.snr_db == 40

    def test_set_profile(self):
        engine = NoiseEngine()
        engine.set_profile("cafe")
        assert engine.ambient.name == "cafe"
        assert engine.ambient.snr_db == 15

    def test_set_snr(self):
        engine = NoiseEngine()
        engine.set_snr(10)
        assert engine.ambient.snr_db == 10

    def test_mix_with_speech(self):
        engine = NoiseEngine(profile="office")
        speech = AudioChunk(data=b"\x00\x00" * 320, timestamp=0, sample_rate=16000)
        mixed = engine.mix_with_speech(speech)
        assert isinstance(mixed, AudioChunk)
        assert len(mixed.data) == len(speech.data)

    async def test_inject_transient(self):
        engine = NoiseEngine()
        await engine.inject("transient", "phone_ring")
        assert len(engine.active_transients) == 1
        assert engine.active_transients[0].is_active()


class TestNetworkSimulator:

    def test_default_perfect(self):
        net = NetworkSimulator(profile="perfect")
        assert net.base_latency == 10
        assert net.loss_rate == 0.0

    def test_set_profile(self):
        net = NetworkSimulator()
        net.set_profile("bad_wifi")
        assert net.base_latency == 200
        assert net.loss_rate == 0.10

    async def test_apply_passes_chunk(self):
        net = NetworkSimulator(profile="perfect")
        chunk = AudioChunk(data=b"\x01\x02", timestamp=0)
        result = await net.apply(chunk)
        assert result is not None
        assert result.data == chunk.data


class TestVideoStreamSimulator:

    async def test_generate_camera(self):
        sim = VideoStreamSimulator(VideoConfig(fps=5))
        frames = []
        async for f in sim.generate({"source": "camera", "duration": 0.2}):
            frames.append(f)
        assert len(frames) >= 1

    async def test_generate_screen(self):
        sim = VideoStreamSimulator(VideoConfig(fps=5))
        frames = []
        async for f in sim.generate({
            "source": "screen",
            "app": "terminal",
            "content": "hello",
            "duration": 0.2,
        }):
            frames.append(f)
        assert len(frames) >= 1


class TestPhysicalWorldSimulator:

    async def test_simulate_device_events(self):
        sim = PhysicalWorldSimulator()
        log = await sim.simulate_scenario("device_events")
        assert len(log) > 0

    async def test_unknown_scenario(self):
        sim = PhysicalWorldSimulator()
        log = await sim.simulate_scenario("nonexistent")
        assert log == []
