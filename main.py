import asyncio
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AgentDefinition,
    AssistantMessage,
    SystemMessage,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
    ToolUseBlock,
    ToolResultBlock
)
from dotenv import load_dotenv
import os
import json
from datetime import datetime, timezone

# Import telemetry and activity tracking modules
from telemetry import get_telemetry_manager
from activity_tracker import AgentActivityTracker
from session_reporter import SessionReporter

# Load environment variables from .env file
load_dotenv()

# Initialize activity tracker for session reporting
activity_tracker = AgentActivityTracker()

# Initialize telemetry with activity tracking
telemetry = get_telemetry_manager(service_name="claude-trading-agent", activity_tracker=activity_tracker)

# ============================================================================
# Message Display Helpers
# ============================================================================

def format_timestamp():
    """Return current UTC timestamp for logging."""
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]

def print_separator(char="=", length=80):
    """Print a separator line."""
    print(char * length)

def print_section_header(title):
    """Print a formatted section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")

def display_thinking(thinking_block: ThinkingBlock):
    """Display agent's thinking process."""
    print(f"\n[{format_timestamp()}] 💭 THINKING:")
    print("-" * 80)
    # Display thinking with indentation
    for line in thinking_block.thinking.split('\n'):
        print(f"  {line}")
    print("-" * 80)

    # Send telemetry event
    telemetry.trace_thinking(thinking_block.thinking)

def display_tool_use(tool_block: ToolUseBlock):
    """Display tool usage with inputs."""
    print(f"\n[{format_timestamp()}] 🔧 TOOL USE: {tool_block.name}")
    print(f"  ID: {tool_block.id}")
    print(f"  Input:")
    # Pretty print the input
    input_json = json.dumps(tool_block.input, indent=4)
    for line in input_json.split('\n'):
        print(f"    {line}")

    # Send telemetry event
    telemetry.trace_tool_use(tool_block.name, tool_block.id, tool_block.input)

def display_tool_result(result_block: ToolResultBlock):
    """Display tool execution results."""
    print(f"\n[{format_timestamp()}] ✅ TOOL RESULT: {result_block.tool_use_id}")
    if result_block.is_error:
        print(f"  ❌ ERROR: {result_block.content}")
    else:
        # Handle different content types
        if isinstance(result_block.content, str):
            # Truncate very long outputs
            content = result_block.content
            if len(content) > 500:
                print(f"  Result (truncated):")
                print(f"    {content[:500]}...")
                print(f"    ... ({len(content)} total characters)")
            else:
                print(f"  Result:")
                for line in content.split('\n')[:20]:  # Limit to 20 lines
                    print(f"    {line}")
        elif isinstance(result_block.content, list):
            print(f"  Result (structured):")
            for item in result_block.content:
                print(f"    {item}")
        else:
            print(f"  Result: {result_block.content}")

    # Send telemetry event
    result_summary = str(result_block.content) if result_block.content else ""
    telemetry.trace_tool_result(
        result_block.tool_use_id,
        result_block.is_error if result_block.is_error else False,
        result_summary
    )

def display_text(text_block: TextBlock):
    """Display text content from agent."""
    print(f"\n[{format_timestamp()}] 💬 RESPONSE:")
    print(text_block.text)

    # Send telemetry event
    telemetry.trace_response(text_block.text)

def display_system_message(sys_msg: SystemMessage):
    """Display system messages."""
    print(f"\n[{format_timestamp()}] ⚙️  SYSTEM: {sys_msg.subtype}")
    if sys_msg.data:
        print(f"  Data: {json.dumps(sys_msg.data, indent=2)}")

    # Send telemetry event
    telemetry.trace_system_message(sys_msg.subtype, sys_msg.data if sys_msg.data else {})

def display_result(result: ResultMessage):
    """Display final result with usage statistics."""
    print_section_header("SESSION RESULT")
    print(f"Status: {'✅ Success' if not result.is_error else '❌ Error'}")
    print(f"Duration: {result.duration_ms}ms (API: {result.duration_api_ms}ms)")
    print(f"Turns: {result.num_turns}")
    print(f"Session ID: {result.session_id}")

    if result.total_cost_usd:
        print(f"💰 Cost: ${result.total_cost_usd:.4f}")

    if result.usage:
        print(f"\n📊 Token Usage:")
        usage = result.usage
        if isinstance(usage, dict):
            for key, value in usage.items():
                print(f"  {key}: {value}")
        else:
            print(f"  {usage}")

    if result.result:
        print(f"\nResult: {result.result}")

    print_separator()

    # Send telemetry event
    result_data = {
        "duration_ms": result.duration_ms,
        "duration_api_ms": result.duration_api_ms,
        "num_turns": result.num_turns,
        "is_error": result.is_error,
        "session_id": result.session_id,
        "total_cost_usd": result.total_cost_usd,
        "usage": result.usage
    }
    telemetry.trace_session_result(result_data)

