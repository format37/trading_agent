# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered cryptocurrency trading system using Claude SDK and Model Context Protocol (MCP). Manages a real Binance account competing against a 33% BTC / 33% ETH / 33% USDT passive benchmark.

**Key Innovation**: CSV-First MCP Architecture - All MCP servers return CSV file paths instead of text summaries, forcing systematic quantitative analysis via pandas/numpy.

## Build & Run Commands

```bash
# Production deployment (Docker)
./compose_prod.sh

# Development - direct execution
python trading_agent.py

# Development - with test prompts
USE_TEST_PROMPTS=true python trading_agent.py

# Interactive mode
python trading_agent.py --interactive

# Event-driven mode
python trading_agent.py --event-file events/alert.json

# API server
python api.py

# Health check
curl http://localhost:8012/health

# Trigger analysis via API
curl -X POST http://localhost:8012/action \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_prompt": "Analyze market conditions"}'

# View logs
./logs.sh
```

## Architecture

### Core Files
- `trading_agent.py` - Main orchestration using Claude SDK with ClaudeSDKClient
- `api.py` - FastAPI REST server with token-based auth, exposes /health and /action endpoints
- `prompts/` - 14 prompt files (system, user, test variants, and 10 subagent prompts)

### Subagent System
Ten specialized subagents run in a phased workflow with restricted tool access:

| Agent | Phase | Purpose | Trading? |
|-------|-------|---------|----------|
| news-analyst | 0 (FIRST) | News preprocessing to CSV | No |
| market-intelligence | 1 | Sentiment & FOMO/FUD (Perplexity) | No |
| btc-researcher | 2 | Bitcoin analysis | No |
| eth-researcher | 2 | Ethereum ecosystem | No |
| altcoin-researcher | 2 | Alternative opportunities | No |
| technical-analyst | 2 | Chart analysis | No |
| risk-manager | 2 | Portfolio risk (account tools only) | No |
| data-analyst | 2 | Statistical analysis (Python + Read only) | No |
| futures-analyst | 2 | Leverage strategies | No |
| critic | 3 (LAST) | Devil's advocate review | No |

Subagents are defined in `create_subagent_definitions()` (~line 295) with `AgentDefinition` objects specifying allowed tools.

### MCP Servers
Three external MCP servers required (configured via environment variables):
- **Polygon** (`POLYGON_URL`) - Market data, technical indicators, news
- **Binance** (`BINANCE_URL`) - Trading, account management, P&L
- **Perplexity** (`PERPLEXITY_URL`) - Web research

All tools return CSV file paths stored in `data/mcp-{server}/`. Agent must use `mcp__ide__executeCode` or `mcp__binance__binance_py_eval` to analyze CSVs with pandas.

### Data Flow
```
n8n Event -> REST API -> Trading Agent -> MCP Server -> CSV File -> Python Analysis -> Trading Decision
```

## Configuration

Key environment variables (`.env.prod`):
```bash
POLYGON_URL=http://mcp-polygon:8006/polygon/
BINANCE_URL=http://mcp-binance-local:8010/binance/
PERPLEXITY_URL=http://mcp-perplexity-local:8011/perplexity/
STRICT_MCP_CHECK=true          # Fail-fast if MCP servers unreachable
AGENT_TIMEOUT_SECONDS=600      # 10 minute timeout
AGENT_REQUIRE_AUTH=true        # Enable token auth
AGENT_TOKENS=token1,token2     # Comma-separated allowed tokens
USE_TEST_PROMPTS=false         # Use test prompts instead of production
```

## Code Conventions

### Claude SDK Usage
```python
from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, AgentDefinition,
    AssistantMessage, TextBlock, ThinkingBlock, ToolUseBlock, ToolResultBlock
)

options = ClaudeAgentOptions(
    system_prompt=system_prompt,
    agents=subagents,           # Dict of AgentDefinition objects
    allowed_tools=[...],
    permission_mode="bypassPermissions",
    mcp_servers={...}
)

async with ClaudeSDKClient(options=options) as client:
    await client.query(user_prompt)
    async for message in client.receive_response():
        # Handle AssistantMessage, SystemMessage, ResultMessage
```

### Timestamp Handling
Always use UTC timestamps:
```python
from datetime import datetime, timezone
current_time = datetime.now(timezone.utc)
```

### Telemetry
Telemetry is disabled by default (`ENABLE_TELEMETRY=False`). No-op implementations are used when disabled.

## Docker

- Base: Python 3.11-slim + Node.js 22 (for claude-code CLI)
- Network: `mcp-shared` (shared with MCP servers)
- Port: 8012
- Data volumes: `/data` mounted for CSV persistence
