import asyncio
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, AssistantMessage, TextBlock, ToolUseBlock
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

async def main():
    """Conservative Trading Agent with full MCP tool access for market analysis and execution."""

    # Load trading prompt
    with open("trading_prompt.md", "r") as f:
        trading_prompt = f.read()

    # Configure options with all MCP tools
    options = ClaudeAgentOptions(
        # System prompt for conservative trading
        system_prompt=trading_prompt,

        # Analysis and utility tools
        allowed_tools=[
            "mcp__ide__executeCode",  # Python code execution for data analysis
            "Read",  # Read CSV files returned by MCP tools

            # Polygon MCP - Market News & Reference Data
            "mcp__polygon__polygon_news",
            "mcp__polygon__polygon_ticker_details",
            "mcp__polygon__polygon_market_holidays",
            "mcp__polygon__polygon_market_status",

            # Polygon MCP - Real-Time Price Data
            "mcp__polygon__polygon_crypto_last_trade",
            "mcp__polygon__polygon_crypto_snapshot_ticker",
            "mcp__polygon__polygon_crypto_snapshot_book",
            "mcp__polygon__polygon_crypto_snapshots",
            "mcp__polygon__polygon_crypto_gainers_losers",

            # Polygon MCP - Historical OHLCV Data
            "mcp__polygon__polygon_crypto_aggregates",
            "mcp__polygon__polygon_crypto_previous_close",
            "mcp__polygon__polygon_crypto_daily_open_close",
            "mcp__polygon__polygon_crypto_grouped_daily",
            "mcp__polygon__polygon_crypto_trades",

            # Polygon MCP - Technical Indicators
            "mcp__polygon__polygon_crypto_rsi",
            "mcp__polygon__polygon_crypto_ema",
            "mcp__polygon__polygon_crypto_macd",
            "mcp__polygon__polygon_crypto_sma",

            # Polygon MCP - Reference Data
            "mcp__polygon__polygon_crypto_tickers",
            "mcp__polygon__polygon_crypto_exchanges",
            "mcp__polygon__polygon_crypto_conditions",

            # Polygon MCP - Analysis Tools
            "mcp__polygon__polygon_price_data",

            # Binance MCP - Market Data (Read-Only)
            "mcp__binance__binance_get_ticker",
            "mcp__binance__binance_get_orderbook",
            "mcp__binance__binance_get_recent_trades",
            "mcp__binance__binance_get_price",
            "mcp__binance__binance_get_book_ticker",
            "mcp__binance__binance_get_avg_price",

            # Binance MCP - Account Management
            "mcp__binance__binance_get_account",
            "mcp__binance__binance_get_open_orders",
            "mcp__binance__binance_spot_trade_history",

            # Binance MCP - Spot Trading
            "mcp__binance__binance_spot_market_order",
            "mcp__binance__binance_spot_limit_order",
            "mcp__binance__binance_spot_oco_order",
            "mcp__binance__binance_cancel_order",

            # Binance MCP - Futures Trading
            "mcp__binance__binance_set_futures_leverage",
            "mcp__binance__binance_manage_futures_positions",
            "mcp__binance__binance_calculate_liquidation_risk",

            # Binance MCP - Analysis & Risk Management
            "mcp__binance__binance_calculate_spot_pnl",
            "mcp__binance__trading_notes",
        ],

        permission_mode="bypassPermissions",  # Full permissions - no prompts
        cwd=os.getcwd(),

        # MCP Server connections
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
    )

    print("=" * 80)
    print("Conservative Cryptocurrency Trading Agent")
    print("=" * 80)
    print("\nInitializing trading agent with:")
    print("  - Full Polygon MCP access (market data, technicals, news)")
    print("  - Full Binance MCP access (account, trading, risk management)")
    print("  - Conservative portfolio management system prompt")
    print("  - One-day trading horizon\n")
    print("=" * 80)

    async with ClaudeSDKClient(options=options) as client:
        # Initial trading prompt
        initial_prompt = """Please perform a comprehensive market assessment for BTC and ETH:

1. Check current market status and recent crypto news
2. Analyze top gainers/losers to understand market trends
3. Review my current account balance and positions
4. Provide a detailed market assessment with actionable recommendations
5. Perform a weighted trading strategy based on the analysis

Remember to read and analyze all CSV data returned by the MCP tools using Python."""

        await client.query(initial_prompt)
        turn_count = 1

        # Process the initial response
        print(f"\n[Turn {turn_count}] Claude:\n")
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        print(block.text)
                    elif isinstance(block, ToolUseBlock):
                        if block.name == "mcp__ide__executeCode":
                            print(f"\n[Executing Python code for analysis]")

        # Interactive conversation loop
        print("\n" + "=" * 80)
        print("Interactive Mode - You can now respond to Claude")
        print("=" * 80)
        print("Commands:")
        print("  - Type your response to continue the conversation")
        print("  - 'exit' or 'quit' - End the conversation")
        print("  - 'interrupt' - Stop Claude's current task")
        print("=" * 80 + "\n")

        while True:
            try:
                # Get user input
                user_input = input(f"[Turn {turn_count + 1}] You: ").strip()

                if not user_input:
                    print("Please enter a response or command.\n")
                    continue

                # Handle commands
                if user_input.lower() in ['exit', 'quit']:
                    print("\n" + "=" * 80)
                    print(f"Trading session ended after {turn_count} turns.")
                    print("=" * 80)
                    break

                elif user_input.lower() == 'interrupt':
                    await client.interrupt()
                    print("\n[Task interrupted!]\n")
                    continue

                # Send user's response to Claude
                turn_count += 1
                await client.query(user_input)

                # Process Claude's response
                print(f"\n[Turn {turn_count}] Claude:\n")
                async for message in client.receive_response():
                    if isinstance(message, AssistantMessage):
                        for block in message.content:
                            if isinstance(block, TextBlock):
                                print(block.text)
                            elif isinstance(block, ToolUseBlock):
                                if block.name == "mcp__ide__executeCode":
                                    print(f"\n[Executing Python code for analysis]")
                                elif block.name.startswith("mcp__binance"):
                                    # Show when trading actions are being executed
                                    action = block.name.replace("mcp__binance__", "").replace("_", " ").title()
                                    print(f"\n[Executing: {action}]")
                print()  # Add spacing after response

            except KeyboardInterrupt:
                print("\n\n" + "=" * 80)
                print("Trading session interrupted by user.")
                print("=" * 80)
                break
            except EOFError:
                print("\n\n" + "=" * 80)
                print("Trading session ended.")
                print("=" * 80)
                break

if __name__ == "__main__":
    asyncio.run(main())
