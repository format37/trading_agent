# Before
Recently we had some issues with the binance_spot_oco_order MCP tool:
```
[Turn 1] Claude:

I understand. I'll test the fixed `binance_spot_oco_order` tool carefully with a small amount to verify it now works correctly with the new Binance API v3 parameters.

Let me start by checking the current market conditions and account status to plan a safe, minimal-risk test.
Good! Now let me analyze the account to understand what we have available for testing:

[Executing Python code for analysis]
Let me read the account CSV directly:
Perfect! Now let me analyze this data:

## Account Analysis

**Portfolio Value**: ~$655.85 USD total
- BTC: 0.00415896 BTC = $460.14 (70.2%)
- ETH: 0.03229848 ETH = $128.61 (19.6%)
- USDT: $65.58 (10.0%)
- USDC: $1.50 (0.2%)
- SOL: 0.00028024 SOL = $0.06 (0.01%)

**Current BTC Price**: $110,637.92

## Test Plan: OCO Order with Minimal Risk

I'll test with **0.00005 BTC** (exactly as mentioned in the original test notes):
- **Test Value**: ~$5.53 USD (0.84% of portfolio)
- **We have sufficient BTC**: 0.00415896 BTC available ✓

For a **SELL OCO order**, I'll use **very conservative parameters**:
- **Take Profit**: +0.5% above current price ($111,191.34)
- **Stop Loss**: -0.5% below current price ($110,084.50)
- **Stop Limit**: Slightly below stop ($110,030)

**Maximum Risk**: $0.028 USD (if stop hits)
**Maximum Profit**: $0.028 USD (if take profit hits)

This is an extremely safe test - we're risking less than 3 cents to verify the tool works.

Let me proceed with the test:
Interesting! The fix introduced a new issue - it's sending `aboveTimeInForce` when it's not required. Let me document this finding:
## Test Results Summary

❌ **Test Failed** - New issue discovered after the v3 API fix.

### What Happened

The development team's fix correctly addressed the missing `aboveType`/`belowType` parameters, but introduced a new error:

**Error**: `APIError(code=-1106): Parameter 'aboveTimeInForce' sent when not required.`

### Root Cause

The Binance API has **conditional requirements** for the `timeInForce` parameter:
- **LIMIT_MAKER orders**: Do NOT accept `timeInForce` (always GTC by definition)
- **STOP_LOSS_LIMIT orders**: REQUIRE `timeInForce` parameter

The current implementation appears to be sending `timeInForce` for both order types, when it should only be sent for the stop-loss leg.

### Correct Parameter Structure

**For SELL OCO** (what we tested):
```python
{
    "aboveType": "LIMIT_MAKER",        # Take profit above
    "abovePrice": 111191.34,           # Take profit price
    # ❌ NO aboveTimeInForce for LIMIT_MAKER
    
    "belowType": "STOP_LOSS_LIMIT",    # Stop loss below
    "belowStopPrice": 110084.50,       # Stop trigger
    "belowPrice": 110030,              # Stop limit price
    "belowTimeInForce": "GTC"          # ✓ Required for STOP_LOSS_LIMIT
}
```

**For BUY OCO** (opposite):
```python
{
    "aboveType": "STOP_LOSS_LIMIT",    # Stop loss above
    "aboveStopPrice": X,               # Stop trigger
    "abovePrice": Y,                   # Stop limit price
    "aboveTimeInForce": "GTC",         # ✓ Required for STOP_LOSS_LIMIT
    
    "belowType": "LIMIT_MAKER",        # Take profit below
    "belowPrice": Z,                   # Take profit price
    # ❌ NO belowTimeInForce for LIMIT_MAKER
}
```

### Required Fix

In `backend/binance_tools/spot_oco_order.py`, the code needs to:
1. Only send `aboveTimeInForce` when `aboveType == "STOP_LOSS_LIMIT"`
2. Only send `belowTimeInForce` when `belowType == "STOP_LOSS_LIMIT"`
3. Never send `timeInForce` for `LIMIT_MAKER` orders

### Test Details

- **Account**: Real account with ~$655 portfolio
- **Test Amount**: 0.00005 BTC (~$5.53 USD, 0.84% of portfolio)
- **Maximum Risk**: ~$0.03 USD
- **Test was safe**: No funds at risk due to API validation catching the error

### Documentation

I've saved detailed technical notes to `tool_notes/binance_spot_oco_order.md` for the development team with the exact fix needed.

### Status

🔴 **Tool remains non-functional** - Awaiting fix for conditional `timeInForce` parameter logic.

The good news: We're very close! The team correctly implemented the new v3 API structure, just needs one more adjustment for the conditional `timeInForce` parameter.
```

