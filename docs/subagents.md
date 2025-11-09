# Subagent Architecture

Detailed documentation of the specialized subagent system that enables parallel analysis and token-efficient processing.

## Overview

Subagents are specialized AI agents orchestrated by the main trading agent, each with:
- **Domain expertise** via specialized system prompts
- **Tool restrictions** enforcing their role
- **Separate context** preventing context pollution
- **Parallel execution** capability

## Architecture Benefits

### Token Economy
- Each subagent maintains its own context
- Main agent doesn't carry detailed analysis history
- Reduced token usage by 60-70% in complex analyses

### Enforced Specialization
- Tool restrictions prevent accidental trades by analysts
- Each agent focuses on its domain
- Clear separation of concerns

### Parallel Processing
- Multiple subagents can run simultaneously
- BTC, ETH, and altcoin analysis in parallel
- Faster overall execution time

## Subagent Definitions

### 1. BTC Researcher

**File:** `prompts/btc_researcher.md`

**Purpose:** Deep analysis of Bitcoin market dynamics, on-chain metrics, and institutional flows.

**System Prompt Focus:**
- Bitcoin dominance and market cycles
- Mining difficulty and hash rate impacts
- Institutional adoption indicators
- Lightning Network activity
- Correlation with traditional markets

**Available Tools:**
```python
[
    "polygon_*",           # All market data tools
    "binance_get_*",       # Read-only Binance data
    "perplexity_*",        # Web research
    "mcp__ide__executeCode", # Data analysis
    "Read", "Write"        # File operations
]
```

**Restricted From:**
- Any trading execution
- Order placement
- Position management

**Example Usage:**
```python
btc_analyst = invoke_subagent(
    "btc-researcher",
    "Analyze Bitcoin market structure and identify support/resistance levels"
)
```

### 2. ETH Researcher

**File:** `prompts/eth_researcher.md`

**Purpose:** Ethereum ecosystem analysis including DeFi, L2s, and smart contract activity.

**System Prompt Focus:**
- Gas fee trends and network congestion
- DeFi TVL and yield opportunities
- Layer 2 adoption metrics
- Smart contract deployments
- ETH staking dynamics

**Available Tools:**
```python
[
    "polygon_*",           # All market data tools
    "binance_get_*",       # Read-only Binance data
    "perplexity_*",        # Web research
    "mcp__ide__executeCode", # Data analysis
    "Read", "Write"        # File operations
]
```

**Unique Capabilities:**
- DeFi protocol analysis
- Gas optimization strategies
- L2 arbitrage opportunities
- Staking reward calculations

### 3. Altcoin Researcher

**File:** `prompts/altcoin_researcher.md`

**Purpose:** Discovering opportunities in alternative cryptocurrencies.

**System Prompt Focus:**
- Momentum and breakout patterns
- Volume anomaly detection
- Social sentiment shifts
- New listing opportunities
- Sector rotation (DeFi, Gaming, AI, etc.)

**Available Tools:**
```python
[
    "polygon_crypto_gainers_losers", # Top movers
    "polygon_news",                  # News sentiment
    "polygon_crypto_snapshot*",      # Multi-asset snapshots
    "binance_get_*",                 # Market data
    "perplexity_*",                  # Research
]
```

**Screening Criteria:**
- 24h volume > $1M
- Listed on major exchanges
- Positive momentum indicators
- News catalyst presence

### 4. Market Intelligence

**File:** `prompts/market_intelligence.md`

**Purpose:** Macro analysis and external market factors.

**System Prompt Focus:**
- Regulatory developments
- Macro economic indicators
- Institutional news
- Competitive landscape
- Technology trends

**Available Tools (RESTRICTED):**
```python
[
    "perplexity_*",    # ONLY web research
    "polygon_news",    # ONLY news data
    "Read", "Write"    # File operations
]
```

**Cannot Access:**
- Price data
- Trading functions
- Technical indicators
- Account information

**Output Format:**
```json
{
  "sentiment": "bullish/bearish/neutral",
  "key_factors": ["factor1", "factor2"],
  "risk_events": ["event1", "event2"],
  "recommendation": "text"
}
```

### 5. Technical Analyst

**File:** `prompts/technical_analyst.md`

**Purpose:** Pure chart analysis without fundamental bias.

**System Prompt Focus:**
- Price action patterns
- Support/resistance levels
- Technical indicators (RSI, MACD, EMA)
- Volume profile analysis
- Order flow imbalances

