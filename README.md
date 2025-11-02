# Claude SDK Trading Agent

AI-powered cryptocurrency trading agent built with Claude SDK and the Model Context Protocol (MCP), featuring systematic CSV-based data analysis and conservative risk management for live market trading.

## Requirements
* mcp-binance
* mcp-polygon
* mcp-perplexity

## Installation
```
git clone https://github.com/format37/trading_agent.git
cd trading_agent
sudo mkdir -p /home/ubuntu/mcp/data
sudo mkdir -p /home/ubuntu/mcp/data/trading_agent/logs
sudo chown -R $USER:$USER /home/ubuntu/mcp/data
./compose_prod.sh
```
Check health:
U can call this for example from the n8n container: http://trading-agent:8012/health

## Claude Authentication

After deploying the container, you need to authenticate Claude CLI to use your Claude subscription instead of API keys.

### Authentication Workflow

1. **Connect to the running container**:
   ```bash
   docker exec -it trading-agent bash
   ```

2. **Authenticate Claude CLI**:
   ```bash
   claude login
   ```
   This will:
   - Open a browser for authentication
   - Save credentials to `/home/appuser/.claude/.credentials.json`
   - Credentials persist across container restarts (via volume mount)

3. **Exit the container**:
   ```bash
   exit
   ```

4. **Restart the trading agent** (to load new credentials):
   ```bash
   docker-compose -f docker-compose.prod.yml restart trading-agent
   ```

### How It Works

- The container includes Node.js 22.x and `@anthropic-ai/claude-code` CLI
- Authentication credentials are stored in `/home/ubuntu/.claude/` on the host (mounted to container)
- The Python SDK (`claude-agent-sdk`) reads credentials from `~/.claude/.credentials.json`
- No API key required in environment variables once authenticated

### Verification

Check if authentication is working:
```bash
docker logs trading-agent
```

You should see the agent starting without API key errors.

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

## Architecture

### Subagent-Powered Parallel Analysis

The trading agent leverages **8 specialized subagents** for parallel execution and domain expertise:

**Asset Research Agents** (Run in Parallel):
- **btc-researcher**: Bitcoin-specific analysis (technical, on-chain, institutional flows)
- **eth-researcher**: Ethereum ecosystem analysis (DeFi, Layer 2, network metrics)
- **altcoin-researcher**: Opportunity discovery in mid/small-cap cryptocurrencies

**Specialized Analysis Agents**:
- **market-intelligence**: Web research specialist (Perplexity-powered macro/sentiment analysis)
- **technical-analyst**: Pure chart analysis expert (multi-timeframe, support/resistance)
- **risk-manager**: Portfolio risk assessment and position sizing validator
- **data-analyst**: Python/pandas statistical analysis specialist
- **futures-analyst**: Futures trading specialist (leverage, funding rates, liquidation risk)

**Key Benefits**:
- **2-3x Faster**: Parallel subagent execution vs sequential analysis
- **Deeper Insights**: Each subagent has specialized expertise and separate context
- **Better Decisions**: Main agent synthesizes multiple expert perspectives
- **Risk Control**: Risk manager validates every trade before execution

### CSV-First Data Analysis Workflow

The agent operates on a structured data pipeline that promotes systematic, evidence-based decision-making:

- **Data Collection**: MCP servers (Polygon + Binance) fetch market data, technical indicators, news, and account information
- **CSV Storage**: All tools save results to CSV files in the shared `data/` folder (mounted across MCP servers and agent)
- **Python Analysis**: Agent reads CSV files and executes pandas/numpy code to analyze patterns, calculate metrics, and identify signals
- **Trading Decisions**: Multi-factor analysis across 7+ dimensions (momentum, trend, price position, order book, sentiment, liquidity)
- **Risk Management**: Conservative position sizing, stop-loss automation, and portfolio diversification

**Multi-Phase Trading Process with Subagents**

Each trading session follows a disciplined workflow orchestrated by the main agent with specialized subagents:

1. **Parallel Market Assessment**
   - Main agent launches btc-researcher, eth-researcher, and market-intelligence subagents IN PARALLEL
   - While subagents analyze, main agent checks market status and account balance
   - Collect and synthesize all subagent reports
   - **Speed**: 2-3 minutes vs 5-6 minutes sequential

2. **Technical Validation**
   - Delegate to technical-analyst subagent for objective chart analysis
   - Optional: Use data-analyst for statistical validation
   - Receive precise entry/exit levels and technical score

3. **Risk Assessment**
   - ALWAYS use risk-manager subagent before executing trades
   - Validates position sizing and portfolio risk
   - Provides APPROVED/REDUCE/REJECT verdict

