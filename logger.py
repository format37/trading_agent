"""
Logging Module for Trading Agent

Handles timestamped file logging for event-driven server deployment.
Redirects stdout/stderr to log files while maintaining console output.
"""

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class TeeStream:
    """Stream that writes to both file and console."""

    def __init__(self, file_stream, console_stream):
        self.file_stream = file_stream
        self.console_stream = console_stream

    def write(self, data):
        self.file_stream.write(data)
        self.console_stream.write(data)
        self.flush()

    def flush(self):
        self.file_stream.flush()
        self.console_stream.flush()


class SessionLogger:
    """Manages session logging with timestamped files."""

    def __init__(self, log_dir: str = "data/trading_agent/logs", session_id: Optional[str] = None):
        """
        Initialize session logger.

        Args:
            log_dir: Directory to store log files
            session_id: Optional session ID (defaults to timestamp)
        """
        self.log_dir = Path(log_dir)
        self.session_id = session_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.log_file_path: Optional[Path] = None
        self.log_file = None

        # Store original streams
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        # Setup logging
        self._setup_logging()

    def _setup_logging(self):
        """Setup file logging with console echo."""
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create log file path
        log_filename = f"session_{self.session_id}.log"
        self.log_file_path = self.log_dir / log_filename

        # Open log file
        self.log_file = open(self.log_file_path, 'w', buffering=1)  # Line buffered

        # Write header
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.log_file.write(f"{'=' * 80}\n")
        self.log_file.write(f"Trading Agent Session Log\n")
        self.log_file.write(f"Session ID: {self.session_id}\n")
        self.log_file.write(f"Started: {timestamp}\n")
        self.log_file.write(f"{'=' * 80}\n\n")
        self.log_file.flush()

        # Redirect stdout and stderr to tee streams
        sys.stdout = TeeStream(self.log_file, self.original_stdout)
        sys.stderr = TeeStream(self.log_file, self.original_stderr)

    def close(self):
        """Close log file and restore original streams."""
        if self.log_file:
            # Write footer
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            self.log_file.write(f"\n{'=' * 80}\n")
            self.log_file.write(f"Session ended: {timestamp}\n")
            self.log_file.write(f"{'=' * 80}\n")

            # Restore streams before closing file
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr

            # Close file
            self.log_file.close()
            self.log_file = None

    def get_log_path(self) -> str:
        """Get the path to the current log file."""
        return str(self.log_file_path) if self.log_file_path else ""

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def setup_session_logging(log_dir: str = "data/trading_agent/logs",
                         session_id: Optional[str] = None) -> SessionLogger:
    """
    Setup session logging with timestamped files.

    Args:
        log_dir: Directory to store log files
        session_id: Optional session ID (defaults to timestamp)

    Returns:
        SessionLogger instance

    Example:
        logger = setup_session_logging()
        print("This goes to both console and log file")
        logger.close()
    """
    return SessionLogger(log_dir=log_dir, session_id=session_id)