**Available Tools:**
```python
[
    "polygon_crypto_aggregates",  # OHLCV data
    "polygon_crypto_rsi",         # RSI indicator
    "polygon_crypto_macd",        # MACD indicator
    "polygon_crypto_ema",         # Moving averages
    "polygon_crypto_sma",         # Simple MA
    "binance_get_orderbook",     # Order flow
    "binance_get_recent_trades", # Trade flow
    "mcp__ide__executeCode"      # Analysis
]
```

**Analysis Framework:**
```python
def analyze_technicals(symbol):
    # 1. Trend identification (EMA cross)
    # 2. Momentum (RSI, MACD)
    # 3. Volume confirmation
    # 4. Support/resistance levels
    # 5. Entry/exit signals
    return signals
```

### 6. Risk Manager

**File:** `prompts/risk_manager.md`

**Purpose:** Portfolio risk assessment and position sizing.

**System Prompt Focus:**
- Portfolio correlation analysis
- Value at Risk (VaR) calculations
- Maximum drawdown limits
- Position sizing rules
- Stop-loss placement

**Available Tools (HIGHLY RESTRICTED):**
```python
[
    "binance_get_account",          # Portfolio data
    "binance_calculate_spot_pnl",   # P&L analysis
    "binance_get_open_orders",      # Open positions
    "mcp__ide__executeCode",        # Risk calculations
    "Read"                          # Read-only files
]
```

**Risk Parameters:**
```python
MAX_POSITION_SIZE = 0.05  # 5% max per position
MAX_PORTFOLIO_RISK = 0.02  # 2% portfolio risk
MAX_CORRELATION = 0.7      # Position correlation limit
MIN_RISK_REWARD = 2.0     # Minimum R:R ratio
```

### 7. Data Analyst

**File:** `prompts/data_analyst.md`

**Purpose:** Statistical analysis and pattern recognition in CSV data.

**System Prompt Focus:**
- Statistical significance testing
- Correlation analysis
- Pattern recognition
- Backtesting strategies
- Performance metrics

**Available Tools (MINIMAL):**
```python
[
    "mcp__ide__executeCode",  # Python/pandas only
    "Read",                   # Read CSV files
    "Write"                   # Save results
]
```

**Analysis Capabilities:**
```python
# Statistical tests
- Correlation matrices
- Regression analysis
- Time series decomposition
- Monte Carlo simulations
- Sharpe ratio calculations
```

### 8. Futures Analyst

**File:** `prompts/futures_analyst.md`

**Purpose:** Futures market analysis and leverage strategies.

**System Prompt Focus:**
- Funding rate arbitrage
- Basis trading opportunities
- Liquidation level analysis
- Open interest trends
- Perpetual vs spot spreads

**Available Tools:**
```python
[
    "binance_calculate_liquidation_risk", # Risk metrics
    "binance_get_futures_*",              # Futures data (when available)
    "polygon_crypto_*",                   # Spot reference
    "mcp__ide__executeCode",              # Calculations
]
```

**Leverage Rules:**
```python
CONSERVATIVE_LEVERAGE = 2   # Default max
MODERATE_LEVERAGE = 5       # With strong signals
NEVER_EXCEED = 10           # Absolute maximum
```

**Cannot Execute:**
- Opening futures positions (recommends only)
- Setting leverage (calculates safe levels)
- Modifying positions (analysis only)

## Subagent Invocation

### Main Agent Code

```python
# From trading_agent.py
def create_subagent(name, prompt_file, restricted_tools):
    return AgentDefinition(
        name=name,
        description=f"Specialized {name} analyst",
        system_prompt_template=read_file(prompt_file),
        tools=filter_tools(restricted_tools)
    )

# Parallel execution example
async def parallel_analysis(symbols):
    tasks = []
    for symbol in symbols:
        if symbol == "BTC":
            tasks.append(invoke_subagent("btc-researcher", f"Analyze {symbol}"))
        elif symbol == "ETH":
            tasks.append(invoke_subagent("eth-researcher", f"Analyze {symbol}"))
        else:
            tasks.append(invoke_subagent("altcoin-researcher", f"Analyze {symbol}"))

    results = await asyncio.gather(*tasks)
    return combine_analyses(results)
```

### Prompt Templates

Each subagent prompt follows this structure:

```markdown
# {Agent Name} Specialist

You are a specialized {domain} analyst for a cryptocurrency trading system.

## Your Role
- {Primary responsibility}
- {Secondary responsibilities}

## Analysis Framework
1. {Step 1}
2. {Step 2}
3. {Step 3}

## Constraints
- You CANNOT execute trades
- You must provide actionable insights
- Focus only on your domain

## Output Format
Provide analysis in this structure:
- Summary: Brief overview
- Signals: Specific indicators
- Recommendation: Clear action
- Confidence: High/Medium/Low
```

## Tool Restriction Matrix