4. **Trade Execution**
   - Execute only when multiple subagents confirm direction
   - Use technical analyst's entry/exit levels
   - Follow risk manager's position sizing

5. **Ongoing Monitoring**
   - Risk manager periodically checks portfolio health
   - Adjust positions based on changing conditions

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

## Typical Workflow

```python
# 1. Agent fetches market data from Polygon
polygon_crypto_snapshot_ticker(ticker='X:BTCUSD')
# Returns: "✓ Data saved to CSV\nFile: data/mcp-polygon/crypto_snapshot_BTC_a1b2c3.csv"

# 2. Agent reads the CSV file
Read('data/mcp-polygon/crypto_snapshot_BTC_a1b2c3.csv')

# 3. Agent analyzes the data with Python
mcp__ide__executeCode("""
import pandas as pd
df = pd.read_csv('data/mcp-polygon/crypto_snapshot_BTC_a1b2c3.csv')

current_price = df['price'].iloc[0]
volume_24h = df['volume'].iloc[0]
change_24h = df['change_percent'].iloc[0]

print(f"BTC Price: ${current_price:,.2f}")
print(f"24h Change: {change_24h:+.2f}%")
print(f"24h Volume: ${volume_24h:,.0f}")
""")

# 4. Agent fetches technical indicators
polygon_crypto_rsi(ticker='X:BTCUSD', timespan='hour', window=14)
polygon_crypto_macd(ticker='X:BTCUSD', timespan='hour')

# 5. Agent performs multi-factor analysis across all CSVs
# Calculates weighted scores across momentum, trend, sentiment, liquidity

# 6. Agent checks portfolio
binance_get_account()

# 7. Agent executes trades based on data-driven analysis
binance_spot_market_order(symbol='BTCUSDT', side='BUY', quantity=0.001)

# 8. Agent sets protective stop-loss and take-profit
binance_spot_oco_order(
    symbol='BTCUSDT',
    side='SELL',
    quantity=0.001,
    take_profit_price=115000,
    stop_loss_price=110000
)
```

## Trading Strategy

**Conservative Risk Management** (One-Day Horizon)

The agent follows disciplined risk parameters:

- **Capital Preservation First** - Avoid high-risk trades or excessive leverage
- **Position Sizing** - Maximum 5-10% of portfolio per position
- **Stop-Loss Discipline** - Protective stops at 2-3% below entry
- **Risk/Reward Ratio** - Minimum 1:2 reward-to-risk ratio for each trade
- **Diversification** - Maintain exposure across 3-5 uncorrelated assets
- **Leverage Limits** - Minimal leverage (max 2x) only when conditions are highly favorable

**Entry/Exit Rules**

Entry criteria (all must align):
- Multiple technical indicators confirm the same direction
- Risk/reward ratio is favorable (minimum 1:2)
- Market sentiment supports the trade
- Position size fits within risk parameters

Exit triggers:
- Take profit at predetermined targets
- Stop-loss hit (immediate exit)
- Technical setup invalidates (e.g., support breaks)
- End of day if position hasn't moved as expected

## Setup

### Requirements

- Python 3.8+
- Claude SDK (`claude-agent-sdk`)
- Running MCP servers:
  - Polygon MCP (port 8009)
  - Binance MCP (port 8010)
- Shared data folder with proper permissions

### MCP Servers

This project utilizes the following Model Context Protocol (MCP) repositories:

