"""Tests for the tools layer."""

from __future__ import annotations

import pytest

from voice_test_framework.tools.registry import MockToolRegistry
from voice_test_framework.tools.asserter import ToolCallAsserter
from voice_test_framework.tools.builtin_mocks import (
    register_hotel_booking_mocks,
    register_general_mocks,
)


class TestMockToolRegistry:

    def test_register_and_list(self, tool_registry: MockToolRegistry):
        assert "check_availability" in tool_registry.tools
        assert "create_booking" in tool_registry.tools
        assert "get_weather" in tool_registry.tools

    async def test_handle_call_success(self, tool_registry: MockToolRegistry):
        result = await tool_registry.handle_call("get_weather", {"location": "Tokyo"})
        assert result.success
        assert result.data["location"] == "Tokyo"
        assert result.latency_ms > 0

    async def test_handle_unknown_tool(self, tool_registry: MockToolRegistry):
        result = await tool_registry.handle_call("nonexistent", {})
        assert not result.success
        assert "Unknown tool" in result.error

    async def test_call_log(self, tool_registry: MockToolRegistry):
        await tool_registry.handle_call("get_weather", {"location": "NYC"})
        assert len(tool_registry.call_log) == 1
        assert tool_registry.call_log[0]["tool"] == "get_weather"

    def test_reset(self, tool_registry: MockToolRegistry):
        tool_registry.call_log.append({"tool": "test", "args": {}, "timestamp": 0})
        tool_registry.reset()
        assert len(tool_registry.call_log) == 0


class TestToolCallAsserter:

    async def test_assert_called(self, tool_registry: MockToolRegistry):
        asserter = ToolCallAsserter(tool_registry)
        await tool_registry.handle_call("get_weather", {"location": "LA"})
        asserter.assert_called("get_weather")

    async def test_assert_not_called(self, tool_registry: MockToolRegistry):
        asserter = ToolCallAsserter(tool_registry)
        asserter.assert_not_called("create_booking")

    async def test_assert_called_fails(self, tool_registry: MockToolRegistry):
        asserter = ToolCallAsserter(tool_registry)
        with pytest.raises(AssertionError):
            asserter.assert_called("nonexistent")

    async def test_assert_call_order(self, tool_registry: MockToolRegistry):
        asserter = ToolCallAsserter(tool_registry)
        await tool_registry.handle_call("check_availability", {})
        await tool_registry.handle_call("create_booking", {})
        asserter.assert_call_order("check_availability", "create_booking")

    async def test_assert_called_times(self, tool_registry: MockToolRegistry):
        asserter = ToolCallAsserter(tool_registry)
        await tool_registry.handle_call("get_weather", {})
        await tool_registry.handle_call("get_weather", {})
        asserter.assert_called_times("get_weather", 2)
