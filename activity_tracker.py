"""
Agent Activity Tracker Module

Tracks agent activity, tool usage, and subagent execution throughout trading sessions.
Provides data for session report generation.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict


@dataclass
class ToolCall:
    """Represents a single tool invocation."""
    tool_name: str
    tool_id: str
    timestamp: str
    agent: str = "main"  # "main" or subagent name


@dataclass
class SubagentExecution:
    """Represents a subagent execution via Task tool."""
    subagent_type: str
    task_description: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[int] = None
    result_summary: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    total_cost_usd: Optional[float] = None


@dataclass
class TurnActivity:
    """Represents activity within a single conversation turn."""
    turn_number: int
    start_time: str
    end_time: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    subagent_executions: List[SubagentExecution] = field(default_factory=list)

    def add_tool_call(self, tool_name: str, tool_id: str, agent: str = "main"):
        """Add a tool call to this turn."""
        self.tool_calls.append(ToolCall(
            tool_name=tool_name,
            tool_id=tool_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent=agent
        ))

    def add_subagent_execution(self, subagent_type: str, task_description: str):
        """Start tracking a subagent execution."""
        execution = SubagentExecution(
            subagent_type=subagent_type,
            task_description=task_description,
            start_time=datetime.now(timezone.utc).isoformat()
        )
        self.subagent_executions.append(execution)
        return execution

    def get_tool_counts(self) -> Dict[str, int]:
        """Get tool call counts for this turn."""
        counts = defaultdict(int)
        for call in self.tool_calls:
            counts[call.tool_name] += 1
        return dict(counts)

    def get_agent_tool_counts(self) -> Dict[str, Dict[str, int]]:
        """Get tool counts grouped by agent."""
        agent_counts = defaultdict(lambda: defaultdict(int))
        for call in self.tool_calls:
            agent_counts[call.agent][call.tool_name] += 1
        return {agent: dict(tools) for agent, tools in agent_counts.items()}


class AgentActivityTracker:
    """Tracks agent activity throughout a trading session."""

    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.start_time = datetime.now(timezone.utc).isoformat()
        self.end_time: Optional[str] = None
        self.turns: List[TurnActivity] = []
        self.current_turn: Optional[TurnActivity] = None

        # Track pending subagent executions (by tool_id)
        self._pending_subagents: Dict[str, SubagentExecution] = {}

    def start_turn(self, turn_number: int):
        """Start tracking a new conversation turn."""
        self.current_turn = TurnActivity(
            turn_number=turn_number,
            start_time=datetime.now(timezone.utc).isoformat()
        )
        self.turns.append(self.current_turn)

    def end_turn(self):
        """End the current turn."""
        if self.current_turn:
            self.current_turn.end_time = datetime.now(timezone.utc).isoformat()

    def record_tool_call(self, tool_name: str, tool_id: str, tool_input: Optional[Dict[str, Any]] = None):
        """Record a tool call in the current turn."""
        if not self.current_turn:
            # Auto-create turn if not started
            self.start_turn(len(self.turns) + 1)

        # If this is a Task tool, track it as a subagent execution
        if tool_name == "Task" and tool_input:
            subagent_type = tool_input.get("subagent_type", "unknown")
            task_description = tool_input.get("description", "")
            execution = self.current_turn.add_subagent_execution(subagent_type, task_description)
            self._pending_subagents[tool_id] = execution

        # Record the tool call
        self.current_turn.add_tool_call(tool_name, tool_id, agent="main")

    def record_tool_result(self, tool_id: str, result: Any, is_error: bool = False):
        """Record a tool result and update subagent execution if applicable."""
        if tool_id in self._pending_subagents:
            execution = self._pending_subagents[tool_id]
            execution.end_time = datetime.now(timezone.utc).isoformat()

            # Try to extract metadata from result
            if isinstance(result, dict):
                execution.duration_ms = result.get("duration_ms")
                execution.usage = result.get("usage")
                execution.total_cost_usd = result.get("total_cost_usd")
                execution.result_summary = str(result.get("result", ""))[:200]  # Truncate
            elif isinstance(result, str):
                execution.result_summary = result[:200]  # Truncate

            del self._pending_subagents[tool_id]

    def end_session(self):
        """End the session and finalize tracking."""
        self.end_time = datetime.now(timezone.utc).isoformat()
        if self.current_turn and not self.current_turn.end_time:
            self.end_turn()

    def get_session_stats(self) -> Dict[str, Any]:
        """Get comprehensive session statistics."""
        total_tools = sum(len(turn.tool_calls) for turn in self.turns)
        total_subagents = sum(len(turn.subagent_executions) for turn in self.turns)

        # Count unique agents used
        agents_used = {"main"}
        for turn in self.turns:
            for execution in turn.subagent_executions:
                agents_used.add(execution.subagent_type)

        # Count tool usage across all turns
        all_tool_counts = defaultdict(int)
        for turn in self.turns:
            for tool_name, count in turn.get_tool_counts().items():
                all_tool_counts[tool_name] += count

        # Sort tools by usage
        sorted_tools = sorted(all_tool_counts.items(), key=lambda x: x[1], reverse=True)

        # Calculate session duration
        duration_str = "N/A"
        if self.end_time:
            start = datetime.fromisoformat(self.start_time)
            end = datetime.fromisoformat(self.end_time)
            duration = end - start
            minutes = int(duration.total_seconds() // 60)
            seconds = int(duration.total_seconds() % 60)
            duration_str = f"{minutes}m {seconds}s"

        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": duration_str,
            "total_turns": len(self.turns),
            "total_tool_calls": total_tools,
            "total_subagent_executions": total_subagents,
            "unique_agents": len(agents_used),
            "agents_list": sorted(list(agents_used)),
            "tool_usage": sorted_tools
        }

    def get_turn_summary(self, turn_number: int) -> Optional[Dict[str, Any]]:
        """Get summary for a specific turn."""
        if turn_number <= 0 or turn_number > len(self.turns):
            return None

        turn = self.turns[turn_number - 1]
        agent_tools = turn.get_agent_tool_counts()

        return {
            "turn_number": turn.turn_number,
            "start_time": turn.start_time,
            "end_time": turn.end_time,
            "total_tools": len(turn.tool_calls),
            "agent_tools": agent_tools,
            "subagent_executions": [
                {
                    "type": exec.subagent_type,
                    "description": exec.task_description,
                    "duration_ms": exec.duration_ms,
                    "cost_usd": exec.total_cost_usd
                }
                for exec in turn.subagent_executions
            ]
        }

    def get_trading_actions(self) -> List[Dict[str, Any]]:
        """
        Extract only trading-specific tool calls from all turns.
        Returns a list of trading actions with timestamp and type.
        """
        trading_tool_names = [
            "mcp__binance__binance_spot_market_order",
            "mcp__binance__binance_spot_limit_order",
            "mcp__binance__binance_spot_oco_order",
            "mcp__binance__binance_cancel_order",
            "mcp__binance__binance_trade_futures_market",
            "mcp__binance__binance_futures_limit_order",
            "mcp__binance__binance_cancel_futures_order"
        ]

        trading_actions = []
        for turn in self.turns:
            for tool_call in turn.tool_calls:
                if tool_call.tool_name in trading_tool_names:
                    trading_actions.append({
                        "type": tool_call.tool_name.replace("mcp__binance__", ""),
                        "timestamp": tool_call.timestamp,
                        "tool_id": tool_call.tool_id,
                        "turn_number": turn.turn_number
                    })

        return trading_actions