- **[mcp-binance](https://github.com/format37/mcp-binance)** - Provides comprehensive Binance exchange integration including spot trading, futures trading, account management, and portfolio analytics
- **[mcp-polygon](https://github.com/format37/mcp-polygon)** - Delivers market data and technical analysis capabilities through Polygon.io APIs including real-time prices, historical data, and technical indicators

### Installation

```bash
# Install Python dependencies
pip install -r requirements.txt

# Mount shared data folder
./mount.sh

# Configure environment
export ANTHROPIC_API_KEY=your_claude_api_key
```

### Environment Configuration

The agent connects to MCP servers configured in `main.py`:

```python
mcp_servers={
    "polygon": {
        "type": "http",
        "url": "http://localhost:8009/polygon/"
    },
    "binance": {
        "type": "http",
        "url": "http://localhost:8010/binance/"
    }
}
```

Ensure both MCP servers are running and accessible before starting the agent.

### Data Folder Setup

The `data/` folder is mounted via `mount.sh` to enable CSV sharing between MCP servers and the agent:

```bash
#!/bin/bash
mkdir -p ./data
sudo mount --bind /home/alex/projects/data/ ./data
```

This ensures all CSV files saved by MCP tools are immediately accessible to the agent for analysis.

## Usage

The trading agent supports two execution modes:

### 1. Single-Turn Event-Driven Mode (Default)

Designed for server deployment with scheduled tasks or event triggers. The agent processes one analysis cycle and exits automatically.

**Basic Usage:**
```bash
python main.py
```

The agent will:
1. Load trading system prompt and initialize subagents
2. Execute comprehensive market analysis
3. Make autonomous trading decisions
4. Generate session report and exit

**Event-Triggered Usage:**
```bash
python main.py --event-file event.json
```

Example event file (`event.json`):
```json
{
  "type": "market_cap",
  "message": "The Bitcoin MarketCap went above $2,200.0 billion USD.",
  "currency": "BTC",
  "direction": "above",
  "threshold": "2200.0 billion",
  "alert_condition_id": 2281576
}
```
The JSON structure is not strict. It sending to agent as text.

The agent will:
1. Load and process the event data
2. Analyze market conditions related to the event
3. Execute appropriate trading actions
4. Exit with status code (0=success, 1=error, 2=no action)

**Server Deployment Examples:**

Cron job (every 4 hours):
```bash
0 */4 * * * cd /path/to/trading_agent && python main.py >> data/trading_agent/logs/cron.log 2>&1
```

Systemd service for event files:
```bash
# /etc/systemd/system/trading-agent@.service
[Unit]
Description=Trading Agent Event Processor

[Service]
Type=oneshot
WorkingDirectory=/path/to/trading_agent
ExecStart=/usr/bin/python3 main.py --event-file %i
User=trader
```

Call with:
```bash
systemctl start trading-agent@/tmp/event.json
```

**Exit Codes:**
- `0` - Success: Agent completed analysis and/or executed trades
- `1` - Error: Fatal error occurred during execution
- `2` - No Action: Analysis completed but no trades were needed

**Output Files:**
- Log: `data/trading_agent/logs/session_YYYYMMDD_HHMMSS.log`
- Report: `data/trading_agent/session_YYYYMMDD_HHMMSS.md`

### 2. Interactive Multi-Turn Mode

For manual trading sessions with back-and-forth conversation.

```bash
python main.py --interactive
```

The agent will:
1. Load the trading system prompt and initialize subagents
2. Execute initial market assessment
3. Enter interactive mode for ongoing conversation

Once the agent completes its initial analysis, you can:

```
[Turn 2] You: Please execute the rebalancing strategy you recommended

[Turn 3] You: Show me the P&L for my last 10 trades

[Turn 4] You: Analyze ETH technical indicators and recommend entry points
```

Commands:
- `exit` or `quit` - End the trading session
- `interrupt` - Stop Claude's current task

### Example Trading Session

```
================================================================================
Conservative Cryptocurrency Trading Agent
================================================================================

Initializing trading agent with:
  - Full Polygon MCP access (market data, technicals, news)
  - Full Binance MCP access (account, trading, risk management)
  - Conservative portfolio management system prompt
  - One-day trading horizon

================================================================================

[Turn 1] Claude:

I'll perform a comprehensive market assessment for BTC and ETH...

[Executing Python code for analysis]
[Executing: Binance Get Account]
[Executing: Binance Spot Market Order]

## 📊 COMPREHENSIVE MARKET ASSESSMENT COMPLETE

**Market Outlook:** Cautiously Neutral (Confidence: 6/10)

**Key Findings:**
- ✅ Crypto markets open and trading normally
- ⚠ CRITICAL RISK: Portfolio 99.6% concentrated in BTC
- 📈 ETH outperforming BTC (+4.20% vs +1.17%)
- 🎯 Immediate action: Portfolio rebalancing required

**WEIGHTED TRADING STRATEGY**
- Target: 65% BTC, 25% ETH, 10% Cash
- ETH scored 6.90/10 vs BTC's 5.15/10

Would you like me to execute this trading strategy now?

================================================================================
Interactive Mode - You can now respond to Claude
================================================================================

[Turn 2] You: Yes, proceed with the rebalancing

[Turn 2] Claude:

Excellent! Now let's execute the rebalancing strategy...

[Executing: Binance Spot Market Order]
✅ Step 1 completed: Sold 0.00206 BTC at $112,500

[Executing: Binance Spot Market Order]
✅ Step 2 completed: Bought 0.04031 ETH at $4,152

[Executing: Binance Spot Oco Order]
✅ Step 3 completed: Set ETH protection (TP: $4,277 | SL: $4,069)

Portfolio rebalanced successfully!
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

**Benefits:**
- Historical portfolio tracking across sessions
- Performance analysis over time
- Audit trails for all trading decisions
- Systematic backtesting capabilities
- Reproducible data analysis workflows

## Security & Risk Notes

### Trading Risks

- **Live Trading** - This agent executes REAL trades on live Binance accounts
- **Financial Risk** - Every decision has direct financial consequences
- **Market Volatility** - Cryptocurrency markets are highly volatile
- **API Limits** - Respect exchange rate limits and trading restrictions

### API Security

- **Binance API Keys** - Configure with appropriate permissions (spot/futures trading)
- **Read-Only Tools** - Market data and account info tools are read-only
- **Trading Tools** - Clearly marked in tool descriptions; require explicit action
- **MCP Authentication** - Ensure MCP servers use token authentication in production

### Risk Management Best Practices

- **Start Small** - Test with small position sizes initially
- **Monitor Actively** - Review agent decisions before execution in critical markets
- **Stop-Loss Discipline** - Always use stop-losses for risk protection
- **Position Limits** - Respect the 5-10% per position rule
- **Cash Buffer** - Maintain 10%+ cash for opportunities and emergencies

**Conservative Principle**: When in doubt, stay in cash. Preservation > speculation.

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

**Customization**: Edit these prompts to adjust subagent behavior, expertise, and analysis style.

### Parallel Execution Example

When main agent invokes:
```python
# In a single message, launch multiple subagents:
- Use btc-researcher for BTC analysis
- Use eth-researcher for ETH analysis
- Use market-intelligence for macro research
```

**Result**:
- All 3 subagents run simultaneously
- Each maintains separate context (no cross-contamination)
- Main agent receives 3 comprehensive reports
- Total time: ~90 seconds (vs ~270 seconds sequential)

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

## System Prompt

The agent's behavior is defined in `system_prompt.md`, which includes:

- Subagent orchestration strategy (NEW)
- Parallel execution workflow (NEW)
- Conservative risk management principles
- Multi-phase trading process with subagent delegation
- Entry/exit rules with technical criteria
- Position sizing formulas
- Tool usage guidelines
- Decision-making framework with subagent synthesis

Modify this file to customize the agent's trading strategy, risk parameters, and subagent orchestration approach.

## Project Structure

```
trading_agent/
├── main.py                 # Agent entry point with subagent configuration
├── system_prompt.md        # Main agent system prompt with subagent orchestration
├── user_prompt.md          # User task description
├── entrance.md             # Session entrance message
├── prompts/                # Subagent specialized prompts (NEW)
│   ├── btc_researcher.md
│   ├── eth_researcher.md
│   ├── altcoin_researcher.md
│   ├── market_intelligence.md
│   ├── technical_analyst.md
│   ├── risk_manager.md
│   ├── data_analyst.md
│   └── futures_analyst.md
├── telemetry.py            # OpenTelemetry observability
├── requirements.txt        # Python dependencies (claude-agent-sdk)
├── mount.sh                # Script to mount shared data folder
├── data/                   # Shared CSV data folder (mounted)
│   ├── mcp-binance/        # Binance MCP tool outputs
│   └── mcp-polygon/        # Polygon MCP tool outputs
├── examples/
│   └── subagents.md        # Subagent SDK documentation
├── python-sdk.md           # Claude Agent SDK documentation
└── README.md               # This file
```

## Example Analysis Output

The agent performs comprehensive multi-factor analysis before trading:

```
## Technical Analysis Summary

### Bitcoin (BTC/USDT)
- Price: $112,499.97 (+1.17% / 24h)
- RSI(14): 53.16 - NEUTRAL
- MACD: Bullish but weakening momentum
- Order Book: 77% ask-side (selling pressure)
- Weighted Score: 5.15/10.0

### Ethereum (ETH/USDT)
- Price: $4,152.55 (+4.20% / 24h)
- RSI(14): 56.03 - NEUTRAL, Rising
- Order Book: 65% bid-side (buying pressure)
- Outperforming BTC by 3x
- Weighted Score: 6.90/10.0 ✓

### News Sentiment
- 53 crypto articles in last 7 days
- Headlines: "Bitcoin Soared", "Crypto Investments Surge"
- Bullish sentiment around political events
```

## License

MIT License - See LICENSE file for details.

## Disclaimer

This software is for educational and research purposes. Cryptocurrency trading involves substantial risk of loss. Always perform your own due diligence and never trade with funds you cannot afford to lose. The authors and contributors are not responsible for any financial losses incurred through the use of this software.
