"""
Session Reporter Module

Generates markdown reports from agent activity data.
"""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from activity_tracker import AgentActivityTracker


class SessionReporter:
    """Generates markdown reports for trading agent sessions."""

    def __init__(self, activity_tracker: AgentActivityTracker):
        self.tracker = activity_tracker

    def generate_report(self) -> str:
        """Generate a complete markdown report."""
        sections = [
            self._generate_header(),
            self._generate_session_overview(),
            self._generate_turn_details(),
            self._generate_agent_summary(),
            self._generate_tool_statistics()
        ]
        return "\n\n".join(sections)

    def _generate_header(self) -> str:
        """Generate report header."""
        return "# Trading Agent Session Report"

    def _generate_session_overview(self) -> str:
        """Generate session overview section."""
        stats = self.tracker.get_session_stats()

        # Format start time
        start_dt = datetime.fromisoformat(stats["start_time"])
        start_str = start_dt.strftime("%Y-%m-%d %H:%M:%S UTC")

        lines = [
            "## Session Overview",
            f"**Session ID**: `{stats['session_id']}`",
            f"**Start Time**: {start_str}",
            f"**Duration**: {stats['duration']}",
            f"**Total Turns**: {stats['total_turns']}",
            f"**Total Tool Calls**: {stats['total_tool_calls']}",
            f"**Subagent Executions**: {stats['total_subagent_executions']}",
            f"**Unique Agents**: {stats['unique_agents']}"
        ]
        return "\n".join(lines)

    def _generate_turn_details(self) -> str:
        """Generate turn-by-turn breakdown."""
        if not self.tracker.turns:
            return "## Turn Details\n\n*No turns recorded*"

        lines = ["## Turn Details"]

        for turn in self.tracker.turns:
            lines.append(f"\n### Turn {turn.turn_number}")

            # Format turn time
            start_dt = datetime.fromisoformat(turn.start_time)
            start_str = start_dt.strftime("%H:%M:%S")
            lines.append(f"**Time**: {start_str}")

            # Agents executed
            agents_in_turn = {"main"}
            for exec in turn.subagent_executions:
                agents_in_turn.add(exec.subagent_type)
            lines.append(f"**Agents Executed**: {', '.join(sorted(agents_in_turn))}")

            # Main agent tools
            main_tools = []
            for tool_call in turn.tool_calls:
                if tool_call.agent == "main":
                    main_tools.append(tool_call.tool_name)

            if main_tools:
                lines.append(f"\n**Main Agent Tools** ({len(main_tools)} calls):")
                tool_counts = {}
                for tool in main_tools:
                    tool_counts[tool] = tool_counts.get(tool, 0) + 1

                for tool, count in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True):
                    lines.append(f"- `{tool}`: {count}x")

            # Subagent executions
            if turn.subagent_executions:
                lines.append(f"\n**Subagent Executions** ({len(turn.subagent_executions)}):")
                for exec in turn.subagent_executions:
                    exec_lines = [f"- **{exec.subagent_type}**"]

                    if exec.task_description:
                        exec_lines.append(f"  - Description: {exec.task_description}")

                    if exec.duration_ms:
                        duration_sec = exec.duration_ms / 1000
                        exec_lines.append(f"  - Duration: {duration_sec:.1f}s")

                    if exec.total_cost_usd:
                        exec_lines.append(f"  - Cost: ${exec.total_cost_usd:.4f}")

                    if exec.result_summary:
                        summary = exec.result_summary[:100]
                        if len(exec.result_summary) > 100:
                            summary += "..."
                        exec_lines.append(f"  - Result: {summary}")

                    lines.extend(exec_lines)

        return "\n".join(lines)

    def _generate_agent_summary(self) -> str:
        """Generate agent usage summary."""
        lines = ["## Agent Summary"]

        # Count tool calls per agent across all turns
        agent_tool_counts = {}
        agent_call_counts = {}

        for turn in self.tracker.turns:
            for tool_call in turn.tool_calls:
                agent = tool_call.agent
                tool = tool_call.tool_name

                if agent not in agent_tool_counts:
                    agent_tool_counts[agent] = {}
                    agent_call_counts[agent] = 0

                agent_tool_counts[agent][tool] = agent_tool_counts[agent].get(tool, 0) + 1
                agent_call_counts[agent] += 1

        # Count subagent executions
        subagent_exec_counts = {}
        for turn in self.tracker.turns:
            for exec in turn.subagent_executions:
                subagent_exec_counts[exec.subagent_type] = subagent_exec_counts.get(exec.subagent_type, 0) + 1

        # Main agent
        if "main" in agent_call_counts:
            lines.append(f"\n### Main Agent")
            lines.append(f"**Total Tool Calls**: {agent_call_counts['main']}")
            lines.append(f"**Tools Used**:")
            for tool, count in sorted(agent_tool_counts["main"].items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- `{tool}`: {count}x")

        # Subagents
        if subagent_exec_counts:
            lines.append(f"\n### Subagents")
            for subagent, count in sorted(subagent_exec_counts.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- **{subagent}**: Executed {count}x")

        return "\n".join(lines)

    def _generate_tool_statistics(self) -> str:
        """Generate tool usage statistics."""
        stats = self.tracker.get_session_stats()
        tool_usage = stats["tool_usage"]

        if not tool_usage:
            return "## Tool Usage Statistics\n\n*No tools used*"

        lines = [
            "## Tool Usage Statistics",
            f"\n**Total Tools Called**: {stats['total_tool_calls']}"
        ]

        # Top 10 most used tools
        top_tools = tool_usage[:10]
        if top_tools:
            lines.append("\n**Most Used Tools**:")
            for i, (tool, count) in enumerate(top_tools, 1):
                lines.append(f"{i}. `{tool}`: {count}x")

        return "\n".join(lines)

    def save_report(self, output_dir: str = "data/trading_agent") -> str:
        """Generate and save the report to a file."""
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Generate report content
        report_content = self.generate_report()

        # Create filename with timestamp
        filename = f"session_{self.tracker.session_id}.md"
        filepath = os.path.join(output_dir, filename)

        # Write report
        with open(filepath, "w") as f:
            f.write(report_content)

        return filepath

    @staticmethod
    def generate_and_save(tracker: AgentActivityTracker, output_dir: str = "data/trading_agent") -> str:
        """Convenience method to generate and save report."""
        reporter = SessionReporter(tracker)
        return reporter.save_report(output_dir)
