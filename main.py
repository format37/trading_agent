import asyncio
import aiohttp
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
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Import telemetry and activity tracking modules (optional)
# Check if telemetry is enabled via environment variable
ENABLE_TELEMETRY = os.getenv("ENABLE_TELEMETRY", "false").lower() in ["true", "1", "yes"]

if ENABLE_TELEMETRY:
    try:
        from telemetry import get_telemetry_manager
        from activity_tracker import AgentActivityTracker
        from session_reporter import SessionReporter
        from logger import setup_session_logging
        TELEMETRY_AVAILABLE = True
    except ImportError as e:
        print(f"⚠️  Telemetry imports failed: {e}")
        print("   Continuing without telemetry...")
        TELEMETRY_AVAILABLE = False
        ENABLE_TELEMETRY = False
else:
    TELEMETRY_AVAILABLE = False

# No-op telemetry classes when telemetry is disabled
if not TELEMETRY_AVAILABLE:
    class NoOpActivityTracker:
        """No-op activity tracker when telemetry is disabled."""
        def __init__(self):
            self.end_time = None

        def start_turn(self, turn_count):
            pass

        def end_turn(self):
            pass

        def end_session(self):
            pass

        def record_tool_call(self, tool_name, tool_id, tool_input):
            pass

        def record_tool_result(self, tool_id, result_summary, is_error):
            pass

    class NoOpTelemetryManager:
        """No-op telemetry manager when telemetry is disabled."""
        def __init__(self, *args, **kwargs):
            self.enabled = False

        def trace_agent_turn(self, turn_number):
            from contextlib import contextmanager
            @contextmanager
            def _noop():
                yield None
            return _noop()

        def trace_thinking(self, thinking_content):
            pass

        def trace_tool_use(self, tool_name, tool_id, tool_input):
            pass

        def trace_tool_result(self, tool_id, is_error, result_summary):
            pass

        def trace_response(self, response_text):
            pass

        def trace_session_result(self, result_data):
            pass

        def trace_system_message(self, subtype, data):
            pass

        def shutdown(self):
            pass

    class NoOpSessionReporter:
        """No-op session reporter when telemetry is disabled."""
        @staticmethod
        def generate_and_save(activity_tracker):
            return "session_report_disabled.md"

    class NoOpSessionLogger:
        """No-op session logger when telemetry is disabled."""
        def get_log_path(self):
            return "logging_disabled.log"

        def close(self):
            pass

    AgentActivityTracker = NoOpActivityTracker
    SessionReporter = NoOpSessionReporter

    def get_telemetry_manager(*args, **kwargs):
        return NoOpTelemetryManager()

    def setup_session_logging():
        return NoOpSessionLogger()

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

    # Check for MCP server failures in system message data
    if sys_msg.data and "mcp_servers" in sys_msg.data:
        mcp_servers = sys_msg.data["mcp_servers"]
        failed_servers = []

        # Check each MCP server status
        for server_info in mcp_servers:
            if isinstance(server_info, dict):
                server_name = server_info.get("name", "unknown")
                server_status = server_info.get("status", "unknown")

                if server_status == "failed":
                    failed_servers.append(server_name)

        # If any MCP server failed, exit immediately
        if failed_servers:
            print(f"\n{'=' * 80}")
            print(f"❌ CRITICAL ERROR: MCP Server(s) Failed to Initialize")
            print(f"{'=' * 80}")
            print(f"Failed servers: {', '.join(failed_servers)}")
            print(f"\nThe trading agent requires all MCP servers to function properly.")
            print(f"Please verify:")
            print(f"  1. MCP servers are running and accessible")
            print(f"  2. Environment variables are configured correctly:")
            for server_name in failed_servers:
                env_var = f"{server_name.upper()}_URL"
                url = os.getenv(env_var, "NOT SET")
                print(f"     - {env_var}: {url}")
            print(f"  3. Docker network connectivity exists (network: mcp-shared)")
            print(f"  4. Authentication is configured (if required)")
            print(f"\nTroubleshooting steps:")
            print(f"  - Check if MCP server containers are running: docker ps")
            print(f"  - Check MCP server logs: docker logs <mcp-server-container>")
            print(f"  - Verify network connectivity: docker network inspect mcp-shared")
            print(f"  - Test MCP server health: curl <MCP_SERVER_URL>/health")
            print(f"{'=' * 80}\n")

            # Exit immediately - cannot proceed without MCP servers
            print(f"❌ Exiting due to MCP server failures.\n")
            sys.exit(1)

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

    # Note: result.result contains the agent's final response text, which has already
    # been displayed by display_text() when the TextBlock was received earlier.
    # Printing it here would duplicate the output, so we skip it.
    # if result.result:
    #     print(f"\nResult: {result.result}")

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
                "mcp__binance__binance_py_eval",
                "mcp__binance__binance_save_tool_notes",
                "mcp__binance__binance_read_tool_notes",
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
                "mcp__binance__binance_py_eval",
                "mcp__binance__binance_save_tool_notes",
                "mcp__binance__binance_read_tool_notes",
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
                "mcp__binance__binance_py_eval",
                "mcp__binance__binance_save_tool_notes",
                "mcp__binance__binance_read_tool_notes",
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
                "mcp__binance__binance_get_historical_klines",
                "mcp__binance__binance_py_eval",
                "mcp__binance__binance_save_tool_notes",
                "mcp__binance__binance_read_tool_notes",
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
                "mcp__binance__binance_get_deposit_history",
                "mcp__binance__binance_get_withdrawal_history",
                "mcp__binance__binance_get_p2p_history",
                "mcp__binance__binance_calculate_spot_pnl",
                "mcp__binance__binance_portfolio_performance",
                "mcp__binance__trading_notes",
                "mcp__binance__binance_py_eval",
                "mcp__binance__binance_save_tool_notes",
                "mcp__binance__binance_read_tool_notes",
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
                "mcp__binance__binance_get_historical_klines",
                "mcp__binance__binance_portfolio_performance",
                "mcp__binance__binance_py_eval",
                "mcp__binance__binance_save_tool_notes",
                "mcp__binance__binance_read_tool_notes",
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
                "mcp__binance__binance_get_futures_balances",
                "mcp__binance__binance_trade_futures_market",
                "mcp__binance__binance_futures_limit_order",
                "mcp__binance__binance_get_futures_open_orders",
                "mcp__binance__binance_cancel_futures_order",
                "mcp__binance__binance_get_futures_trade_history",
                "mcp__binance__binance_set_futures_leverage",
                "mcp__binance__binance_manage_futures_positions",
                "mcp__binance__binance_calculate_liquidation_risk",
                "mcp__binance__binance_py_eval",
                "mcp__binance__binance_save_tool_notes",
                "mcp__binance__binance_read_tool_notes",
                "mcp__polygon__polygon_crypto_snapshot_ticker",
                "mcp__polygon__polygon_crypto_aggregates",
                "mcp__ide__executeCode",
                "Read"
            ],
            model="sonnet"
        )

    return agents

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Trading Agent - Event-driven cryptocurrency trading with Claude SDK"
    )
    parser.add_argument(
        "--event-file",
        type=str,
        help="Path to JSON file containing event data to trigger analysis"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode (multi-turn conversation)"
    )
    return parser.parse_args()

