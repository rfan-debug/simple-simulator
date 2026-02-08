"""Tool call assertion helpers for verifying SUT behaviour."""

from __future__ import annotations

from typing import Any

from .registry import MockToolRegistry


class ToolCallAsserter:
    """
    Convenience wrapper around a ``MockToolRegistry`` for writing
    expressive assertions in tests.
    """

    def __init__(self, registry: MockToolRegistry) -> None:
        self.registry = registry

    @property
    def call_log(self) -> list[dict[str, Any]]:
        return self.registry.call_log

    def assert_called(
        self,
        tool_name: str,
        args_contain: dict[str, Any] | None = None,
        within_ms: int = 5000,
    ) -> None:
        """Assert that *tool_name* was called (optionally with matching args)."""
        calls = [c for c in self.call_log if c["tool"] == tool_name]
        if not calls:
            raise AssertionError(
                f"Expected '{tool_name}' to be called, "
                f"but it wasn't.  Call log: {self.call_log}"
            )
        if args_contain:
            last_call = calls[-1]
            for key, value in args_contain.items():
                if key not in last_call["args"]:
                    raise AssertionError(
                        f"Missing arg '{key}' in {tool_name} call.  "
                        f"Got: {last_call['args']}"
                    )
                if last_call["args"][key] != value:
                    raise AssertionError(
                        f"Arg '{key}' mismatch: expected {value!r}, "
                        f"got {last_call['args'][key]!r}"
                    )

    def assert_not_called(self, tool_name: str) -> None:
        """Assert that *tool_name* was **not** called."""
        calls = [c for c in self.call_log if c["tool"] == tool_name]
        if calls:
            raise AssertionError(
                f"Expected '{tool_name}' NOT to be called, "
                f"but it was called {len(calls)} time(s)"
            )

    def assert_call_order(self, *tool_names: str) -> None:
        """Assert that tools were called in the specified order."""
        actual_order = [c["tool"] for c in self.call_log]
        idx = 0
        for expected in tool_names:
            found = False
            while idx < len(actual_order):
                if actual_order[idx] == expected:
                    found = True
                    idx += 1
                    break
                idx += 1
            if not found:
                raise AssertionError(
                    f"Expected call order {tool_names}, "
                    f"but actual order was {actual_order}"
                )

    def assert_retry_on_failure(
        self, tool_name: str, max_retries: int = 3
    ) -> None:
        """Assert the SUT retried *tool_name* after failures."""
        calls = [c for c in self.call_log if c["tool"] == tool_name]
        if len(calls) < 2:
            raise AssertionError(
                f"Expected '{tool_name}' to be retried, "
                f"but it was only called {len(calls)} time(s)"
            )
        if len(calls) > max_retries + 1:
            raise AssertionError(
                f"'{tool_name}' was called {len(calls)} times, "
                f"exceeding max retries ({max_retries})"
            )

    def assert_called_times(self, tool_name: str, times: int) -> None:
        """Assert *tool_name* was called exactly *times* times."""
        calls = [c for c in self.call_log if c["tool"] == tool_name]
        if len(calls) != times:
            raise AssertionError(
                f"Expected '{tool_name}' to be called {times} time(s), "
                f"but it was called {len(calls)} time(s)"
            )


class AssertionError(AssertionError):
    """Custom assertion error with nicer formatting."""
    pass
