"""
OpenTelemetry Telemetry Module for Claude Agent SDK Trading Agent

This module provides comprehensive observability for the trading agent using OpenTelemetry.
It captures traces, spans, events, and metrics for all agent interactions, tool usage, and responses.
"""

import os
import logging
from typing import Optional, Any, Dict
from datetime import datetime, timezone
from contextlib import contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor
)
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPSpanExporterGRPC
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPSpanExporterHTTP
from opentelemetry.trace import Status, StatusCode

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TelemetryManager:
    """Manages OpenTelemetry configuration and instrumentation for the trading agent."""

    def __init__(self, service_name: str = "claude-trading-agent"):
        """
        Initialize the telemetry manager.

        Args:
            service_name: Name of the service for telemetry identification
        """
        self.service_name = service_name
        self.tracer_provider: Optional[TracerProvider] = None
        self.tracer: Optional[trace.Tracer] = None
        self.enabled = self._is_telemetry_enabled()

        if self.enabled:
            self._setup_telemetry()

    def _is_telemetry_enabled(self) -> bool:
        """Check if telemetry is enabled via environment variable."""
        return os.getenv("ENABLE_TELEMETRY", "false").lower() in ["true", "1", "yes"]

    def _setup_telemetry(self):
        """Setup OpenTelemetry with configured exporters."""
        logger.info("🔍 Initializing OpenTelemetry telemetry...")

        # Create resource with service name
        resource = Resource(attributes={
            SERVICE_NAME: self.service_name,
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development")
        })

        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource)

        # Setup exporters based on configuration
        self._setup_exporters()

        # Set as global tracer provider
        trace.set_tracer_provider(self.tracer_provider)

        # Get tracer
        self.tracer = trace.get_tracer(__name__)

        logger.info("✅ OpenTelemetry telemetry initialized successfully")

    def _setup_exporters(self):
        """Setup trace exporters based on environment configuration."""
        exporter_type = os.getenv("OTEL_EXPORTER_TYPE", "console").lower()

        if exporter_type == "console":
            self._setup_console_exporter()
        elif exporter_type == "otlp-grpc":
            self._setup_otlp_grpc_exporter()
        elif exporter_type == "otlp-http":
            self._setup_otlp_http_exporter()
        elif exporter_type == "all":
            # Use multiple exporters
            self._setup_console_exporter()
            self._setup_otlp_grpc_exporter()
        else:
            logger.warning(f"Unknown exporter type: {exporter_type}, falling back to console")
            self._setup_console_exporter()

    def _setup_console_exporter(self):
        """Setup console exporter for local debugging."""
        logger.info("Setting up Console exporter...")
        exporter = ConsoleSpanExporter()
        processor = SimpleSpanProcessor(exporter)
        self.tracer_provider.add_span_processor(processor)

    def _setup_otlp_grpc_exporter(self):
        """Setup OTLP gRPC exporter for remote backends."""
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")

        logger.info(f"Setting up OTLP gRPC exporter (endpoint: {endpoint})...")

        headers_dict = {}
        if headers:
            for header in headers.split(","):
                if "=" in header:
                    key, value = header.split("=", 1)
                    headers_dict[key.strip()] = value.strip()

        exporter = OTLPSpanExporterGRPC(
            endpoint=endpoint,
            headers=headers_dict if headers_dict else None
        )
        processor = BatchSpanProcessor(exporter)
        self.tracer_provider.add_span_processor(processor)

    def _setup_otlp_http_exporter(self):
        """Setup OTLP HTTP exporter for remote backends."""
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces")
        headers = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")

        logger.info(f"Setting up OTLP HTTP exporter (endpoint: {endpoint})...")

        headers_dict = {}
        if headers:
            for header in headers.split(","):
                if "=" in header:
                    key, value = header.split("=", 1)
                    headers_dict[key.strip()] = value.strip()

        exporter = OTLPSpanExporterHTTP(
            endpoint=endpoint,
            headers=headers_dict if headers_dict else None
        )
        processor = BatchSpanProcessor(exporter)
        self.tracer_provider.add_span_processor(processor)

    @contextmanager
    def trace_agent_turn(self, turn_number: int):
        """
        Create a span for a complete agent turn.

        Args:
            turn_number: The turn number in the conversation
        """
        if not self.enabled or not self.tracer:
            yield None
            return

        with self.tracer.start_as_current_span(
            f"agent.turn.{turn_number}",
            attributes={
                "agent.turn.number": turn_number,
                "agent.timestamp": datetime.now(timezone.utc).isoformat()
            }
        ) as span:
            yield span

    def trace_tool_use(self, tool_name: str, tool_id: str, tool_input: Dict[str, Any]):
        """
        Record a tool use event.

        Args:
            tool_name: Name of the tool being used
            tool_id: Unique identifier for this tool invocation
            tool_input: Input parameters for the tool
        """
        if not self.enabled or not self.tracer:
            return

        current_span = trace.get_current_span()
        if current_span:
            current_span.add_event(
                "tool.use",
                attributes={
                    "tool.name": tool_name,
                    "tool.id": tool_id,
                    "tool.input": str(tool_input),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )

    def trace_tool_result(self, tool_id: str, is_error: bool, result_summary: str):
        """
        Record a tool result event.

        Args:
            tool_id: Unique identifier for the tool invocation
            is_error: Whether the tool execution resulted in an error
            result_summary: Summary of the result (truncated if too long)
        """
        if not self.enabled or not self.tracer:
            return

        current_span = trace.get_current_span()
        if current_span:
            # Truncate result if too long
            if len(result_summary) > 1000:
                result_summary = result_summary[:1000] + "... (truncated)"

            current_span.add_event(
                "tool.result",
                attributes={
                    "tool.id": tool_id,
                    "tool.error": is_error,
                    "tool.result.summary": result_summary,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )

            if is_error:
                current_span.set_status(Status(StatusCode.ERROR, "Tool execution failed"))

    def trace_thinking(self, thinking_content: str):
        """
        Record agent thinking process.

        Args:
            thinking_content: The agent's thinking content
        """
        if not self.enabled or not self.tracer:
            return

        current_span = trace.get_current_span()
        if current_span:
            # Truncate if too long
            if len(thinking_content) > 1000:
                thinking_content = thinking_content[:1000] + "... (truncated)"

            current_span.add_event(
                "agent.thinking",
                attributes={
                    "thinking.content": thinking_content,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )

    def trace_response(self, response_text: str):
        """
        Record agent text response.

        Args:
            response_text: The agent's response text
        """
        if not self.enabled or not self.tracer:
            return

        current_span = trace.get_current_span()
        if current_span:
            # Truncate if too long
            if len(response_text) > 1000:
                response_text = response_text[:1000] + "... (truncated)"

            current_span.add_event(
                "agent.response",
                attributes={
                    "response.text": response_text,
                    "response.length": len(response_text),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )

    def trace_session_result(self, result_data: Dict[str, Any]):
        """
        Record session result with usage statistics.

        Args:
            result_data: Dictionary containing session result information
        """
        if not self.enabled or not self.tracer:
            return

        current_span = trace.get_current_span()
        if current_span:
            # Extract key metrics
            attributes = {
                "session.duration_ms": result_data.get("duration_ms", 0),
                "session.duration_api_ms": result_data.get("duration_api_ms", 0),
                "session.num_turns": result_data.get("num_turns", 0),
                "session.is_error": result_data.get("is_error", False),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            # Add cost if available
            if result_data.get("total_cost_usd"):
                attributes["session.cost_usd"] = result_data["total_cost_usd"]

            # Add usage stats if available
            if result_data.get("usage"):
                usage = result_data["usage"]
                if isinstance(usage, dict):
                    for key, value in usage.items():
                        # OpenTelemetry attributes only support simple types
                        # Convert dict/list values to JSON strings
                        if isinstance(value, (dict, list)):
                            import json
                            attributes[f"session.usage.{key}"] = json.dumps(value)
                        else:
                            attributes[f"session.usage.{key}"] = value

            current_span.add_event("session.result", attributes=attributes)

            # Set span status
            if result_data.get("is_error", False):
                current_span.set_status(Status(StatusCode.ERROR, "Session ended with error"))
            else:
                current_span.set_status(Status(StatusCode.OK))

    def trace_system_message(self, subtype: str, data: Dict[str, Any]):
        """
        Record system message.

        Args:
            subtype: System message subtype
            data: System message data
        """
        if not self.enabled or not self.tracer:
            return

        current_span = trace.get_current_span()
        if current_span:
            current_span.add_event(
                "system.message",
                attributes={
                    "system.subtype": subtype,
                    "system.data": str(data),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )

    def shutdown(self):
        """Shutdown telemetry and flush all pending spans."""
        if self.enabled and self.tracer_provider:
            logger.info("Shutting down telemetry...")
            self.tracer_provider.shutdown()
            logger.info("Telemetry shutdown complete")


# Global telemetry manager instance
_telemetry_manager: Optional[TelemetryManager] = None


def get_telemetry_manager(service_name: str = "claude-trading-agent") -> TelemetryManager:
    """
    Get or create the global telemetry manager instance.

    Args:
        service_name: Name of the service for telemetry

    Returns:
        TelemetryManager instance
    """
    global _telemetry_manager
    if _telemetry_manager is None:
        _telemetry_manager = TelemetryManager(service_name=service_name)
    return _telemetry_manager
