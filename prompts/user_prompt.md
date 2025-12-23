# Trading Session - Benchmark Competition Mode

Execute systematic trading strategy to outperform the 33% BTC / 33% ETH / 33% USDT benchmark.

## Session Checklist (MANDATORY)

### Phase 0: Market Data Collection (FIRST)
- [ ] Call `news-analyst` FIRST for comprehensive market data
  - News analysis CSV
  - Technical indicators CSV (RSI, MACD, EMA, SMA)
  - Market snapshot CSV
  - Gainers/losers CSV

### Phase 1: Context Gathering (SECOND)
- [ ] Call `market-intelligence` for context and sentiment
  - Portfolio state vs benchmark
  - Trading notes review
  - FOMO/FUD analysis using news-analyst output
  - **Action recommendation with confidence score**

### Phase 2: Parallel Analysis
Run these subagents IN PARALLEL:
- [ ] `risk-manager` - **REQUIRED** (has VETO POWER)
- [ ] `technical-analyst` - Chart patterns, rebalancing signals
- [ ] `data-analyst` - Statistical analysis, benchmark tracking
- [ ] `futures-analyst` - Funding rates, sentiment signals

Each returns an **Action Recommendation** with:
- Recommendation type
- Direction (BUY/SELL/HOLD)
- Confidence score (X/10)
- Specific actions

### Phase 3: Synthesis & Consensus
- [ ] Compile recommendations from all subagents
- [ ] Check risk-manager verdict (APPROVE/REJECT)
- [ ] **If risk-manager REJECT → NO TRADE (veto power)**
- [ ] Count aligned recommendations (3/4 majority needed)
- [ ] Formulate trade instructions (if consensus reached)

**Consensus Matrix**:
| Subagent | Recommendation | Direction | Confidence |
|----------|---------------|-----------|------------|
| market-intelligence | [rec] | [dir] | [X/10] |
| technical-analyst | [rec] | [dir] | [X/10] |
| risk-manager | [APPROVE/REJECT] | [dir] | [X/10] |
| data-analyst | [rec] | [dir] | [X/10] |

### Phase 4: Trade Execution (IF APPROVED)
- [ ] Only proceed if: consensus (3/4) + risk-manager APPROVE
- [ ] Call `trader` with specific trade instructions
- [ ] Receive execution confirmation
- [ ] **Skip if no consensus or risk-manager REJECT**

### Phase 5: Session Report (LAST)
- [ ] Call `reporter` ABSOLUTE LAST
- [ ] Read session report CSV with py_eval
- [ ] Include tool usage summary in final response

## CSV Analysis
- [ ] Use py_eval for EVERY CSV file received
- [ ] Calculate benchmark performance comparison
- [ ] Analyze allocation deviation metrics

## Documentation
- [ ] Record current vs target allocation
- [ ] Document consensus level
- [ ] Log risk-manager verdict
- [ ] Note any FOMO signals detected
- [ ] Record trade execution (if any)

## Rebalancing Status Check

**Active Triggers to Monitor**:
1. Deviation >10% from target? → Rebalance
2. Monthly review due? → Check calendar
3. Market moved >20% in 24h? → Adjust positions
4. Cash >50% for 3+ days? → Deploy capital

## Performance Tracking

**Track These Metrics**:
- Current portfolio value vs starting value
- Performance vs benchmark (33/33/33)
- Current allocation percentages
- Days since last rebalancing
- Tracking error from benchmark

## Workflow Summary

```
Phase 0: news-analyst (FIRST) → Market data CSVs
         |
Phase 1: market-intelligence → Context + recommendation
         |
Phase 2: [PARALLEL]
         +-- risk-manager (VETO POWER)
         +-- technical-analyst
         +-- data-analyst
         +-- futures-analyst
         |
Phase 3: YOUR SYNTHESIS → Consensus evaluation
         |
Phase 4: trader (IF APPROVED) → Execute trades
         |
Phase 5: reporter (LAST) → Session report
```

## Consensus Rules

- **risk-manager REJECT = NO TRADE** (overrides all)
- **3/4 agree** = Good consensus, call trader
- **2/4 agree** = Weak consensus, skip or reduce size
- **< 2 agree** = No consensus, no trade

## Anti-FOMO Reminder

Before approving ANY trade, verify:
- Am I chasing a pump? → Don't
- Is this fear or greed? → Default to benchmark
- Am I deviating too far from 33/33/33? → Rebalance
- Did risk-manager approve? → Required for all trades
- Is there consensus (3/4)? → Required for all trades

## Trading Authority

**CRITICAL**:
- You have NO direct trading tools
- All trades MUST go through `trader` subagent
- `trader` is ONLY called after consensus + risk-manager APPROVE

## Session Type

Single-turn autonomous execution with MANDATORY completion of all 5 phases.

Proceed with Phase 0: Call news-analyst first.
