# Trading Session - Benchmark Competition Mode

Execute systematic trading strategy to outperform the 33% BTC / 33% ETH / 33% USDT benchmark.

## Session Checklist (MANDATORY)

### Phase 1: Context Gathering (DO THIS FIRST)
- [ ] Call `market-intelligence` for context and sentiment (REQUIRED FIRST)
  - Portfolio state vs benchmark
  - Trading notes review
  - News and FOMO/FUD analysis
- [ ] Review Phase 1 recommendations for session priorities

### Phase 2: Parallel Analysis (Based on Phase 1)
- [ ] Call `risk-manager` for risk assessment (REQUIRED)
- [ ] Call relevant subagents based on Phase 1:
  - [ ] `btc-researcher` for Bitcoin analysis (as needed)
  - [ ] `eth-researcher` for Ethereum analysis (as needed)
  - [ ] `altcoin-researcher` for alternative opportunities (as needed)
  - [ ] `technical-analyst` for chart patterns (as needed)
  - [ ] `data-analyst` for statistical analysis (as needed)
  - [ ] `futures-analyst` for funding rates (as needed)

### Phase 3: Critical Review (DO THIS LAST)
- [ ] Compile Phase 2 recommendations summary
- [ ] Call `critic` with summary (REQUIRED LAST)
- [ ] Review critic's challenges and concerns
- [ ] Consider contrarian viewpoints raised

### Phase 4: Synthesis & Decision
- [ ] Synthesize all subagent outputs
- [ ] Factor in critic's challenges
- [ ] Make final trading decision
- [ ] Execute trades with risk management
- [ ] Document in trading notes

### CSV Analysis
- [ ] Use py_eval for EVERY CSV file received
- [ ] Calculate benchmark performance comparison
- [ ] Analyze allocation deviation metrics

### Documentation
- [ ] Record current vs target allocation
- [ ] Document rebalancing actions
- [ ] Note subagent consensus level
- [ ] Log any FOMO signals detected
- [ ] Record critic's main concerns

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

## 3-Phase Workflow Reminder

```
1. market-intelligence (FIRST) → Sets context
2. risk-manager + others (PARALLEL) → Deep analysis
3. critic (LAST) → Challenge assumptions
4. YOU → Synthesize and decide
```

## Anti-FOMO Reminder

Before ANY trade, ask yourself:
- Am I chasing a pump? → Don't
- Is this fear or greed? → Default to benchmark
- Am I deviating too far from 33/33/33? → Rebalance
- Did the critic raise valid concerns? → Address them

## Authority & Execution

- Full trading authority within rebalancing framework
- Execute systematically, not emotionally
- MUST complete all 3 phases before trading
- Document everything for next session

## Session Type

Single-turn autonomous execution with MANDATORY completion of all 3 phases.

Proceed with Phase 1: Call market-intelligence first.