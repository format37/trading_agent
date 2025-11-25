# Trading Session - Benchmark Competition Mode

Execute systematic trading strategy to outperform the 33% BTC / 33% ETH / 33% USDT benchmark.

## Session Checklist (MANDATORY)

### Pre-Trading Analysis
- [ ] Check current portfolio allocation
- [ ] Calculate deviation from 33/33/33 benchmark
- [ ] Review previous trading notes for context
- [ ] Check if any rebalancing triggers are active

### Subagent Consultation
- [x] Call `risk-manager` for risk assessment (REQUIRED)
- [ ] Call `btc-researcher` for Bitcoin analysis (as needed)
- [ ] Call `eth-researcher` for Ethereum analysis (as needed)
- [ ] Call `altcoin-researcher` for alternative opportunities (as needed)
- [ ] Call `market-intelligence` for sentiment check (as needed)
- [ ] Call `technical-analyst` for chart patterns (as needed)
- [ ] Call `data-analyst` for statistical analysis (as needed)
- [ ] Call `futures-analyst` for funding rates (as needed)

### CSV Analysis
- [ ] Use py_eval for EVERY CSV file received
- [ ] Calculate benchmark performance comparison
- [ ] Analyze allocation deviation metrics

### Trading Decision
- [ ] Check FOMO warning signals
- [ ] Determine if rebalancing needed
- [ ] Calculate position sizes based on target allocation
- [ ] Execute trades with appropriate order types

### Documentation
- [ ] Record current vs target allocation
- [ ] Document rebalancing actions
- [ ] Note subagent consensus level
- [ ] Log any FOMO signals detected

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

## Anti-FOMO Reminder

Before ANY trade, ask yourself:
- Am I chasing a pump? → Don't
- Is this fear or greed? → Default to benchmark
- Am I deviating too far from 33/33/33? → Rebalance

## Authority & Execution

- Full trading authority within rebalancing framework
- Execute systematically, not emotionally
- Use risk-manager (required) and relevant subagents based on context
- Document everything for next session

## Session Type

Single-turn autonomous execution with MANDATORY completion of all checklist items.

Proceed with systematic analysis and disciplined trading.