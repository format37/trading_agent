# Claude SDK Trading Agent

### Overview
AI-powered cryptocurrency trading agent built with Claude SDK and the Model Context Protocol (MCP), featuring systematic CSV-based data analysis and conservative risk management for live market trading.

<p align="center">
  <img src="assets/trading_agent.png" alt="Trading Agent Architecture">
</p>

### Deep Analysis of Each MCP Tool Response
All tools save results to CSV files in the shared `data/` folder (mounted across MCP servers and agent).

The agent does not receive text from requested MCP tools. It has only a single option - read CSV files and execute pandas/numpy code to analyze patterns, calculate metrics, and identify signals.

### Subagents
The primary benefits of using sub-agents are token economy and strict focus on the corresponding task.

### Activation by n8n Events
This agent is deployed as a REST API. The following parameters are accepted:
* System prompt
* User prompts
* Event notes

Agent activation is initialized by an n8n process, which includes:
* Cron: 8, 14, 20 UTC
* Binance news notifications
* cryptocurrencyalerting.com alerts

<p align="center">
  <img src="assets/n8n.png" alt="n8n Workflow">
</p>

### Trading Notes & UI
Before each trading session, the agent reads the trading notes using the Binance MCP tool.

After each session, the agent updates trading notes using the Binance MCP tool.

All tools that the agent has are available as MCP in Claude web & Claude mobile. Users can always ask Claude about trading notes or request to close or open positions. Everything the trading agent has is available for Claude web & mobile.

### Performance
<p align="center">
  <img src="assets/performance.png" alt="Performance metrics">
</p>

According to the first month test on a real portfolio, it underperformed the 33% BTC - 33% ETH - 33% USDT weighted portfolio by 0.86%.
```
Total Capital Invested: $2,910.75

ACTUAL TRADING:
  Final Equity:  $2,828.12
  Return:        -2.84%
  Profit/Loss:   $-82.62
  Max Drawdown:  -7.53%

BUY-AND-HOLD (33% BTC, 33% ETH, 33% USDT):
  Final Equity:  $2,853.08
  Return:        -1.98%
  Profit/Loss:   $-57.67
  Max Drawdown:  -8.47%

OUTPERFORMANCE: -0.86%
```

## Installation
### Requirements
* mcp-binance
* mcp-polygon
* mcp-perplexity
### Installation
```
git clone https://github.com/format37/trading_agent.git
cd trading_agent
sudo mkdir -p /home/ubuntu/mcp/data
sudo mkdir -p /home/ubuntu/mcp/data/trading_agent/logs
sudo chown -R $USER:$USER /home/ubuntu/mcp/data
./compose_prod.sh
```
### Health check
http://trading-agent:8012/health

## Claude Authentication

After deploying the container, you can authenticate Claude CLI to use your Claude subscription instead of API keys.

### Authentication Workflow

1. **Connect to the running container**:
```bash
docker exec -it trading-agent bash
```

2. **Authenticate Claude CLI**:
```bash
claude
```
If you restart the container, you would need to repeat this step.

### Troubleshooting

**Error: `EACCES: permission denied, mkdir '/home/appuser/.claude/debug'`**

This occurs when the host directory doesn't have proper permissions. Fix it:

```bash
# On your VPS host (as ubuntu user)
sudo mkdir -p /home/ubuntu/.claude
sudo chown -R 1000:1000 /home/ubuntu/.claude
sudo chmod -R 755 /home/ubuntu/.claude

# Rebuild and restart container
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d --build

# Try authentication again
docker exec -it trading-agent bash
claude login
exit
```

**Why this happens**: The Docker volume mount uses the host directory's permissions. The container's `appuser` has UID 1000, which must match the host directory ownership.

## Request
Step-by-Step Setup in n8n

1. Create HTTP Request Node

In your n8n workflow:
1. Add HTTP Request node
2. Configure the request:
  - Method: POST
  - URL: http://trading-agent:8012/action

---
2. Configure Authentication

Select Authentication Type:
- Choose: Generic Credential Type → Header Auth

Create New Credential:
1. Click "Create New Credential"
2. Credential Type: Header Auth
3. Credential Name: Trading Agent Token (or any name you prefer)
4. Add header:
  - Name: Authorization
  - Value: Bearer abcde (or your actual token)

## Available Tools

### Polygon MCP - Market Data & Research

