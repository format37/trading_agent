# MCP Tools Reference

Complete documentation of all Model Context Protocol (MCP) tools available to the trading agent. All tools return CSV file paths for mandatory quantitative analysis.

## Polygon MCP - Market Data & Research

### Market News & Reference Data

- **`polygon_news`** - Market news with ticker/date filtering
  - Returns news articles with sentiment analysis potential
  - Filterable by ticker symbol and date range

- **`polygon_ticker_details`** - Detailed ticker information
  - Symbol metadata, market cap, description
  - Exchange listing information

- **`polygon_market_holidays`** - Market holiday calendar
  - Upcoming market closures and special hours

- **`polygon_market_status`** - Real-time market status
  - Current trading session status
  - After-hours and pre-market indicators

### Real-Time Price Data

- **`polygon_crypto_last_trade`** - Most recent trade execution
  - Latest executed trade price and volume
  - Timestamp and exchange information

- **`polygon_crypto_snapshot_ticker`** - Real-time price snapshot
  - Current price, volume, 24-hour statistics
  - Day's high/low, volume weighted average price

- **`polygon_crypto_snapshot_book`** - Current order book
  - Best bid/ask prices and sizes
  - Market depth information

- **`polygon_crypto_snapshots`** - Multi-ticker snapshots
  - Bulk snapshot data for multiple pairs
  - Efficient for portfolio-wide analysis

- **`polygon_crypto_gainers_losers`** - Top performing cryptocurrencies
  - Biggest gainers and losers by percentage
  - Volume and price change metrics

### Historical OHLCV Data

- **`polygon_crypto_aggregates`** - Historical aggregate bars
  - Customizable timeframes (1min to 1month)
  - OHLCV with volume and trade count

- **`polygon_crypto_previous_close`** - Previous day's closing data
  - Prior session close, high, low, volume

- **`polygon_crypto_daily_open_close`** - Daily OHLC for specific dates
  - Historical daily data for backtesting

- **`polygon_crypto_grouped_daily`** - Grouped daily bars
  - Multiple pairs' daily data in one request
  - Efficient for correlation analysis

- **`polygon_crypto_trades`** - Trade-by-trade historical data
  - Granular execution data
  - For detailed market microstructure analysis

### Technical Indicators

- **`polygon_crypto_rsi`** - Relative Strength Index
  - Overbought/oversold conditions (14-period default)
  - Momentum oscillator between 0-100

- **`polygon_crypto_ema`** - Exponential Moving Average
  - Trend following with recent price emphasis
  - Multiple period support (12, 26, 50, 200)

- **`polygon_crypto_macd`** - Moving Average Convergence Divergence
  - Trend and momentum indicator
  - Signal line crossovers for entry/exit

- **`polygon_crypto_sma`** - Simple Moving Average
  - Basic trend identification
  - Support/resistance levels

### Reference Data

- **`polygon_crypto_tickers`** - Available cryptocurrency tickers
  - Complete list of tradeable pairs
  - Symbol mapping and naming conventions

- **`polygon_crypto_exchanges`** - Exchange information
  - Supported exchanges and their codes

- **`polygon_crypto_conditions`** - Trade condition codes
  - Decoding special trade conditions

## Binance MCP - Trading & Portfolio Management

### Market Data (Read-Only)

- **`binance_get_ticker`** - 24hr price change statistics
  - Percentage changes, volume, quote volume
  - High/low prices for the period

- **`binance_get_orderbook`** - Current bid/ask order book
  - Market depth up to 5000 levels
  - Bid/ask imbalance analysis

- **`binance_get_recent_trades`** - Recent market trades
  - Latest 500-1000 executed trades
  - Trade flow and momentum analysis

- **`binance_get_price`** - Latest price for symbol(s)
  - Current market price
  - Bulk pricing for multiple symbols

- **`binance_get_book_ticker`** - Best bid/ask prices
  - Top of book quotes
  - Spread analysis

- **`binance_get_avg_price`** - Average price over time window
  - 5-minute average price
  - Smoothed price for volatility reduction

### Account Management (Read-Only)

- **`binance_get_account`** - Portfolio balances with USDT valuations
  - All asset balances
  - Free and locked amounts
  - Total portfolio value in USDT

- **`binance_get_open_orders`** - Currently active orders
  - Pending limit orders
  - Order status and remaining quantity