def load_subagent_prompts():
    """Load all subagent prompts from the prompts directory."""
    prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")

    # Load each subagent prompt
    subagent_files = {
        "btc-researcher": "btc_researcher.md",
        "eth-researcher": "eth_researcher.md",
        "altcoin-researcher": "altcoin_researcher.md",
        "market-intelligence": "market_intelligence.md",
        "technical-analyst": "technical_analyst.md",
        "risk-manager": "risk_manager.md",
        "data-analyst": "data_analyst.md",
        "futures-analyst": "futures_analyst.md"
    }

    prompts = {}
    for name, filename in subagent_files.items():
        filepath = os.path.join(prompts_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                prompts[name] = f.read()
        else:
            print(f"Warning: Subagent prompt file not found: {filepath}")

    return prompts

def create_subagent_definitions():
    """Create AgentDefinition objects for all subagents."""
    # Load prompts
    prompts = load_subagent_prompts()

    # Define agents with their configurations
    agents = {}

    # BTC Researcher - Parallel asset analysis
    if "btc-researcher" in prompts:
        agents["btc-researcher"] = AgentDefinition(
            description="Bitcoin market analysis specialist. Use for comprehensive BTC analysis when making trading decisions. Provides technical analysis, on-chain metrics, and institutional flow research. Can run in parallel with other researchers.",
            prompt=prompts["btc-researcher"],
            tools=[
                "mcp__polygon__polygon_crypto_snapshot_ticker",
                "mcp__polygon__polygon_crypto_aggregates",
                "mcp__polygon__polygon_crypto_gainers_losers",
                "mcp__polygon__polygon_crypto_rsi",
                "mcp__polygon__polygon_crypto_macd",
                "mcp__polygon__polygon_crypto_ema",
                "mcp__polygon__polygon_crypto_sma",
                "mcp__polygon__polygon_news",
                "mcp__perplexity__perplexity_sonar",
                "mcp__perplexity__perplexity_sonar_pro",
                "mcp__perplexity__perplexity_sonar_reasoning",
                "mcp__binance__binance_get_orderbook",
                "mcp__binance__binance_get_recent_trades",
                "mcp__binance__binance_get_ticker",
                "mcp__binance__binance_get_price",
                "mcp__ide__executeCode",
                "Read"
            ],
            model="sonnet"
        )

    # ETH Researcher - Parallel asset analysis
    if "eth-researcher" in prompts:
        agents["eth-researcher"] = AgentDefinition(
            description="Ethereum ecosystem analysis specialist. Use for comprehensive ETH analysis when making trading decisions. Provides ETH technical analysis, DeFi metrics, Layer 2 adoption, and network activity research. Can run in parallel with other researchers.",
            prompt=prompts["eth-researcher"],
            tools=[
                "mcp__polygon__polygon_crypto_snapshot_ticker",
                "mcp__polygon__polygon_crypto_aggregates",
                "mcp__polygon__polygon_crypto_gainers_losers",
                "mcp__polygon__polygon_crypto_rsi",
                "mcp__polygon__polygon_crypto_macd",
                "mcp__polygon__polygon_crypto_ema",
                "mcp__polygon__polygon_crypto_sma",
                "mcp__polygon__polygon_news",
                "mcp__perplexity__perplexity_sonar",
                "mcp__perplexity__perplexity_sonar_pro",
                "mcp__perplexity__perplexity_sonar_reasoning",
                "mcp__binance__binance_get_orderbook",
                "mcp__binance__binance_get_recent_trades",
                "mcp__binance__binance_get_ticker",
                "mcp__binance__binance_get_price",
                "mcp__ide__executeCode",
                "Read"
            ],
            model="sonnet"
        )

    # Altcoin Researcher - Opportunity discovery
    if "altcoin-researcher" in prompts:
        agents["altcoin-researcher"] = AgentDefinition(
            description="Altcoin opportunity research specialist. Use when seeking portfolio diversification beyond BTC/ETH or when looking for alternative opportunities. Discovers mid-cap and small-cap cryptocurrencies with sector rotation signals and momentum plays.",
            prompt=prompts["altcoin-researcher"],
            tools=[
                "mcp__polygon__polygon_crypto_snapshot_ticker",
                "mcp__polygon__polygon_crypto_aggregates",
                "mcp__polygon__polygon_crypto_gainers_losers",
                "mcp__polygon__polygon_crypto_rsi",
                "mcp__polygon__polygon_crypto_macd",
                "mcp__polygon__polygon_news",
                "mcp__polygon__polygon_ticker_details",
                "mcp__perplexity__perplexity_sonar",
                "mcp__perplexity__perplexity_sonar_pro",
                "mcp__perplexity__perplexity_sonar_reasoning",
                "mcp__binance__binance_get_orderbook",
                "mcp__binance__binance_get_recent_trades",
                "mcp__binance__binance_get_ticker",
                "mcp__binance__binance_get_price",
                "mcp__binance__binance_get_book_ticker",
                "mcp__ide__executeCode",
                "Read"
            ],
            model="sonnet"
        )

    # Market Intelligence - Web research specialist
    if "market-intelligence" in prompts:
        agents["market-intelligence"] = AgentDefinition(
            description="Market intelligence and research specialist. Use when you need comprehensive web research on macro trends, regulatory developments, institutional activity, or market sentiment that cannot be obtained from price data alone. Read-only analyst.",
            prompt=prompts["market-intelligence"],
            tools=[
                "mcp__perplexity__perplexity_sonar",
                "mcp__perplexity__perplexity_sonar_pro",
                "mcp__perplexity__perplexity_sonar_reasoning",
                "mcp__perplexity__perplexity_sonar_reasoning_pro",
                "mcp__perplexity__perplexity_sonar_deep_research",
                "mcp__polygon__polygon_news",
                "Read"
            ],
            model="sonnet"
        )

    # Technical Analyst - Pure chart analysis
    if "technical-analyst" in prompts:
        agents["technical-analyst"] = AgentDefinition(
            description="Pure technical analysis specialist. Use for multi-timeframe chart analysis, support/resistance levels, and technical indicators WITHOUT fundamental bias. Provides precise entry/exit levels.",
            prompt=prompts["technical-analyst"],
            tools=[
                "mcp__polygon__polygon_crypto_snapshot_ticker",
                "mcp__polygon__polygon_crypto_aggregates",
                "mcp__polygon__polygon_crypto_rsi",
                "mcp__polygon__polygon_crypto_macd",
                "mcp__polygon__polygon_crypto_ema",
                "mcp__polygon__polygon_crypto_sma",
                "mcp__binance__binance_get_orderbook",
                "mcp__binance__binance_get_recent_trades",
                "mcp__binance__binance_get_ticker",
                "mcp__ide__executeCode",
                "Read"
            ],
            model="sonnet"
        )

    # Risk Manager - Portfolio risk assessment
    if "risk-manager" in prompts:
        agents["risk-manager"] = AgentDefinition(
            description="Portfolio risk manager. Use BEFORE executing trades to validate position sizing and AFTER trades to assess portfolio health. Calculates risk metrics and ensures risk management compliance. Read-only analyst with no trading authority.",
            prompt=prompts["risk-manager"],
            tools=[
                "mcp__binance__binance_get_account",
                "mcp__binance__binance_get_open_orders",
                "mcp__binance__binance_spot_trade_history",
                "mcp__binance__binance_calculate_spot_pnl",
                "mcp__binance__trading_notes",
                "mcp__polygon__polygon_crypto_aggregates",
                "mcp__ide__executeCode",
                "Read"
            ],
            model="sonnet"
        )

    # Data Analyst - Python/pandas specialist
    if "data-analyst" in prompts:
        agents["data-analyst"] = AgentDefinition(
            description="Data analysis specialist. Use when you need rigorous quantitative analysis of CSV data from MCP tools. Expert in statistical analysis, pattern recognition, and data validation.",
            prompt=prompts["data-analyst"],
            tools=[
                "mcp__ide__executeCode",
                "Read"
            ],
            model="sonnet"
        )

    # Futures Analyst - Leverage and futures trading specialist
    if "futures-analyst" in prompts:
        agents["futures-analyst"] = AgentDefinition(
            description="Futures trading analyst. Use when considering leveraged positions or futures opportunities. Analyzes funding rates, liquidation risk, basis spreads, and recommends safe leverage levels. Emphasizes risk management for leveraged trading.",
            prompt=prompts["futures-analyst"],
            tools=[
                "mcp__binance__binance_get_ticker",
                "mcp__binance__binance_get_orderbook",
                "mcp__binance__binance_get_price",
                "mcp__binance__binance_get_account",
                "mcp__binance__binance_set_futures_leverage",
                "mcp__binance__binance_manage_futures_positions",
                "mcp__binance__binance_calculate_liquidation_risk",
                "mcp__polygon__polygon_crypto_snapshot_ticker",
                "mcp__polygon__polygon_crypto_aggregates",
                "mcp__ide__executeCode",
                "Read"
            ],
            model="sonnet"
        )

    return agents

async def main():
    """Trading Agent with full MCP tool access for market analysis and execution."""

    # Load system prompt
    with open("system_prompt.md", "r") as f:
        system_prompt = f.read()

    # Create subagent definitions
    print("=" * 80)
    print("Initializing Subagent Architecture...")
    print("=" * 80)
    subagents = create_subagent_definitions()
    print(f"✓ Loaded {len(subagents)} specialized subagents:")
    for agent_name in subagents.keys():
        print(f"  - {agent_name}")
    print("=" * 80 + "\n")

    # Configure options with all MCP tools and subagents
    options = ClaudeAgentOptions(
        # System prompt for conservative trading
        system_prompt=system_prompt,

        # Subagents for parallel analysis and specialized tasks
        agents=subagents,

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
            "mcp__binance__save_tool_notes",
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
            },
            "perplexity": {
                "type": "http",
                "url": "http://localhost:8011/perplexity/"
            }
        }
    )

    print("=" * 80)

    async with ClaudeSDKClient(options=options) as client:
        # Initial trading prompt
        with open("user_prompt.md", "r") as f:
            user_prompt = f.read()

        # Load entrance prompt (optional trigger for market check)
        with open("entrance.md", "r") as f:
            entrance_prompt = f.read()

        # Optionally append entrance prompt to trigger market action check
        # To enable: user_prompt = f"{user_prompt}\n\n{entrance_prompt}"
        # For now, entrance_prompt is available but not automatically appended

        # Add current UTC timestamp to the prompt
        current_utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        user_prompt_with_timestamp = f"Current UTC Time: {current_utc_time}\n\n{user_prompt}"

        await client.query(user_prompt_with_timestamp)
        turn_count = 1

        # Start tracking the first turn
        activity_tracker.start_turn(turn_count)

        # Process the initial response
        print(f"\n{'=' * 80}")
        print(f"[Turn {turn_count}] Agent Response")
        print(f"{'=' * 80}")

        # Wrap in telemetry trace
        with telemetry.trace_agent_turn(turn_count):
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ThinkingBlock):
                            display_thinking(block)
                        elif isinstance(block, TextBlock):
                            display_text(block)
                        elif isinstance(block, ToolUseBlock):
                            display_tool_use(block)
                        elif isinstance(block, ToolResultBlock):
                            display_tool_result(block)
                elif isinstance(message, SystemMessage):
                    display_system_message(message)
                elif isinstance(message, ResultMessage):
                    display_result(message)
                    # End the current turn when we receive the result
                    activity_tracker.end_turn()

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

                    # End session and generate report
                    activity_tracker.end_session()
                    report_path = SessionReporter.generate_and_save(activity_tracker)
                    print(f"\n📊 Session report saved to: {report_path}")

                    break

                elif user_input.lower() == 'interrupt':
                    await client.interrupt()
                    print("\n[Task interrupted!]\n")
                    continue

                # Send user's response to Claude with UTC timestamp
                turn_count += 1

                # Start tracking the new turn
                activity_tracker.start_turn(turn_count)

                current_utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                user_input_with_timestamp = f"Current UTC Time: {current_utc_time}\n\n{user_input}"
                await client.query(user_input_with_timestamp)

                # Process Claude's response
                print(f"\n{'=' * 80}")
                print(f"[Turn {turn_count}] Agent Response")
                print(f"{'=' * 80}")

                # Wrap in telemetry trace
                with telemetry.trace_agent_turn(turn_count):
                    async for message in client.receive_response():
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, ThinkingBlock):
                                    display_thinking(block)
                                elif isinstance(block, TextBlock):
                                    display_text(block)
                                elif isinstance(block, ToolUseBlock):
                                    display_tool_use(block)
                                elif isinstance(block, ToolResultBlock):
                                    display_tool_result(block)
                        elif isinstance(message, SystemMessage):
                            display_system_message(message)
                        elif isinstance(message, ResultMessage):
                            display_result(message)
                            # End the current turn when we receive the result
                            activity_tracker.end_turn()

                print()  # Add spacing after response

            except KeyboardInterrupt:
                print("\n\n" + "=" * 80)
                print("Trading session interrupted by user.")
                print("=" * 80)

                # End session and generate report
                activity_tracker.end_session()
                report_path = SessionReporter.generate_and_save(activity_tracker)
                print(f"\n📊 Session report saved to: {report_path}")

                break
            except EOFError:
                print("\n\n" + "=" * 80)
                print("Trading session ended.")
                print("=" * 80)

                # End session and generate report
                activity_tracker.end_session()
                report_path = SessionReporter.generate_and_save(activity_tracker)
                print(f"\n📊 Session report saved to: {report_path}")

                break

    # Final safety net: Ensure session report is generated
    if activity_tracker and not activity_tracker.end_time:
        activity_tracker.end_session()
        try:
            report_path = SessionReporter.generate_and_save(activity_tracker)
            print(f"\n📊 Session report saved to: {report_path}")
        except Exception as e:
            print(f"\n⚠️ Could not save session report: {e}")

    # Shutdown telemetry
    telemetry.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
