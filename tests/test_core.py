"""Tests for core framework components."""

from __future__ import annotations

import asyncio

import pytest

from voice_test_framework.core.clock import SimulatedClock
from voice_test_framework.core.results import TestResults, AssertionResult, ToolCallResults
from voice_test_framework.core.interfaces import AudioChunk, VideoFrame, ToolResult


class TestSimulatedClock:

    async def test_advance_to(self):
        clock = SimulatedClock()
        assert clock.now() == 0.0
        await clock.advance_to(5.0)
        assert clock.now() == 5.0

    async def test_advance_by(self):
        clock = SimulatedClock()
        await clock.advance_by(3.0)
        assert clock.now() == 3.0
        await clock.advance_by(2.0)
        assert clock.now() == 5.0

    async def test_no_backward(self):
        clock = SimulatedClock()
        await clock.advance_to(5.0)
        await clock.advance_to(3.0)  # should be no-op
        assert clock.now() == 5.0

    def test_reset(self):
        clock = SimulatedClock()
        clock._current = 10.0
        clock.reset()
        assert clock.now() == 0.0


class TestTestResults:

    def test_all_passed(self):
        r = TestResults()
        r.add(0, AssertionResult(timestamp=0, passed=True, description="a"))
        r.add(1, AssertionResult(timestamp=1, passed=True, description="b"))
        assert r.all_passed()

    def test_not_all_passed(self):
        r = TestResults()
        r.add(0, AssertionResult(timestamp=0, passed=True))
        r.add(1, AssertionResult(timestamp=1, passed=False))
        assert not r.all_passed()

    def test_add_dict(self):
        r = TestResults()
        r.add(0, {"passed": True, "description": "from dict"})
        assert len(r.assertions) == 1
        assert r.assertions[0].passed

    def test_record_response(self):
        r = TestResults()
        r.record_response(text="hello", timestamp=1.0)
        assert r.last_response.text == "hello"

    def test_tag(self):
        r = TestResults()
        r.tag("snr_15")
        assert "snr_15" in r.tags


class TestToolCallResults:

    def test_assert_called(self):
        tcr = ToolCallResults()
        from voice_test_framework.core.results import ToolCallRecord
        tcr.calls.append(ToolCallRecord(tool="foo", args={}, timestamp=0))
        assert tcr.assert_called("foo")
        assert not tcr.assert_called("bar")

    def test_assert_call_order(self):
        tcr = ToolCallResults()
        from voice_test_framework.core.results import ToolCallRecord
        tcr.calls.append(ToolCallRecord(tool="a", args={}, timestamp=0))
        tcr.calls.append(ToolCallRecord(tool="b", args={}, timestamp=1))
        tcr.calls.append(ToolCallRecord(tool="c", args={}, timestamp=2))
        assert tcr.assert_call_order("a", "b", "c")
        assert tcr.assert_call_order("a", "c")
        assert not tcr.assert_call_order("c", "a")


class TestDataTypes:

    def test_audio_chunk(self):
        chunk = AudioChunk(data=b"\x00\x01", timestamp=0.5)
        assert chunk.sample_rate == 16000

    def test_video_frame(self):
        frame = VideoFrame(data=b"\xff", timestamp=1.0)
        assert frame.resolution == (1280, 720)

    def test_tool_result(self):
        tr = ToolResult(success=True, data={"key": "value"})
        assert tr.success
        assert tr.data["key"] == "value"
