# Trading Agent Observability Guide

This guide explains how to monitor and observe your Claude Agent SDK trading agent using OpenTelemetry.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [What Gets Captured](#what-gets-captured)
4. [Configuration Options](#configuration-options)
5. [Visualization Backends](#visualization-backends)
6. [Understanding OpenTelemetry](#understanding-opentelemetry)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Usage](#advanced-usage)

---

## Overview

This trading agent now includes comprehensive observability features that allow you to:

- **See agent thinking** - View the agent's internal reasoning process
- **Track tool usage** - Monitor which tools are being called and with what parameters
- **Analyze performance** - Measure response times, token usage, and costs
- **Debug issues** - Trace errors and understand failure patterns
- **Monitor trends** - Analyze agent behavior over time

The observability system has three layers:

1. **Console Display** - Enhanced real-time console output (always active)
2. **OpenTelemetry Tracing** - Structured telemetry events (opt-in)
3. **Visualization Backend** - Web UI for analysis (optional)

---

## Quick Start

### Phase 1: Enhanced Console Output (No Configuration Needed)

The agent now displays comprehensive information in the console:

```bash
python main.py
```

You'll see:
- 💭 **THINKING** - Agent's reasoning process
- 🔧 **TOOL USE** - Tools being called with inputs
- ✅ **TOOL RESULT** - Tool execution results
- 💬 **RESPONSE** - Agent's text responses
- ⚙️  **SYSTEM** - System-level messages
- 📊 **Token Usage & Costs** - At the end of each session

### Phase 2: OpenTelemetry Traces (Console Exporter)

To enable OpenTelemetry telemetry with console output:

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` to enable telemetry:**
   ```bash
   ENABLE_TELEMETRY=true
   OTEL_EXPORTER_TYPE=console
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the agent:**
   ```bash
   python main.py
   ```

You'll now see structured OpenTelemetry spans in the console with detailed timing and event information.

### Phase 3: Web-Based Visualization (Optional)

For a professional observability dashboard, you can use SigNoz, Grafana, or other OTLP-compatible backends.

**Using SigNoz (Easiest):**

1. **Clone SigNoz repository:**
   ```bash
   cd ..
   git clone https://github.com/SigNoz/signoz.git
   cd signoz/deploy/docker/clickhouse-setup
   ```

2. **Start SigNoz:**
   ```bash
   docker-compose up -d
   ```

3. **Update your `.env`:**
   ```bash
   ENABLE_TELEMETRY=true
   OTEL_EXPORTER_TYPE=otlp-grpc
   OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
   ```

4. **Run your agent:**
   ```bash
   cd /path/to/trading_agent
   python main.py
   ```

5. **View traces:**
   - Open http://localhost:3301
   - Navigate to "Traces" section
   - Explore your agent's execution traces

---

## What Gets Captured

### Agent Turns
Each conversation turn is captured as a **span** with:
- Turn number
- Timestamp
- Duration
- All events within that turn

### Thinking Process
When the agent uses extended thinking:
- Full thinking content (truncated if > 1000 chars)
- Timestamp

### Tool Usage
For each tool invocation:
- Tool name
- Tool ID
- Input parameters
- Execution timestamp

### Tool Results
For each tool result:
- Tool ID
- Success/error status
- Result content (truncated if > 1000 chars)
- Execution timestamp

### Agent Responses
For each text response:
- Response content (truncated if > 1000 chars)
- Response length
- Timestamp

### System Messages
System-level events:
- Message subtype
- Associated data
- Timestamp

### Session Results
At the end of each session:
- Total duration (ms)
- API duration (ms)
- Number of turns
- Success/error status
- Total cost (USD)
- Token usage breakdown

---

## Configuration Options

All configuration is done via environment variables in `.env`:

### Basic Configuration

```bash
# Enable/disable telemetry
ENABLE_TELEMETRY=true

# Exporter type
OTEL_EXPORTER_TYPE=console  # Options: console, otlp-grpc, otlp-http, all
```

### OTLP Configuration (for remote backends)

```bash
# Endpoint
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Headers (for authentication)
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Bearer your_token
```

### Service Identification

```bash
# Service name (appears in telemetry data)
OTEL_SERVICE_NAME=claude-trading-agent

# Environment tag
ENVIRONMENT=development  # Options: development, staging, production
```

---

## Visualization Backends

### Option 1: SigNoz (Recommended for Beginners)

**Pros:**
- All-in-one solution
- Easy Docker setup
- Built-in dashboards
- Free and open-source

**Setup:**
```bash
# Clone and start
git clone https://github.com/SigNoz/signoz.git
cd signoz/deploy/docker/clickhouse-setup
docker-compose up -d

# Configure .env
ENABLE_TELEMETRY=true
OTEL_EXPORTER_TYPE=otlp-grpc
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

**Access:** http://localhost:3301

### Option 2: Grafana Cloud

**Pros:**
- Managed service (no infrastructure)
- Generous free tier
- Professional-grade features

**Setup:**
1. Sign up at https://grafana.com/
2. Create a new stack
3. Get your OTLP endpoint and credentials
4. Configure `.env`:
   ```bash
   ENABLE_TELEMETRY=true
   OTEL_EXPORTER_TYPE=otlp-http
   OTEL_EXPORTER_OTLP_ENDPOINT=https://your-instance.grafana.net:443/otlp
   OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic your_base64_credentials
   ```

### Option 3: Honeycomb

**Pros:**
- Excellent query interface
- Great for debugging
- 20GB/month free tier

**Setup:**
1. Sign up at https://honeycomb.io/
2. Get your API key
3. Configure `.env`:
   ```bash
   ENABLE_TELEMETRY=true
   OTEL_EXPORTER_TYPE=otlp-grpc
   OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io:443
   OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=your_api_key
   ```

### Option 4: Console Only (Local Debugging)

**Pros:**
- No setup required
- See traces immediately
- Good for development

**Setup:**
```bash
ENABLE_TELEMETRY=true
OTEL_EXPORTER_TYPE=console
```

---

## Understanding OpenTelemetry

### What is OpenTelemetry?

OpenTelemetry is a vendor-neutral standard for observability. It provides:

- **Traces** - Detailed execution flows showing what happened and when
- **Spans** - Individual units of work (e.g., one agent turn)
- **Events** - Point-in-time occurrences (e.g., tool use, thinking)
- **Attributes** - Metadata attached to spans and events

### Key Concepts

#### Traces
A trace represents a complete operation (e.g., one agent conversation turn).

```
Trace: Agent Turn 1
├─ Span: agent.turn.1 (5000ms)
   ├─ Event: agent.thinking (t=0ms)
   ├─ Event: tool.use (t=100ms)
   ├─ Event: tool.result (t=2000ms)
   ├─ Event: agent.response (t=2100ms)
   └─ Event: session.result (t=5000ms)
```

#### Spans
Spans are the building blocks of traces. Each span has:
- Name (e.g., `agent.turn.1`)
- Start and end timestamps
- Duration
- Status (OK, ERROR)
- Events and attributes

#### Events
Events are timestamped log records attached to spans:
```json
{
  "name": "tool.use",
  "timestamp": "2025-10-15T14:30:00.123Z",
  "attributes": {
    "tool.name": "binance_get_account",
    "tool.id": "toolu_abc123",
    "tool.input": "{...}"
  }
}
```

#### Attributes
Key-value pairs providing context:
- `tool.name`: Name of the tool used
- `session.cost_usd`: Cost in USD
- `session.num_turns`: Number of conversation turns

---

## Troubleshooting

### Telemetry Not Appearing

**Check 1: Is telemetry enabled?**
```bash
# In .env
ENABLE_TELEMETRY=true
```

**Check 2: Are dependencies installed?**
```bash
pip install -r requirements.txt
```

**Check 3: Is the exporter configured correctly?**
```bash
# For console output
OTEL_EXPORTER_TYPE=console

# For OTLP (check endpoint is reachable)
OTEL_EXPORTER_TYPE=otlp-grpc
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

**Check 4: Are there Python errors?**
Look for errors in the console output when the agent starts.

### SigNoz Not Receiving Traces

**Check 1: Is SigNoz running?**
```bash
docker-compose ps
```

**Check 2: Is the collector accessible?**
```bash
curl http://localhost:4317
# or
telnet localhost 4317
```

**Check 3: Check SigNoz logs:**
```bash
docker-compose logs otel-collector
```

**Check 4: Verify endpoint in .env:**
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
# NOT https, NOT :4318 for gRPC
```

### Traces Are Incomplete

**Issue:** Some events are missing from traces.

**Solution:** Traces are exported in batches. Make sure:
1. The agent completes its execution
2. Telemetry is properly shutdown (it is, automatically)
3. Check console for errors during telemetry export

### High Memory Usage

**Issue:** Telemetry is consuming too much memory.

**Solution:** Telemetry intentionally truncates large outputs:
- Thinking content: 1000 chars
- Tool results: 1000 chars
- Response text: 1000 chars

If memory is still an issue, you can:
1. Reduce truncation limits in `telemetry.py`
2. Use sampling (export only % of traces)

---

## Advanced Usage

### Custom Attributes

You can add custom attributes to spans by modifying `telemetry.py`:

```python
def trace_custom_event(self, event_name: str, attributes: Dict[str, Any]):
    """Add a custom event to the current span."""
    if not self.enabled or not self.tracer:
        return

    current_span = trace.get_current_span()
    if current_span:
        current_span.add_event(event_name, attributes=attributes)
```

Then in `main.py`:
```python
telemetry.trace_custom_event("trading.signal", {
    "symbol": "BTC/USDT",
    "action": "BUY",
    "confidence": 0.85
})
```

### Filtering Traces

To export only specific traces, you can use sampling:

```python
# In telemetry.py, update TracerProvider initialization:
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

self.tracer_provider = TracerProvider(
    resource=resource,
    sampler=TraceIdRatioBased(0.5)  # Sample 50% of traces
)
```

### Multiple Exporters

To send traces to multiple backends simultaneously:

```bash
OTEL_EXPORTER_TYPE=all
```

This sends traces to both console and OTLP.

### Custom Exporter

You can add custom exporters in `telemetry.py`:

```python
from opentelemetry.sdk.trace.export import SpanExporter

class FileSpanExporter(SpanExporter):
    def __init__(self, file_path: str):
        self.file_path = file_path

    def export(self, spans):
        with open(self.file_path, 'a') as f:
            for span in spans:
                f.write(f"{span.to_json()}\n")
        return SpanExportResult.SUCCESS
```

---

## Learning Resources

### OpenTelemetry
- Official Docs: https://opentelemetry.io/docs/
- Python Docs: https://opentelemetry.io/docs/languages/python/
- Instrumentation: https://opentelemetry.io/docs/languages/python/instrumentation/

### Claude Agent SDK
- Overview: https://docs.claude.com/en/api/agent-sdk/overview
- Python Reference: https://docs.claude.com/en/api/agent-sdk/python
- Monitoring: https://docs.claude.com/en/docs/claude-code/monitoring-usage

### Observability Platforms
- SigNoz: https://signoz.io/docs/
- Grafana: https://grafana.com/docs/
- Honeycomb: https://docs.honeycomb.io/

---

## Example Queries

Once you have traces in a backend like SigNoz, you can run queries like:

### Find Expensive Operations
```
duration > 5000ms
```

### Find Failed Tools
```
tool.error = true
```

### Track Costs Over Time
```
session.cost_usd > 0
GROUP BY time
```

### Analyze Token Usage
```
session.usage.total_tokens
GROUP BY agent.turn.number
```

---

## Next Steps

1. **Start Simple** - Enable console telemetry and observe the output
2. **Understand the Data** - Look at what events are being captured
3. **Add a Backend** - Set up SigNoz or another visualization tool
4. **Explore Traces** - Click around and understand the trace structure
5. **Create Dashboards** - Build custom views for your trading metrics
6. **Set Up Alerts** - Get notified when errors occur or costs spike

---

## Support

For issues with:
- **This observability implementation**: Check logs, review configuration
- **OpenTelemetry**: Visit https://opentelemetry.io/docs/
- **Claude Agent SDK**: Visit https://docs.claude.com/
- **SigNoz**: Visit https://signoz.io/docs/

Happy observing! 🔍