**Market News & Reference Data**
- `polygon_news` - Market news with ticker/date filtering
- `polygon_ticker_details` - Detailed ticker information
- `polygon_market_holidays` - Market holiday calendar
- `polygon_market_status` - Real-time market status

**Real-Time Price Data**
- `polygon_crypto_last_trade` - Most recent trade execution
- `polygon_crypto_snapshot_ticker` - Real-time price, volume, 24h statistics
- `polygon_crypto_snapshot_book` - Current order book (bid/ask)
- `polygon_crypto_snapshots` - Multi-ticker snapshots
- `polygon_crypto_gainers_losers` - Top performing cryptocurrencies

**Historical OHLCV Data**
- `polygon_crypto_aggregates` - Historical aggregate bars with customizable timeframes
- `polygon_crypto_previous_close` - Previous day's closing data
- `polygon_crypto_daily_open_close` - Daily OHLC for specific dates
- `polygon_crypto_grouped_daily` - Grouped daily bars across multiple pairs
- `polygon_crypto_trades` - Trade-by-trade historical data

**Technical Indicators**
- `polygon_crypto_rsi` - Relative Strength Index (overbought/oversold)
- `polygon_crypto_ema` - Exponential Moving Average (trend following)
- `polygon_crypto_macd` - Moving Average Convergence Divergence
- `polygon_crypto_sma` - Simple Moving Average (trend identification)

**Reference Data**
- `polygon_crypto_tickers` - Available cryptocurrency tickers
- `polygon_crypto_exchanges` - Exchange information
- `polygon_crypto_conditions` - Trade condition codes

### Binance MCP - Trading & Portfolio Management

**Market Data (Read-Only)**
- `binance_get_ticker` - 24hr price change statistics
- `binance_get_orderbook` - Current bid/ask order book
- `binance_get_recent_trades` - Recent market trades
- `binance_get_price` - Latest price for symbol(s)
- `binance_get_book_ticker` - Best bid/ask prices
- `binance_get_avg_price` - Average price over time window

**Account Management (Read-Only)**
- `binance_get_account` - Portfolio balances with USDT valuations
- `binance_get_open_orders` - Currently active orders
- `binance_spot_trade_history` - Executed trade history with P&L data

**Spot Trading**
- `binance_spot_market_order` - Execute market buy/sell orders
- `binance_spot_limit_order` - Place limit orders (GTC/IOC/FOK)
- `binance_spot_oco_order` - One-Cancels-Other orders (take-profit + stop-loss)
- `binance_cancel_order` - Cancel individual or all orders

**Futures Trading**
- `binance_set_futures_leverage` - Configure leverage for symbol
- `binance_manage_futures_positions` - Open/close/modify futures positions
- `binance_calculate_liquidation_risk` - Calculate liquidation prices and risk

**Analysis & Risk Management**
- `binance_calculate_spot_pnl` - Profit/loss analysis with fee tracking
- `trading_notes` - Save and retrieve trading decisions/observations

### Python Code Execution

**Built-in Analysis Tool**
- `mcp__ide__executeCode` - Execute Python code with pandas/numpy pre-loaded for CSV analysis

## Configuration

### MCP Servers

This project utilizes the following Model Context Protocol (MCP) repositories:

- **[mcp-binance](https://github.com/format37/mcp-binance)** - Provides comprehensive Binance exchange integration including spot trading, futures trading, account management, and portfolio analytics
- **[mcp-polygon](https://github.com/format37/mcp-polygon)** - Delivers market data and technical analysis capabilities through Polygon.io APIs including real-time prices, historical data, and technical indicators
- **[mcp-perplexity](https://github.com/format37/mcp-perplexity)** - Providing Perplexity AI-powered web search and research capabilities. All tools return JSON responses directly from the Perplexity API.

### MCP Server Configuration

#### Required MCP Servers

The trading agent requires three MCP servers to function:

1. **Polygon MCP** (`mcp-polygon`) - Market data and technical indicators
2. **Binance MCP** (`mcp-binance-local`) - Trading execution and account management
3. **Perplexity MCP** (`mcp-perplexity-local`) - Market intelligence and research

#### Environment Variables

Configure MCP server URLs in `.env.prod`:

```bash
# Polygon MCP - Market data
POLYGON_URL=http://mcp-polygon:8006/polygon/

# Binance MCP - Trading execution
BINANCE_URL=http://mcp-binance-local:8010/binance/

# Perplexity MCP - Market intelligence
PERPLEXITY_URL=http://mcp-perplexity-local:8011/perplexity/

# Optional: Enable strict MCP connectivity check at startup
# If set to "true", agent exits immediately if any MCP server is unreachable
# If set to "false" (default), agent shows warnings but continues
STRICT_MCP_CHECK=false
```

#### MCP Connectivity Checks

The trading agent includes two levels of MCP server validation:

**1. Pre-flight Connectivity Check (Optional)**
- Runs before agent initialization
- Tests HTTP connectivity to each MCP server
- Controlled by `STRICT_MCP_CHECK` environment variable
- Default behavior: Shows warnings but continues (allows testing in development)
- Production recommendation: Set `STRICT_MCP_CHECK=true` for fail-fast behavior

**2. Runtime MCP Status Check (Mandatory)**
- Monitors MCP server status during agent initialization
- Automatically exits if any MCP server fails to connect
- Provides detailed troubleshooting information
- Cannot be disabled (required for agent functionality)

#### Docker Network Requirements

**Network Configuration:**
```yaml
# docker-compose.prod.yml
networks:
  mcp-shared:
    external: true
```

**Requirements:**
- All MCP servers must be on the `mcp-shared` Docker network
- Trading agent container must also be on `mcp-shared` network
- Service names (e.g., `mcp-binance-local`) must resolve within the network

**Verify network connectivity:**
```bash
# Check if network exists
docker network inspect mcp-shared

# Check which containers are on the network
docker network inspect mcp-shared | grep Name
```

## CSV Data Persistence

All CSV files are stored in `data/mcp-{server_name}/` with unique identifiers:

```
data/
├── mcp-binance/
│   ├── account_fc2d93fb.csv
│   ├── orderbook_BTCUSDT_20_2ba055fa.csv
│   ├── market_order_BTCUSDT_sell_e0ece103.csv
│   └── trading_notes/
│       └── strategy.md
└── mcp-polygon/
    ├── crypto_rsi_X_BTCUSD_w14_hour_a62e072d.csv
    ├── crypto_macd_X_BTCUSD_12-26-9_hour_978c58a5.csv
    └── market_status_9f3c1cfe.csv
```

## Subagent Architecture

### How Subagents Work

Subagents are specialized AIs orchestrated by the main trading agent. Each subagent has:

1. **Specialized System Prompt**: Domain-specific expertise and instructions
2. **Restricted Tools**: Only the tools necessary for their role
3. **Separate Context**: Won't pollute main agent's context with detailed analysis
4. **Parallel Execution**: Multiple subagents can run simultaneously

### Subagent Prompts

All subagent prompts are stored in `prompts/` directory:

```
prompts/
├── btc_researcher.md       # Bitcoin analysis specialist
├── eth_researcher.md       # Ethereum ecosystem specialist
├── altcoin_researcher.md   # Altcoin opportunity discovery
├── market_intelligence.md  # Web research & macro analysis
├── technical_analyst.md    # Pure chart analysis expert
├── risk_manager.md         # Portfolio risk assessment
├── data_analyst.md         # Statistical analysis specialist
└── futures_analyst.md      # Futures trading & leverage specialist
```

### Tool Restrictions by Role

**Read-Only Subagents** (Cannot execute trades):
- market-intelligence: Only Perplexity tools + polygon_news
- risk-manager: Only account/risk analysis tools
- technical-analyst: Only price data + indicators
- data-analyst: Only Python execution + Read

**Research Subagents** (Can fetch data but not trade):
- btc-researcher: Polygon + Perplexity + Binance market data
- eth-researcher: Polygon + Perplexity + Binance market data
- altcoin-researcher: Polygon + Perplexity + Binance market data

**Trading Specialist** (Can analyze and recommend but main agent executes):
- futures-analyst: Binance futures data + liquidation calculator + leverage tools
  - Analyzes funding rates and basis spreads
  - Calculates safe leverage levels (max 2-5x recommended)
  - Validates liquidation risk before futures positions
  - Can recommend futures positions but main agent executes

**Main Agent** (Full authority):
- All MCP tools including spot and futures trading execution
- Can invoke any subagent
- Makes final trading decisions
- Executes both spot and futures orders

## License

MIT License - See LICENSE file for details.

## Disclaimer

This software is for educational and research purposes. Cryptocurrency trading involves substantial risk of loss. Always perform your own due diligence and never trade with funds you cannot afford to lose. The authors and contributors are not responsible for any financial losses incurred through the use of this software.