| Subagent | Market Data | Trading | Account | Research | Analysis |
|----------|------------|---------|---------|----------|----------|
| btc-researcher | ✅ Full | ❌ | Read-only | ✅ Full | ✅ |
| eth-researcher | ✅ Full | ❌ | Read-only | ✅ Full | ✅ |
| altcoin-researcher | ✅ Full | ❌ | Read-only | ✅ Full | ✅ |
| market-intelligence | ❌ | ❌ | ❌ | ✅ Full | ✅ |
| technical-analyst | ✅ Full | ❌ | ❌ | ❌ | ✅ |
| risk-manager | ❌ | ❌ | Read-only | ❌ | ✅ |
| data-analyst | ❌ | ❌ | ❌ | ❌ | ✅ |
| futures-analyst | Futures only | ❌ | Read-only | ❌ | ✅ |

## Performance Optimization

### Context Management

```python
# Subagent context limits
MAX_CONTEXT_TOKENS = 4000  # Per subagent
HISTORY_RETENTION = 0       # No history between calls

# Main agent retains only summaries
def process_subagent_response(response):
    full_analysis = response.content
    summary = extract_key_points(full_analysis)
    store_full_analysis(full_analysis)  # To disk
    return summary  # To main agent context
```

### Parallel Execution

```python
# Optimal parallel configuration
MAX_CONCURRENT_SUBAGENTS = 3
TIMEOUT_PER_SUBAGENT = 30  # seconds

# Resource allocation
CPU_PER_SUBAGENT = 0.5
MEMORY_PER_SUBAGENT = "1GB"
```

## Best Practices

### 1. Subagent Selection

Choose the right subagent for the task:
```python
def select_subagent(task_type):
    mapping = {
        "bitcoin_analysis": "btc-researcher",
        "defi_opportunity": "eth-researcher",
        "momentum_scan": "altcoin-researcher",
        "news_impact": "market-intelligence",
        "chart_pattern": "technical-analyst",
        "position_sizing": "risk-manager",
        "backtest": "data-analyst",
        "funding_arb": "futures-analyst"
    }
    return mapping.get(task_type, "main-agent")
```

### 2. Result Aggregation

Combine multiple subagent outputs:
```python
def aggregate_signals(subagent_results):
    signals = {
        "bullish": [],
        "bearish": [],
        "neutral": []
    }

    for result in subagent_results:
        sentiment = result.get("sentiment")
        confidence = result.get("confidence", 0)
        signals[sentiment].append({
            "source": result["agent"],
            "confidence": confidence,
            "factors": result["factors"]
        })

    # Weight by confidence
    final_sentiment = calculate_weighted_sentiment(signals)
    return final_sentiment
```

### 3. Error Handling

```python
def safe_subagent_invoke(agent_name, prompt, fallback=None):
    try:
        result = invoke_subagent(agent_name, prompt, timeout=30)
        return result
    except TimeoutError:
        log.warning(f"Subagent {agent_name} timed out")
        return fallback or {"status": "timeout", "agent": agent_name}
    except Exception as e:
        log.error(f"Subagent {agent_name} failed: {e}")
        return fallback or {"status": "error", "agent": agent_name}
```

## Monitoring Subagents

### Metrics to Track

```python
SUBAGENT_METRICS = {
    "invocation_count": Counter,
    "success_rate": Gauge,
    "average_duration": Histogram,
    "token_usage": Counter,
    "timeout_count": Counter
}

def track_subagent_performance(agent_name, duration, tokens, success):
    SUBAGENT_METRICS["invocation_count"].inc(agent=agent_name)
    SUBAGENT_METRICS["average_duration"].observe(duration, agent=agent_name)
    SUBAGENT_METRICS["token_usage"].inc(tokens, agent=agent_name)
    if success:
        SUBAGENT_METRICS["success_rate"].set(1, agent=agent_name)
    else:
        SUBAGENT_METRICS["timeout_count"].inc(agent=agent_name)
```

### Logging

```python
import logging

subagent_logger = logging.getLogger("subagents")

def log_subagent_execution(agent_name, prompt, response, duration):
    subagent_logger.info(f"""
    Subagent: {agent_name}
    Prompt: {prompt[:100]}...
    Response: {response.get('summary', 'N/A')}
    Duration: {duration}s
    Confidence: {response.get('confidence', 'N/A')}
    """)
```

## Future Enhancements

### Planned Improvements

1. **Dynamic Tool Assignment** - Adjust tools based on market conditions
2. **Subagent Learning** - Store successful patterns for reuse
3. **Cross-Agent Communication** - Allow subagents to query each other
4. **Specialized Training** - Fine-tune models for specific domains
5. **Adaptive Parallelism** - Scale concurrent agents based on urgency