Sentry logs:
```
{
  "payload_size": "582",
  "project_id": "4510187772772352",
  "severity_number": "17",
  "tags[code.line.number,number]": "158",
  "tags[process.pid,number]": "1",
  "tags[thread.id,number]": "130193114823552",
  "timestamp_precise": "1760546776223194000",
  "code.file.path": "binance_tools/spot_oco_order.py",
  "code.function.name": "execute_oco_order",
  "environment": "mcp-binance-local",
  "logger.name": "binance_tools.spot_oco_order",
  "message": "Error placing OCO order: APIError(code=-1106): Parameter 'aboveTimeInForce' sent when not required.",
  "origin": "auto.logger.log",
  "process.executable.name": "MainProcess",
  "sdk.name": "sentry.python.starlette",
  "sdk.version": "2.41.0",
  "server.address": "17cc0870444f",
  "severity": "error",
  "thread.name": "MainThread",
  "trace": "2d087931ed684b1d87794916f30c647a",
  "trace.parent_span_id": "b52f2e9d074afcdd",
  "id": "abf50386d8eba9a39b789fe4c3e89901",
  "observed_timestamp_nanos": "1760546779766627817"
}
{
  "payload_size": "548",
  "project_id": "4510187772772352",
  "severity_number": "17",
  "tags[code.line.number,number]": "100",
  "tags[process.pid,number]": "1",
  "tags[thread.id,number]": "130193114823552",
  "timestamp_precise": "1760546776241972000",
  "code.file.path": "sentry_utils.py",
  "code.function.name": "wrapper",
  "environment": "mcp-binance-local",
  "logger.name": "sentry_utils",
  "message": "Error in binance_spot_oco_order: APIError(code=-1106): Parameter 'aboveTimeInForce' sent when not required.",
  "origin": "auto.logger.log",
  "process.executable.name": "MainProcess",
  "sdk.name": "sentry.python.starlette",
  "sdk.version": "2.41.0",
  "server.address": "17cc0870444f",
  "severity": "error",
  "thread.name": "MainThread",
  "trace": "2d087931ed684b1d87794916f30c647a",
  "trace.parent_span_id": "b52f2e9d074afcdd",
  "id": "88b6300b79a7a286fb79b1e4c3e89901",
  "observed_timestamp_nanos": "1760546779766627817"
}
{
  "payload_size": "587",
  "project_id": "4510187772772352",
  "severity_number": "17",
  "tags[code.line.number,number]": "390",
  "tags[process.pid,number]": "1",
  "tags[thread.id,number]": "130193114823552",
  "timestamp_precise": "1760546776255799000",
  "code.file.path": "binance_tools/spot_oco_order.py",
  "code.function.name": "binance_spot_oco_order",
  "environment": "mcp-binance-local",
  "logger.name": "binance_tools.spot_oco_order",
  "message": "Error placing OCO order: APIError(code=-1106): Parameter 'aboveTimeInForce' sent when not required.",
  "origin": "auto.logger.log",
  "process.executable.name": "MainProcess",
  "sdk.name": "sentry.python.starlette",
  "sdk.version": "2.41.0",
  "server.address": "17cc0870444f",
  "severity": "error",
  "thread.name": "MainThread",
  "trace": "aece6efd018f4340a651a28277340358",
  "trace.parent_span_id": "a6c6e7110a69585c",
  "id": "fb7a063eeac4eba42074bfe4c3e89901",
  "observed_timestamp_nanos": "1760546779766627817"
}
```

# Now
My team fixed these issues. They provided the following resolution:
```
✅ Fix Complete

  Changes Made to backend/binance_tools/spot_oco_order.py

  Removed invalid timeInForce parameters for LIMIT_MAKER orders:

  1. SELL OCO (lines 93-104):
    - ❌ Removed aboveTimeInForce="GTC" from the LIMIT_MAKER order (take profit)
    - ✅ Kept belowTimeInForce=time_in_force for STOP_LOSS_LIMIT order (stop loss)
  2. BUY OCO (lines 105-116):
    - ❌ Removed belowTimeInForce="GTC" from the LIMIT_MAKER order (take profit)
    - ✅ Kept aboveTimeInForce=time_in_force for STOP_LOSS_LIMIT order (stop loss)

  What This Fixes

  This resolves the Sentry error:
  APIError(code=-1106): Parameter 'aboveTimeInForce' sent when not required.

  Final API Call Structure

  For SELL orders:
  aboveType="LIMIT_MAKER"           # Take profit
  abovePrice=<take_profit_price>    # ✓
  # NO aboveTimeInForce              # ✓ Correctly omitted

  belowType="STOP_LOSS_LIMIT"       # Stop loss
  belowStopPrice=<stop_loss_price>  # ✓
  belowPrice=<stop_limit_price>     # ✓
  belowTimeInForce=<time_in_force>  # ✓ Required for STOP_LOSS_LIMIT

  For BUY orders:
  belowType="LIMIT_MAKER"           # Take profit
  belowPrice=<take_profit_price>    # ✓
  # NO belowTimeInForce              # ✓ Correctly omitted

  aboveType="STOP_LOSS_LIMIT"       # Stop loss
  aboveStopPrice=<stop_loss_price>  # ✓
  abovePrice=<stop_limit_price>     # ✓
  aboveTimeInForce=<time_in_force>  # ✓ Required for STOP_LOSS_LIMIT

  Testing Status

  - ✅ Python syntax validation passed
  - ✅ Code properly handles both SELL and BUY cases
  - ✅ Conditional timeInForce logic correctly implemented
  - 🔄 Ready for real-world testing with the same parameters (BTCUSDT, SELL, 0.00005, etc.)

  The binance_spot_oco_order tool should now work correctly with the Binance API v3 requirements!
```
We need to test these tools. When u would perform these tests, please note that account is real. Do not perfrom risky operations. Test with small amount in usd terms.
