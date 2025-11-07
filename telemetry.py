"""
No-op Telemetry Module

Telemetry has been disabled. This module provides no-op implementations
to maintain compatibility with existing code.
"""

from contextlib import contextmanager


class TelemetryManager:
    """No-op telemetry manager."""

    def __init__(self, *args, **kwargs):
        self.enabled = False

    @contextmanager
    def trace_agent_turn(self, turn_number):
        """No-op context manager for tracing agent turns."""
        yield None

    def trace_thinking(self, thinking_content):
        """No-op method."""
        pass

    def trace_tool_use(self, tool_name, tool_id, tool_input):
        """No-op method."""
        pass

    def trace_tool_result(self, tool_id, is_error, result_summary):
        """No-op method."""
        pass

    def trace_response(self, response_text):
        """No-op method."""
        pass

    def trace_session_result(self, result_data):
        """No-op method."""
        pass

    def trace_system_message(self, subtype, data):
        """No-op method."""
        pass

    def shutdown(self):
        """No-op shutdown method."""
        pass


def get_telemetry_manager(*args, **kwargs):
    """Return a no-op telemetry manager."""
    return TelemetryManager()
