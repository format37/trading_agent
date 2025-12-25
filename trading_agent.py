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
from typing import Optional, List, Dict, Any
import re
import uuid

from models import (
    AgentExecutionReport,
    TradingSessionResume,
    MCPToolsReport,
    TradingAction,
    WorkflowResults,
    WorkflowPhaseResult
)

# Load environment variables from .env file
load_dotenv()

def load_config() -> dict:
    """Load model configuration from config.json."""
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: config.json not found, using defaults")
        return {"model": {"name": "sonnet", "effort": ""}}


def parse_reporter_output(agent_text_responses: List[str]) -> MCPToolsReport:
    """
    Parse the reporter agent's output to extract MCP report data.

    Strategy 1: Look for structured JSON block (preferred)
    Strategy 2: Fall back to regex parsing for legacy format
    """
    report = MCPToolsReport()

    for response in agent_text_responses:
        # Strategy 1: Look for structured JSON block
        json_match = re.search(r'```json\s*(\{[^`]+\})\s*```', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                report.csv_path = data.get("csv_path")
                report.total_tool_calls = data.get("total_tool_calls", 0)
                report.unique_requesters = data.get("unique_requesters", 0)
                report.unique_tools = data.get("unique_tools", 0)
                report.calls_by_requester = data.get("calls_by_requester", {})
                report.calls_by_server = data.get("calls_by_server", {})
                report.top_tools = data.get("top_tools", [])
                return report  # Found structured data, return immediately
            except json.JSONDecodeError:
                pass  # Fall through to regex parsing

        # Strategy 2: Fallback regex parsing for text format
        # Trigger on various report headers/indicators
        if ("TOOL USAGE REPORT" in response or "Tool Usage" in response or
            "session_report_" in response or "SESSION SUMMARY" in response or
            "MCP Tool Calls" in response or "TOOL CALLS BY REQUESTER" in response):

            # Parse Total MCP Tool Calls (handle various formats)
            # Matches: "Total MCP Tool Calls: 48" or "TOTAL TOOL CALLS: 48"
            match = re.search(r'Total\s+(?:MCP\s+)?Tool\s+Calls[:\s]+(\d+)', response, re.IGNORECASE)
            if match:
                report.total_tool_calls = int(match.group(1))

            # Parse calls by requester from "TOOL CALLS BY REQUESTER" section
            # Matches format: "- news-analyst: 13 calls (27.1%)"
            requester_section = re.search(
                r'TOOL\s+CALLS\s+BY\s+REQUESTER[:\s]*\n((?:\s*-?\s*[\w-]+[:\s]+\d+\s+calls?[^\n]*\n?)+)',
                response, re.IGNORECASE
            )
            if requester_section:
                requester_lines = requester_section.group(1).strip().split('\n')
                for line in requester_lines:
                    # Match: "- news-analyst: 13 calls (27.1%)" or "news-analyst 13 calls"
                    match = re.match(r'\s*-?\s*([\w-]+)[:\s]+(\d+)\s+calls?', line.strip())
                    if match:
                        requester = match.group(1)
                        calls = int(match.group(2))
                        report.calls_by_requester[requester] = calls

            if report.calls_by_requester:
                report.unique_requesters = len(report.calls_by_requester)

            # Parse calls by server from "TOOL CALLS BY MCP SERVER" section
            # Matches format: "- Binance MCP: 24 calls (50.0%)"
            server_section = re.search(
                r'TOOL\s+CALLS\s+BY\s+(?:MCP\s+)?SERVER[:\s]*\n((?:\s*-?\s*[\w\s-]+[:\s]+\d+\s+calls?[^\n]*\n?)+)',
                response, re.IGNORECASE
            )
            if server_section:
                server_lines = server_section.group(1).strip().split('\n')
                for line in server_lines:
                    # Match: "- Binance MCP: 24 calls (50.0%)"
                    match = re.match(r'\s*-?\s*([\w\s-]+?)\s*(?:MCP)?[:\s]+(\d+)\s+calls?', line.strip())
                    if match:
                        server_name = match.group(1).strip().lower().replace(' mcp', '').replace('mcp', '')
                        # Normalize server names
                        if 'binance' in server_name:
                            server_name = 'binance'
                        elif 'polygon' in server_name:
                            server_name = 'polygon'
                        elif 'perplexity' in server_name:
                            server_name = 'perplexity'
                        calls = int(match.group(2))
                        report.calls_by_server[server_name] = calls

            # Parse top tools from "TOP TOOLS USED" section (if present)
            top_tools_section = re.search(
                r'TOP\s+TOOLS\s+(?:USED)?[:\s]*\n((?:\s*-?\s*[\w_-]+[:\s]+\d+\s+calls?[^\n]*\n?)+)',
                response, re.IGNORECASE
            )
            if top_tools_section:
                tool_lines = top_tools_section.group(1).strip().split('\n')
                for line in tool_lines:
                    match = re.match(r'\s*-?\s*([\w_-]+)[:\s]+(\d+)\s+calls?', line.strip())
                    if match:
                        tool_name = match.group(1)
                        calls = int(match.group(2))
                        report.top_tools.append({"name": tool_name, "calls": calls})

            if report.top_tools:
                report.unique_tools = len(set(t["name"] for t in report.top_tools))

            # Extract CSV path
            csv_match = re.search(r'([\w/\-\.]+session_report_[\w\-\.]+\.csv)', response)
            if csv_match:
                report.csv_path = csv_match.group(1)

    return report


def extract_trading_actions(agent_text_responses: List[str]) -> List[TradingAction]:
    """
    Extract trading actions from agent responses.

    Looks for trading tool calls and their results in the text responses.
    """
    trading_actions = []
    trading_tool_patterns = [
        "binance_spot_market_order",
        "binance_spot_limit_order",
        "binance_spot_oco_order",
        "binance_cancel_order",
        "binance_trade_futures_market",
        "binance_futures_limit_order",
        "binance_cancel_futures_order"
    ]

    for response in agent_text_responses:
        for pattern in trading_tool_patterns:
            if pattern in response:
                # Extract basic info about the trade
                action = TradingAction(
                    action_type=pattern,
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                trading_actions.append(action)

    return trading_actions


def extract_subagents_used(agent_text_responses: List[str]) -> List[str]:
    """Extract list of subagents that were used during the session."""
    subagent_names = [
        "news-analyst", "market-intelligence", "technical-analyst",
        "risk-manager", "data-analyst", "futures-analyst", "trader", "reporter"
    ]
    used = set()

    for response in agent_text_responses:
        for name in subagent_names:
            if name in response.lower():
                used.add(name)

    return sorted(list(used))


def extract_key_decisions(agent_text_responses: List[str]) -> List[str]:
    """
    Extract key trading decisions from agent responses.

    Looks for patterns like:
    - "VERDICT: CONTINUE FREEZE"
    - "Decision: REBALANCE"
    - "STRONGLY AGREE with 95% confidence"
    """
    decisions = []

    for response in agent_text_responses:
        # Pattern 1: VERDICT lines (most common format)
        verdict_match = re.search(r'\*\*VERDICT:\s*(.+?)\*\*', response)
        if verdict_match:
            verdict = verdict_match.group(1).strip()
            # Clean up emoji and extra formatting
            verdict = re.sub(r'\s*[✅❌🎯⚡]\s*', '', verdict).strip()
            if verdict and verdict not in decisions:
                decisions.append(verdict)

        # Pattern 2: Plain VERDICT without markdown
        verdict_plain = re.search(r'VERDICT:\s*([A-Z][A-Z\s]+?)(?:\s*[✅❌]|\n|$)', response)
        if verdict_plain:
            verdict = verdict_plain.group(1).strip()
            if verdict and verdict not in decisions:
                decisions.append(verdict)

        # Pattern 3: APPROVE/REJECT from risk-manager
        approve_match = re.search(r'\*\*(?:VERDICT|Status)\*\*:\s*(APPROVE|REJECT|APPROVE WITH CONDITIONS)', response, re.IGNORECASE)
        if approve_match:
            decision = approve_match.group(1).strip().upper()
            if decision and decision not in decisions:
                decisions.append(decision)

        # Pattern 4: STRONGLY AGREE/DISAGREE from critic
        agree_match = re.search(r'STRONGLY\s+(AGREE|DISAGREE)(?:[^\d]*(\d+%)[^c]*confidence)?', response, re.IGNORECASE)
        if agree_match:
            decision = f"STRONGLY {agree_match.group(1).upper()}"
            if agree_match.group(2):
                decision += f" ({agree_match.group(2)} confidence)"
            if decision not in decisions:
                decisions.append(decision)

    return decisions[:5]  # Limit to top 5 decisions


def extract_workflow_results(agent_text_responses: List[str]) -> WorkflowResults:
    """
    Extract 5-phase workflow results from agent responses.

    Parses markdown tables in two formats:
    1. Phase-based: | **0** | News Analyst | Balanced sentiment | - |
    2. Consensus Matrix: | **market-intelligence** | HOLD | HOLD | 10/10 | rationale |
    """
    workflow = WorkflowResults()
    seen_agents = set()  # Track already-added agents to avoid duplicates

    # Map subagent names to phase numbers
    subagent_phases = {
        'news-analyst': 0,
        'market-intelligence': 1,
        'technical-analyst': 2,
        'risk-manager': 2,
        'data-analyst': 2,
        'futures-analyst': 2,
        'btc-researcher': 2,
        'eth-researcher': 2,
        'altcoin-researcher': 2,
        'critic': 3,
        'trader': 4,
        'reporter': 5
    }

    for response in agent_text_responses:
        # Look for workflow results or consensus matrix sections
        if ("5-Phase Workflow Results" in response or "Workflow Results" in response or
            "Consensus Matrix" in response or "Subagent Consensus" in response or
            "Consensus Analysis" in response):

            # Strategy 1: Parse phase-based table (legacy format)
            # Pattern: | **0** | News Analyst | Balanced sentiment | - |
            phase_pattern = r'\|\s*\*?\*?(\d+)\*?\*?\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|'
            phase_matches = re.findall(phase_pattern, response)

            for match in phase_matches:
                phase_num = int(match[0])
                agent = match[1].strip()
                recommendation = match[2].strip()
                confidence = match[3].strip()

                # Skip header row or separator rows
                if agent.lower() in ['agent', '------', '---', '']:
                    continue
                if 'phase' in agent.lower():
                    continue

                # Skip if we already have this agent
                if agent.lower() in seen_agents:
                    continue
                seen_agents.add(agent.lower())

                phase_result = WorkflowPhaseResult(
                    phase=phase_num,
                    agent=agent,
                    recommendation=recommendation,
                    confidence=confidence if confidence != '-' else None
                )
                workflow.phases.append(phase_result)

            # Strategy 2: Parse consensus matrix (subagent-based format)
            # Pattern: | **market-intelligence** | HOLD (Freeze) | HOLD | 10/10 | rationale |
            # 5-column format: Subagent | Recommendation | Direction | Confidence | Key Rationale
            consensus_pattern = r'\|\s*\*?\*?([\w-]+)\*?\*?\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]*)\s*\|'
            consensus_matches = re.findall(consensus_pattern, response)

            for match in consensus_matches:
                subagent = match[0].strip().lower()
                recommendation = match[1].strip()
                direction = match[2].strip()
                confidence = match[3].strip()
                rationale = match[4].strip() if len(match) > 4 else None

                # Skip header row or separator rows
                if subagent in ['subagent', '------', '---', '', 'agent']:
                    continue
                if 'subagent' in subagent or '---' in subagent:
                    continue

                # Only accept known subagent names (avoid matching other tables)
                if subagent not in subagent_phases:
                    continue

                # Skip if we already have this agent
                if subagent in seen_agents:
                    continue
                seen_agents.add(subagent)

                # Get phase number from subagent name
                phase_num = subagent_phases.get(subagent, 2)

                phase_result = WorkflowPhaseResult(
                    phase=phase_num,
                    agent=subagent,
                    recommendation=recommendation,
                    confidence=confidence if confidence not in ['-', ''] else None,
                    details=f"Direction: {direction}" + (f" | {rationale}" if rationale else "")
                )
                workflow.phases.append(phase_result)

        # Extract final verdict from multiple patterns
        # Pattern 1: "VERDICT: CONTINUE FREEZE"
        verdict_match = re.search(r'VERDICT:\s*([A-Z][A-Z\s]+?)(?:\s*[✅❌]|\n|$)', response)
        if verdict_match and not workflow.verdict:
            workflow.verdict = verdict_match.group(1).strip()

        # Pattern 2: "**Action:** [APPROVE / REJECT]" from risk-manager
        action_match = re.search(r'\*\*Action:\*\*\s*(APPROVE|REJECT)', response, re.IGNORECASE)
        if action_match and not workflow.verdict:
            workflow.verdict = action_match.group(1).strip().upper()

        # Pattern 3: "Decision: NO TRADE TODAY" or similar
        decision_match = re.search(r'Decision:\s*([A-Z][A-Z\s]+?)(?:\n|$)', response)
        if decision_match and not workflow.verdict:
            workflow.verdict = decision_match.group(1).strip()

        # Pattern 4: Risk manager REJECT with VETO
        if '**REJECT**' in response or 'VETO INVOKED' in response:
            if not workflow.verdict:
                workflow.verdict = 'REJECT (VETO)'

        # Pattern 5: Consensus result
        consensus_result = re.search(r'Consensus\s+Result:\s*([^\n]+)', response, re.IGNORECASE)
        if consensus_result and not workflow.verdict:
            workflow.verdict = consensus_result.group(1).strip()

        # Extract rationale (numbered list after "Rationale:")
        rationale_match = re.search(r'\*\*Rationale:\*\*\s*\n((?:\d+\..+\n?)+)', response)
        if rationale_match:
            rationale_text = rationale_match.group(1)
            rationale_items = re.findall(r'\d+\.\s*(.+)', rationale_text)
            workflow.rationale = [item.strip() for item in rationale_items]

        # Alternative: Extract from "Why NOT Trade Today" section
        why_not_match = re.search(r'Why\s+NOT\s+Trade\s+Today[^\n]*\n((?:\d+\..+\n?)+)', response, re.IGNORECASE)
        if why_not_match and not workflow.rationale:
            rationale_text = why_not_match.group(1)
            rationale_items = re.findall(r'\d+\.\s*(.+)', rationale_text)
            workflow.rationale = [item.strip() for item in rationale_items]

    return workflow


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

def display_tool_use(tool_block: ToolUseBlock):
    """Display tool usage with inputs."""
    print(f"\n[{format_timestamp()}] 🔧 TOOL USE: {tool_block.name}")
    print(f"  ID: {tool_block.id}")
    print(f"  Input:")
    # Pretty print the input
    input_json = json.dumps(tool_block.input, indent=4)
    for line in input_json.split('\n'):
        print(f"    {line}")

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

def display_text(text_block: TextBlock):
    """Display text content from agent."""
    print(f"\n[{format_timestamp()}] 💬 RESPONSE:")
    print(text_block.text)

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

def load_subagent_prompts():
    """Load all subagent prompts from the prompts directory."""
    prompts_dir = os.path.join(os.path.dirname(__file__), "prompts")

    # Load each subagent prompt
    subagent_files = {
        "news-analyst": "news_analyst.md",
        "market-intelligence": "market_intelligence.md",
        "technical-analyst": "technical_analyst.md",
        "risk-manager": "risk_manager.md",
        "data-analyst": "data_analyst.md",
        "futures-analyst": "futures_analyst.md",
        "trader": "trader.md",
        "reporter": "reporter.md"
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

def create_subagent_definitions(config: dict):
    """Create AgentDefinition objects for all subagents."""
    # Load prompts
    prompts = load_subagent_prompts()

    # Inject session start time and current UTC timestamp into each subagent prompt
    # Session start time is used by reporter to query request logs
    session_start_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    current_utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    prompts = {
        name: f"Session Start Time: {session_start_time}\nCurrent UTC Time: {current_utc_time}\n\n{prompt}"
        for name, prompt in prompts.items()
    }

    # Get model name from config
    model_name = config.get("model", {}).get("name", "sonnet")

    # Define agents with their configurations
    agents = {}

    # News Analyst - Phase 0: Runs FIRST, comprehensive market data collection with ALL Polygon tools
    if "news-analyst" in prompts:
        agents["news-analyst"] = AgentDefinition(
            description="News analyst. MUST be called FIRST (Phase 0) in every session. Collects comprehensive market data from ALL 22 Polygon tools. Generates structured CSVs for news, indicators, snapshots, and movers.",
            prompt=prompts["news-analyst"],
            tools=[
                # Polygon - News & Reference Data
                "mcp__polygon__polygon_news",
                "mcp__polygon__polygon_ticker_details",
                "mcp__polygon__polygon_market_holidays",
                "mcp__polygon__polygon_market_status",
                # Polygon - Real-Time Price Data
                "mcp__polygon__polygon_crypto_last_trade",
                "mcp__polygon__polygon_crypto_snapshot_ticker",
                "mcp__polygon__polygon_crypto_snapshot_book",
                "mcp__polygon__polygon_crypto_snapshots",
                "mcp__polygon__polygon_crypto_gainers_losers",
                # Polygon - Historical OHLCV Data
                "mcp__polygon__polygon_crypto_aggregates",
                "mcp__polygon__polygon_crypto_previous_close",
                "mcp__polygon__polygon_crypto_daily_open_close",
                "mcp__polygon__polygon_crypto_grouped_daily",
                "mcp__polygon__polygon_crypto_trades",
                "mcp__polygon__polygon_price_data",
                # Polygon - Technical Indicators
                "mcp__polygon__polygon_crypto_rsi",
                "mcp__polygon__polygon_crypto_ema",
                "mcp__polygon__polygon_crypto_macd",
                "mcp__polygon__polygon_crypto_sma",
                # Polygon - Reference Data
                "mcp__polygon__polygon_crypto_tickers",
                "mcp__polygon__polygon_crypto_exchanges",
                "mcp__polygon__polygon_crypto_conditions",
                # Portfolio context
                "mcp__binance__binance_get_account",
                "mcp__binance__binance_portfolio_performance",
                "mcp__binance__binance_get_ticker",
                "mcp__binance__binance_get_price",
                "mcp__binance__binance_py_eval",
                "mcp__ide__executeCode",
                "Read"
            ],
            model=model_name
        )

    # Market Intelligence - Phase 1: Runs SECOND (after news-analyst), provides sentiment context
    if "market-intelligence" in prompts:
        agents["market-intelligence"] = AgentDefinition(
            description="Market intelligence analyst. Runs SECOND (Phase 1) after news-analyst. Uses news-analyst CSV output for sentiment analysis. Detects FOMO/FUD extremes and gathers portfolio context for other subagents.",
            prompt=prompts["market-intelligence"],
            tools=[
                # Perplexity tools for sentiment research
                "mcp__perplexity__perplexity_sonar",
                "mcp__perplexity__perplexity_sonar_pro",
                "mcp__perplexity__perplexity_sonar_reasoning",
                "mcp__perplexity__perplexity_sonar_reasoning_pro",
                "mcp__perplexity__perplexity_sonar_deep_research",
                # Phase 1 context gathering - portfolio and notes (NO polygon_news - uses news-analyst CSV)
                "mcp__binance__binance_get_account",
                "mcp__binance__binance_trading_notes",
                "mcp__binance__binance_portfolio_performance",
                "mcp__binance__binance_get_ticker",
                "mcp__binance__binance_get_price",
                "mcp__binance__binance_py_eval",
                "mcp__ide__executeCode",
                "Read"
            ],
            model=model_name
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
            model=model_name
        )

    # Risk Manager - Portfolio risk assessment with VETO POWER
    if "risk-manager" in prompts:
        agents["risk-manager"] = AgentDefinition(
            description="Portfolio risk manager with VETO POWER. REQUIRED for all trading decisions. Issues APPROVE or REJECT verdict - REJECT overrides all other consensus. Validates position sizing and portfolio health. Read-only analyst with no trading authority.",
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
            model=model_name
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
            model=model_name
        )

    # Futures Analyst - Phase 2: Futures data analysis and recommendations (NO trading authority)
    if "futures-analyst" in prompts:
        agents["futures-analyst"] = AgentDefinition(
            description="Futures market analyst. Runs in Phase 2 parallel analysis. Analyzes funding rates, open interest, liquidation data, and basis spreads. Provides recommendations only - NO trading execution authority. All trades executed by trader subagent.",
            prompt=prompts["futures-analyst"],
            tools=[
                # Futures market data (read-only)
                "mcp__binance__binance_get_futures_open_orders",
                "mcp__binance__binance_get_futures_balances",
                "mcp__binance__binance_get_futures_trade_history",
                "mcp__binance__binance_calculate_liquidation_risk",
                # Market data
                "mcp__binance__binance_get_ticker",
                "mcp__binance__binance_get_orderbook",
                "mcp__binance__binance_get_price",
                "mcp__binance__binance_get_account",
                # Polygon data
                "mcp__polygon__polygon_crypto_snapshot_ticker",
                "mcp__polygon__polygon_crypto_aggregates",
                # Analysis tools
                "mcp__binance__binance_py_eval",
                "mcp__binance__binance_save_tool_notes",
                "mcp__binance__binance_read_tool_notes",
                "mcp__ide__executeCode",
                "Read"
            ],
            model=model_name
        )

    # Trader - Phase 4: ONLY agent with trading execution authority
    if "trader" in prompts:
        agents["trader"] = AgentDefinition(
            description="Trade execution specialist. ONLY agent with trading authority. Called in Phase 4 ONLY after primary agent evaluates consensus (3/4 majority) and risk-manager approval. Receives specific trade instructions and executes spot and futures orders.",
            prompt=prompts["trader"],
            tools=[
                # Spot trading tools
                "mcp__binance__binance_spot_market_order",
                "mcp__binance__binance_spot_limit_order",
                "mcp__binance__binance_spot_oco_order",
                "mcp__binance__binance_cancel_order",
                # Futures trading tools
                "mcp__binance__binance_trade_futures_market",
                "mcp__binance__binance_futures_limit_order",
                "mcp__binance__binance_cancel_futures_order",
                "mcp__binance__binance_set_futures_leverage",
                "mcp__binance__binance_manage_futures_positions",
                # Context tools (for verification)
                "mcp__binance__binance_get_account",
                "mcp__binance__binance_get_open_orders",
                "mcp__binance__binance_get_futures_open_orders",
                "mcp__binance__binance_get_ticker",
                "mcp__binance__binance_get_price",
                "mcp__binance__binance_trading_notes",
                # Analysis tools
                "mcp__binance__binance_py_eval",
                "mcp__ide__executeCode",
                "Read"
            ],
            model=model_name
        )

    # Reporter - Phase 5: Runs ABSOLUTE LAST, generates session tool usage report
    if "reporter" in prompts:
        agents["reporter"] = AgentDefinition(
            description="Session reporter. Runs ABSOLUTE LAST (Phase 5) after all decisions including trading. Aggregates all MCP tool calls made during the session into a CSV summary report.",
            prompt=prompts["reporter"],
            tools=[
                # Request log tools - one per MCP server
                "mcp__binance__binance_get_request_log",
                "mcp__polygon__polygon_get_request_log",
                "mcp__perplexity__get_request_log",
                # Analysis tools for CSV processing
                "mcp__binance__binance_py_eval",
                "mcp__ide__executeCode",
                "Read"
            ],
            model=model_name
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

def load_prompts(custom_system_prompt: Optional[str] = None,
                 custom_user_prompt: Optional[str] = None) -> tuple[str, str]:
    """
    Load system and user prompts, with optional custom overrides.

    Args:
        custom_system_prompt: Custom system prompt text (overrides file)
        custom_user_prompt: Custom user prompt text (overrides file)

    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    # System prompt
    if custom_system_prompt:
        system_prompt = custom_system_prompt
    else:
        with open("system_prompt.md", "r") as f:
            system_prompt = f.read()

    # User prompt
    if custom_user_prompt:
        user_prompt = custom_user_prompt
    else:
        with open("user_prompt.md", "r") as f:
            user_prompt = f.read()

    return system_prompt, user_prompt

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
            # Build health check URL - use /health endpoint which bypasses authentication
            # Health endpoint is at root level (e.g., http://host:port/health)
            from urllib.parse import urlparse
            parsed = urlparse(url)
            health_url = f"{parsed.scheme}://{parsed.netloc}/health"

            # Connect to the health endpoint
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        print(f"✓ {name}: OK ({url})")
                    else:
                        print(f"✗ {name}: HTTP {response.status} ({health_url})")
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

async def main(custom_system_prompt: Optional[str] = None,
               custom_user_prompt: Optional[str] = None):
    """Trading Agent with full MCP tool access for market analysis and execution.

    Args:
        custom_system_prompt: Optional custom system prompt (overrides file-based prompt)
        custom_user_prompt: Optional custom user prompt (overrides file-based prompt)
    """

    # Parse command-line arguments
    args = parse_arguments()

    # Verify MCP connectivity (optional pre-flight check)
    await verify_mcp_connectivity()

    # Session tracking for structured output
    session_id = str(uuid.uuid4())[:8]
    session_start = datetime.now(timezone.utc)

    # Variables to collect trading data for API response
    agent_text_responses = []  # Collect all TextBlock responses
    binance_notes_content = []  # Collect binance_trading_notes tool outputs
    trading_tool_calls = []  # Collect trading-specific tool calls

    # Load prompts (use custom prompts if provided, otherwise load from files)
    system_prompt, base_user_prompt = load_prompts(custom_system_prompt, custom_user_prompt)

    # Inject UTC timestamp into system prompt
    current_utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    system_prompt = f"Current UTC Time: {current_utc_time}\n\n{system_prompt}"

    # Show if custom prompts are provided via API
    if custom_system_prompt:
        print("🔧 Using custom system prompt from API\n")
    if custom_user_prompt:
        print("🔧 Using custom user prompt from API\n")

    # Load model configuration
    config = load_config()
    model_config = config.get("model", {})
    print(f"📋 Model configuration: {model_config.get('name', 'sonnet')}")
    if model_config.get("effort"):
        print(f"   Effort level: {model_config.get('effort')}")
        # TODO: Pass effort parameter to SDK when supported
    print()

    # Create subagent definitions
    print("=" * 80)
    print("Initializing Subagent Architecture...")
    print("=" * 80)
    subagents = create_subagent_definitions(config)
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

            # Binance MCP - Futures Data (read-only, NO trading tools)
            # NOTE: All trading execution removed - trades go through trader subagent
            "mcp__binance__binance_get_futures_balances",
            "mcp__binance__binance_get_futures_open_orders",
            "mcp__binance__binance_get_futures_trade_history",
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
            # Use the base user prompt loaded earlier
            user_prompt = base_user_prompt

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

            # Track tool calls for structured output
            current_tool_calls = {}  # Map tool_id -> tool_name

            # Process the initial response
            print(f"\n{'=' * 80}")
            print(f"[Turn {turn_count}] Agent Response")
            print(f"{'=' * 80}")

            # Process agent response
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
                            # Track tool call for result matching
                            current_tool_calls[block.id] = block.name
                            # Track trading tool calls
                            if "binance_spot_" in block.name or "binance_trade_futures" in block.name or "binance_futures_" in block.name:
                                trading_tool_calls.append({
                                    "tool_name": block.name,
                                    "tool_id": block.id,
                                    "input": getattr(block, 'input', {})
                                })
                        elif isinstance(block, ToolResultBlock):
                            display_tool_result(block)
                            # Capture binance_trading_notes results
                            tool_name = current_tool_calls.get(block.tool_use_id, "")
                            if tool_name == "mcp__binance__binance_trading_notes":
                                if not block.is_error and block.content:
                                    binance_notes_content.append(str(block.content))
                elif isinstance(message, SystemMessage):
                    display_system_message(message)
                elif isinstance(message, ResultMessage):
                    display_result(message)

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

                        current_utc_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                        user_input_with_timestamp = f"Current UTC Time: {current_utc_time}\n\n{user_input}"
                        await client.query(user_input_with_timestamp)

                        # Process Claude's response
                        print(f"\n{'=' * 80}")
                        print(f"[Turn {turn_count}] Agent Response")
                        print(f"{'=' * 80}")

                        # Process agent response
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
                                        # Track tool call for result matching
                                        current_tool_calls[block.id] = block.name
                                        # Track trading tool calls
                                        if "binance_spot_" in block.name or "binance_trade_futures" in block.name or "binance_futures_" in block.name:
                                            trading_tool_calls.append({
                                                "tool_name": block.name,
                                                "tool_id": block.id,
                                                "input": getattr(block, 'input', {})
                                            })
                                    elif isinstance(block, ToolResultBlock):
                                        display_tool_result(block)
                                        # Capture binance_trading_notes results
                                        tool_name = current_tool_calls.get(block.tool_use_id, "")
                                        if tool_name == "mcp__binance__binance_trading_notes":
                                            if not block.is_error and block.content:
                                                binance_notes_content.append(str(block.content))
                            elif isinstance(message, SystemMessage):
                                display_system_message(message)
                            elif isinstance(message, ResultMessage):
                                display_result(message)

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

    # Generate structured output
    print("\n" + "=" * 80)
    print("Generating structured session report...")
    print("=" * 80)

    session_end = datetime.now(timezone.utc)
    duration_seconds = (session_end - session_start).total_seconds()

    # Compile trading notes from agent responses and binance_trading_notes tool
    trading_notes_combined = ""
    if agent_text_responses:
        trading_notes_combined = "\n\n".join(agent_text_responses)
    if binance_notes_content:
        if trading_notes_combined:
            trading_notes_combined += "\n\n## Trading Notes from Binance Tool:\n" + "\n".join(binance_notes_content)
        else:
            trading_notes_combined = "\n".join(binance_notes_content)

    # Parse reporter agent's output for MCP report
    mcp_report = parse_reporter_output(agent_text_responses)

    # Extract trading actions from captured tool calls
    trading_actions = [
        TradingAction(
            action_type=tc["tool_name"].replace("mcp__binance__", ""),
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=tc.get("input", {}).get("symbol"),
            side=tc.get("input", {}).get("side"),
            details=tc.get("input", {})
        )
        for tc in trading_tool_calls
    ]

    # Extract subagents used from responses
    subagents_used = extract_subagents_used(agent_text_responses)

    # Extract key decisions from responses
    key_decisions = extract_key_decisions(agent_text_responses)

    # Extract workflow results from responses
    workflow_results = extract_workflow_results(agent_text_responses)

    # Build session resume
    session_resume = TradingSessionResume(
        session_id=session_id,
        start_time=session_start.isoformat(),
        end_time=session_end.isoformat(),
        duration_seconds=duration_seconds,
        trades_executed=len(trading_actions),
        subagents_used=subagents_used,
        key_decisions=key_decisions,
        market_conditions=None
    )

    # Determine status
    if exit_code == 0:
        status = "success"
    elif exit_code == 1:
        status = "error"
    else:
        status = "no_action"

    # Build structured report
    report = AgentExecutionReport(
        exit_code=exit_code,
        status=status,
        session=session_resume,
        mcp_report=mcp_report,
        workflow_results=workflow_results,
        trading_actions=trading_actions,
        trading_notes=trading_notes_combined
    )

    # Print exit message
    print("\n" + "=" * 80)
    if exit_code == 0:
        print("✅ Trading session completed successfully")
    elif exit_code == 1:
        print("❌ Trading session completed with errors")
    elif exit_code == 2:
        print("ℹ️  Trading session completed - no action taken")
    print(f"📊 Session ID: {session_id}")
    print(f"⏱️  Duration: {duration_seconds:.2f}s")
    print(f"🔧 Trades executed: {len(trading_actions)}")
    print(f"🤖 Subagents used: {len(subagents_used)}")
    if mcp_report.csv_path:
        print(f"📄 MCP Report: {mcp_report.csv_path}")
    print("=" * 80 + "\n")

    # Return structured report as dict
    return report.model_dump()

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
