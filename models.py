"""
Pydantic models for structured agent outputs.

Provides typed schemas for trading agent execution reports,
MCP tools usage, and trading actions.
"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class MCPToolsReport(BaseModel):
    """MCP tools usage report from reporter agent."""
    csv_path: Optional[str] = None
    total_tool_calls: int = 0
    unique_requesters: int = 0
    unique_tools: int = 0
    calls_by_server: Dict[str, int] = {}
    top_tools: List[Dict[str, Any]] = []


class TradingAction(BaseModel):
    """Record of a trading action executed."""
    action_type: str
    timestamp: str
    symbol: Optional[str] = None
    side: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class TradingSessionResume(BaseModel):
    """Concise trading session resume."""
    session_id: str
    start_time: str
    end_time: str
    duration_seconds: float
    trades_executed: int
    subagents_used: List[str] = []
    key_decisions: List[str] = []
    market_conditions: Optional[str] = None


class AgentExecutionReport(BaseModel):
    """Complete structured output from trading agent."""
    exit_code: int
    status: str  # "success", "error", "no_action"
    session: TradingSessionResume
    mcp_report: MCPToolsReport
    trading_actions: List[TradingAction]
    trading_notes: str = ""