- **`binance_spot_trade_history`** - Executed trade history
  - Complete trade log with fees
  - Profit/loss data per trade
  - Commission information

### Spot Trading

- **`binance_spot_market_order`** - Execute market buy/sell orders
  - Immediate execution at best available price
  - Supports both quote and base currency amounts

- **`binance_spot_limit_order`** - Place limit orders
  - Good-Till-Cancelled (GTC)
  - Immediate-Or-Cancel (IOC)
  - Fill-Or-Kill (FOK)

- **`binance_spot_oco_order`** - One-Cancels-Other orders
  - Combined take-profit and stop-loss
  - Risk management in single order

- **`binance_cancel_order`** - Cancel orders
  - Cancel specific order by ID
  - Cancel all orders for a symbol

### Futures Trading

- **`binance_set_futures_leverage`** - Configure leverage for symbol
  - Adjust leverage (1x to 125x depending on pair)
  - Risk management control

- **`binance_manage_futures_positions`** - Position management
  - Open new positions
  - Close existing positions
  - Modify position size

- **`binance_calculate_liquidation_risk`** - Risk calculation
  - Calculate liquidation prices
  - Margin requirements
  - Risk-to-reward ratios

### Analysis & Risk Management

- **`binance_calculate_spot_pnl`** - Profit/loss analysis
  - Realized and unrealized P&L
  - Fee impact analysis
  - Performance metrics

- **`trading_notes`** - Trading decision storage
  - Save strategy observations
  - Retrieve historical decisions
  - Maintain trading journal

## Perplexity MCP - Market Intelligence

### Web Research Tools

- **`perplexity_search`** - AI-powered web search
  - Real-time information gathering
  - Source citations included
  - Fact-checked responses

- **`perplexity_market_analysis`** - Market trend analysis
  - Macro economic factors
  - Industry trends
  - Competitive landscape

- **`perplexity_news_sentiment`** - News sentiment analysis
  - Aggregate sentiment scoring
  - Source diversity metrics
  - Trend identification

## Python Code Execution

### Built-in Analysis Tool

- **`mcp__ide__executeCode`** - Execute Python code
  - Pre-loaded with pandas, numpy, matplotlib
  - Direct CSV file analysis
  - Statistical computations
  - Data visualization capabilities

## CSV Data Structure

All MCP tools return CSV files with standardized structures:

### Example: RSI Data
```csv
timestamp,value,signal
2024-01-15T10:00:00Z,72.5,overbought
2024-01-15T11:00:00Z,68.3,neutral
```

### Example: Account Data
```csv
asset,free,locked,usdt_value
BTC,0.05234,0.0,5234.00
ETH,2.3456,0.1,4567.89
USDT,1000.0,0.0,1000.00
```

### Example: Order Book Data
```csv
price,quantity,side
95000,0.5,bid
94999,1.2,bid
95001,0.8,ask
95002,1.5,ask
```

## Tool Response Patterns

All tools follow a consistent response pattern:

1. **Tool Call** → MCP Server processes request
2. **CSV Generation** → Data saved to `data/mcp-{server}/`
3. **Path Return** → Tool returns file path
4. **Agent Analysis** → Must read CSV and execute Python code

Example workflow:
```python
# 1. Agent calls tool
response = polygon_crypto_rsi("X:BTCUSD", timespan="hour")

# 2. Response contains path
# "data/mcp-polygon/crypto_rsi_X_BTCUSD_w14_hour_abc123.csv"

# 3. Agent must analyze
df = pd.read_csv(response['path'])
latest_rsi = df['value'].iloc[-1]

# 4. Decision making
if latest_rsi > 70:
    # Overbought condition
    ...
```

## Rate Limits and Constraints

### Polygon
- 5 requests per minute (free tier)
- Unlimited with paid subscription
- Historical data limited to 2 years

### Binance
- Weight-based rate limiting
- Order placement: 10 orders/second
- Data requests: 1200 weight/minute

### Perplexity
- 100 searches per day
- Response cached for 15 minutes
- Maximum 4000 tokens per response

## Error Handling

All tools return standardized error CSVs when failures occur:

```csv
error,message,timestamp
API_ERROR,"Rate limit exceeded",2024-01-15T10:00:00Z
```

The agent must check for error conditions before processing data.