def load_event_data(event_file_path: str) -> dict:
    """
    Load event data from JSON file.

    Args:
        event_file_path: Path to event JSON file

    Returns:
        Event data dictionary
    """
    try:
        with open(event_file_path, 'r') as f:
            event_data = json.load(f)
        print(f"✓ Loaded event data from: {event_file_path}")
        return event_data
    except FileNotFoundError:
        print(f"❌ Error: Event file not found: {event_file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in event file: {e}")
        sys.exit(1)

def format_event_prompt(event_data: dict) -> str:
    """
    Format event data into a prompt string.

    Args:
        event_data: Event data dictionary

    Returns:
        Formatted event prompt
    """
    if not event_data:
        return ""

    lines = ["## Event Alert", ""]

    # Format event type
    if "type" in event_data:
        lines.append(f"**Event Type**: {event_data['type']}")

    # Format message
    if "message" in event_data:
        lines.append(f"**Message**: {event_data['message']}")

    # Format additional fields
    for key, value in event_data.items():
        if key not in ["type", "message"]:
            formatted_key = key.replace("_", " ").title()
            lines.append(f"**{formatted_key}**: {value}")

    lines.append("")
    lines.append("Please analyze this event and take appropriate trading action if warranted.")

    return "\n".join(lines)

async def verify_mcp_connectivity():
    """
    Verify MCP servers are accessible before starting the agent.
    This is an optional pre-flight check controlled by STRICT_MCP_CHECK env var.

    Returns:
        bool: True if all MCP servers are accessible, False otherwise
    """
    servers = {
        "Polygon": os.getenv("POLYGON_URL", "http://localhost:8009/polygon/"),
        "Binance": os.getenv("BINANCE_URL", "http://localhost:8010/binance/"),
        "Perplexity": os.getenv("PERPLEXITY_URL", "http://localhost:8011/perplexity/")
    }

    print("=" * 80)
    print("Verifying MCP Server Connectivity...")
    print("=" * 80)

    all_ok = True
    for name, url in servers.items():
        try:
            # Build health check URL (try both base URL and /health endpoint)
            base_url = url.rstrip('/')

            # Try to connect with a simple GET request
            async with aiohttp.ClientSession() as session:
                # First try the base URL
                try:
                    async with session.get(base_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status in [200, 404]:  # 404 is ok - server is responsive
                            print(f"✓ {name}: OK ({url})")
                        else:
                            print(f"✗ {name}: HTTP {response.status} ({url})")
                            all_ok = False
                except Exception:
                    # If base URL fails, try /health endpoint
                    health_url = f"{base_url}/health"
                    async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status == 200:
                            print(f"✓ {name}: OK ({url})")
                        else:
                            print(f"✗ {name}: HTTP {response.status} ({url})")
                            all_ok = False
        except asyncio.TimeoutError:
            print(f"✗ {name}: Connection timeout ({url})")
            all_ok = False
        except aiohttp.ClientConnectorError as e:
            print(f"✗ {name}: Cannot connect - {e} ({url})")
            all_ok = False
        except Exception as e:
            print(f"✗ {name}: {type(e).__name__}: {e} ({url})")
            all_ok = False

    print("=" * 80)

    if not all_ok:
        print("\n⚠️  MCP Server connectivity check FAILED")
        print("   Some MCP servers are unreachable. Please verify:")
        print("   1. MCP servers are running and accessible")
        print("   2. Docker network configuration is correct (network: mcp-shared)")
        print("   3. Environment variables are set correctly:")
        for name, url in servers.items():
            print(f"      - {name.upper()}_URL: {url}")
        print("   4. Firewall/network rules allow connections")
        print("\n   The trading agent may not function correctly without these services.")

        # Check if we should fail fast
        strict_check = os.getenv("STRICT_MCP_CHECK", "false").lower() in ["true", "1", "yes"]
        if strict_check:
            print("\n   STRICT_MCP_CHECK=true - Exiting immediately.\n")
            sys.exit(1)
        else:
            print("\n   STRICT_MCP_CHECK=false - Continuing anyway (may fail later).\n")

        return False

    print("✓ All MCP servers are accessible\n")
    return True

async def main():
    """Trading Agent with full MCP tool access for market analysis and execution."""

    # Parse command-line arguments
    args = parse_arguments()

    # Verify MCP connectivity (optional pre-flight check)
    await verify_mcp_connectivity()

    # Setup session logging
    session_logger = setup_session_logging()
    if TELEMETRY_AVAILABLE:
        print(f"📝 Logging to: {session_logger.get_log_path()}\n")
    else:
        print(f"📝 Telemetry disabled - running without session logging\n")

    # Variables to collect trading data for API response
    agent_text_responses = []  # Collect all TextBlock responses
    binance_notes_content = []  # Collect binance_trading_notes tool outputs
    trading_tool_calls = []  # Collect trading-specific tool calls

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
            "mcp__binance__binance_get_deposit_history",
            "mcp__binance__binance_get_withdrawal_history",
            "mcp__binance__binance_get_p2p_history",
            "mcp__binance__binance_get_historical_klines",

            # Binance MCP - Spot Trading
            "mcp__binance__binance_spot_market_order",
            "mcp__binance__binance_spot_limit_order",
            "mcp__binance__binance_spot_oco_order",
            "mcp__binance__binance_cancel_order",

            # Binance MCP - Futures Trading
            "mcp__binance__binance_get_futures_balances",
            "mcp__binance__binance_trade_futures_market",
            "mcp__binance__binance_futures_limit_order",
            "mcp__binance__binance_get_futures_open_orders",
            "mcp__binance__binance_cancel_futures_order",
            "mcp__binance__binance_get_futures_trade_history",
            "mcp__binance__binance_set_futures_leverage",
            "mcp__binance__binance_manage_futures_positions",
            "mcp__binance__binance_calculate_liquidation_risk",

            # Binance MCP - Analysis & Risk Management
            "mcp__binance__binance_calculate_spot_pnl",
            "mcp__binance__binance_portfolio_performance",
            "mcp__binance__binance_trading_notes",

            # Binance MCP - Tool Management
            "mcp__binance__binance_py_eval",
            "mcp__binance__binance_read_tool_notes",
            "mcp__binance__binance_save_tool_notes",
        ],

        permission_mode="bypassPermissions",  # Full permissions - no prompts
        cwd=os.getcwd(),

        # MCP Server connections (read from environment for Docker compatibility)
        mcp_servers={
            "polygon": {
                "type": "http",
                "url": os.getenv("POLYGON_URL", "http://localhost:8009/polygon/")
            },
            "binance": {
                "type": "http",
                "url": os.getenv("BINANCE_URL", "http://localhost:8010/binance/")
            },
            "perplexity": {
                "type": "http",
                "url": os.getenv("PERPLEXITY_URL", "http://localhost:8011/perplexity/")
            }
        }
    )

    print("=" * 80)

    # Determine execution mode
    interactive_mode = args.interactive

    # Variable to track exit code (0=success, 1=error, 2=no action)
    exit_code = 0

    try:
        async with ClaudeSDKClient(options=options) as client:
            # Initial trading prompt
            with open("user_prompt.md", "r") as f:
                user_prompt = f.read()

            # Load entrance prompt (optional trigger for market check)
            with open("entrance.md", "r") as f:
                entrance_prompt = f.read()
                user_prompt = f"{user_prompt}\n\n{entrance_prompt}"

            # Load and append event data if provided
            if args.event_file:
                event_data = load_event_data(args.event_file)
                event_prompt = format_event_prompt(event_data)
                user_prompt = f"{user_prompt}\n\n{event_prompt}"
                print(f"📢 Event-driven mode: Processing event from {args.event_file}\n")
            elif not interactive_mode:
                print("ℹ️  Single-turn mode: No event file provided, running standard analysis\n")

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
                                # Capture agent's text response for API
                                agent_text_responses.append(block.text)
                            elif isinstance(block, ToolUseBlock):
                                display_tool_use(block)
                            elif isinstance(block, ToolResultBlock):
                                display_tool_result(block)
                                # Capture binance_trading_notes results
                                if hasattr(block, 'tool_use_id'):
                                    # Find the corresponding tool call
                                    for turn in activity_tracker.turns:
                                        for tool_call in turn.tool_calls:
                                            if tool_call.tool_id == block.tool_use_id and tool_call.tool_name == "mcp__binance__binance_trading_notes":
                                                if not block.is_error and block.content:
                                                    binance_notes_content.append(str(block.content))
                    elif isinstance(message, SystemMessage):
                        display_system_message(message)
                    elif isinstance(message, ResultMessage):
                        display_result(message)
                        # End the current turn when we receive the result
                        activity_tracker.end_turn()

            # Interactive or single-turn mode
            if interactive_mode:
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
                                            # Capture agent's text response for API
                                            agent_text_responses.append(block.text)
                                        elif isinstance(block, ToolUseBlock):
                                            display_tool_use(block)
                                        elif isinstance(block, ToolResultBlock):
                                            display_tool_result(block)
                                            # Capture binance_trading_notes results
                                            if hasattr(block, 'tool_use_id'):
                                                # Find the corresponding tool call
                                                for turn in activity_tracker.turns:
                                                    for tool_call in turn.tool_calls:
                                                        if tool_call.tool_id == block.tool_use_id and tool_call.tool_name == "mcp__binance__binance_trading_notes":
                                                            if not block.is_error and block.content:
                                                                binance_notes_content.append(str(block.content))
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
                        exit_code = 1
                        break
                    except EOFError:
                        print("\n\n" + "=" * 80)
                        print("Trading session ended.")
                        print("=" * 80)
                        break
            else:
                # Single-turn mode: Process response and exit
                print("\n📍 Single-turn mode: Processing agent response...\n")

    except Exception as e:
        print(f"\n❌ Error during agent execution: {e}")
        import traceback
        traceback.print_exc()
        exit_code = 1

    # Generate session report
    print("\n" + "=" * 80)
    print("Finalizing session...")
    print("=" * 80)

    if activity_tracker and not activity_tracker.end_time:
        activity_tracker.end_session()

    # Collect trading actions from activity tracker using helper method
    trading_actions = activity_tracker.get_trading_actions() if hasattr(activity_tracker, 'get_trading_actions') else []

    # Compile trading notes from agent responses and binance_trading_notes tool
    trading_notes_combined = ""
    if agent_text_responses:
        trading_notes_combined = "\n\n".join(agent_text_responses)
    if binance_notes_content:
        if trading_notes_combined:
            trading_notes_combined += "\n\n## Trading Notes from Binance Tool:\n" + "\n".join(binance_notes_content)
        else:
            trading_notes_combined = "\n".join(binance_notes_content)

    session_report_path = None
    if TELEMETRY_AVAILABLE:
        try:
            report_path = SessionReporter.generate_and_save(activity_tracker)
            session_report_path = str(report_path)
            print(f"📊 Session report saved to: {report_path}")
        except Exception as e:
            print(f"⚠️ Could not save session report: {e}")
            exit_code = 1

        # Shutdown telemetry
        telemetry.shutdown()

        # Close logger
        session_logger.close()
    else:
        print("📊 Telemetry disabled - no session report generated")

    # Print exit message
    print("\n" + "=" * 80)
    if exit_code == 0:
        print("✅ Trading session completed successfully")
    elif exit_code == 1:
        print("❌ Trading session completed with errors")
    elif exit_code == 2:
        print("ℹ️  Trading session completed - no action taken")
    print("=" * 80 + "\n")

    # Return structured data instead of sys.exit() for API usage
    return {
        "exit_code": exit_code,
        "trading_notes": trading_notes_combined,
        "actions": trading_actions,
        "session_report_path": session_report_path
    }

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        # When running directly (not via API), exit with the exit code
        if result and isinstance(result, dict):
            sys.exit(result.get("exit_code", 0))
        else:
            sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
