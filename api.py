"""
FastAPI Backend Service for Trading Agent

This service provides HTTP endpoints to trigger the trading agent:
- POST /action - Trigger agent analysis with optional event data
- GET /health - Health check endpoint

Authentication is handled via token middleware.
"""

import asyncio
import json
import logging
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the agent's main function
# We'll import dynamically to avoid import errors if dependencies are missing
try:
    from main import main as agent_main
    AGENT_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import agent main: {e}")
    AGENT_AVAILABLE = False


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Token-based authentication middleware.

    Accepts tokens via Authorization header: "Bearer <token>".
    Configure allowed tokens via AGENT_TOKENS env var (comma-separated).
    """

    def __init__(self, app):
        super().__init__(app)
        raw = os.getenv("AGENT_TOKENS", "")
        self.allowed_tokens = {t.strip() for t in raw.split(",") if t.strip()}
        self.require_auth = (
            os.getenv("AGENT_REQUIRE_AUTH", "false").lower() in ("1", "true", "yes")
        )

        if not self.allowed_tokens:
            if self.require_auth:
                logger.warning(
                    "AGENT_TOKENS is not set; AGENT_REQUIRE_AUTH=true -> "
                    "all requests will be rejected (401)"
                )
            else:
                logger.warning(
                    "AGENT_TOKENS is not set; authentication is DISABLED"
                )

    async def dispatch(self, request: Request, call_next):
        # Health check endpoint is always accessible
        if request.url.path == "/health":
            return await call_next(request)

        # If auth is not required, allow all requests
        if not self.require_auth:
            logger.info(f"Auth disabled, allowing request to {request.url.path}")
            return await call_next(request)

        # If no tokens configured but auth is required
        if not self.allowed_tokens:
            return JSONResponse(
                {"detail": "Unauthorized - No tokens configured"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Check Authorization header
        auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth_header:
            return JSONResponse(
                {"detail": "Unauthorized - Missing Authorization header"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"}
            )

        if not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                {"detail": "Unauthorized - Invalid Authorization format"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"}
            )

        token = auth_header.split(" ", 1)[1].strip()

        if token not in self.allowed_tokens:
            logger.warning(f"Invalid token attempted: {token[:8]}...")
            return JSONResponse(
                {"detail": "Unauthorized - Invalid token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"}
            )

        logger.info(f"Authenticated request to {request.url.path}")
        return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Trading Agent API starting up...")

    if not AGENT_AVAILABLE:
        logger.error("Trading agent is not available - import failed")
    else:
        logger.info("Trading agent is available")

    # Ensure data directories exist
    Path("data/trading_agent/logs").mkdir(parents=True, exist_ok=True)
    Path("data/trading_agent").mkdir(parents=True, exist_ok=True)

    yield

    logger.info("Trading Agent API shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Trading Agent API",
    description="HTTP API for triggering the Claude SDK Trading Agent",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware (optional, configure as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add authentication middleware
app.add_middleware(TokenAuthMiddleware)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "trading-agent",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_available": AGENT_AVAILABLE
    }


@app.post("/action")
async def trigger_action(
    request: Request,
    event: Optional[Union[dict, str]] = Body(None)
):
    """
    Trigger the trading agent with optional event data.

    Args:
        event: Event data (JSON object or text string)

    Returns:
        JSON response with execution status and session info
    """
    if not AGENT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Trading agent is not available"
        )

    logger.info("=" * 80)
    logger.info("Received action request")
    logger.info("=" * 80)

    # Parse event data
    event_data = None
    if event:
        if isinstance(event, dict):
            event_data = event
            logger.info(f"Event data (JSON): {json.dumps(event_data, indent=2)}")
        elif isinstance(event, str):
            # Try to parse as JSON first
            try:
                event_data = json.loads(event)
                logger.info(f"Event data (parsed JSON): {json.dumps(event_data, indent=2)}")
            except json.JSONDecodeError:
                # Treat as plain text
                event_data = {"type": "text", "message": event}
                logger.info(f"Event data (text): {event}")
        else:
            logger.warning(f"Unknown event type: {type(event)}")
    else:
        logger.info("No event data provided - running standard analysis")

    # Create temporary event file if event data provided
    event_file_path = None
    if event_data:
        try:
            # Create temp file for event data
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.json',
                delete=False,
                dir='/tmp'
            ) as f:
                json.dump(event_data, f, indent=2)
                event_file_path = f.name
            logger.info(f"Created event file: {event_file_path}")
        except Exception as e:
            logger.error(f"Failed to create event file: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process event data: {str(e)}"
            )

    # Prepare agent arguments
    original_argv = sys.argv.copy()
    try:
        # Set up sys.argv for the agent
        sys.argv = ['main.py']
        if event_file_path:
            sys.argv.extend(['--event-file', event_file_path])

        logger.info(f"Running agent with args: {sys.argv}")

        # Run the agent
        start_time = datetime.now(timezone.utc)
        try:
            # The agent's main() function runs asyncio.run() internally
            # We need to run it in a separate thread to avoid event loop conflicts
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, agent_main())
                # Wait for completion (with timeout)
                future.result(timeout=600)  # 10 minute timeout

            end_time = datetime.now(timezone.utc)
            duration_seconds = (end_time - start_time).total_seconds()

            logger.info("=" * 80)
            logger.info(f"Agent execution completed in {duration_seconds:.2f} seconds")
            logger.info("=" * 80)

            response_data = {
                "status": "success",
                "message": "Trading agent executed successfully",
                "timestamp": end_time.isoformat(),
                "duration_seconds": duration_seconds,
                "event_data": event_data
            }

            # Try to read session report if available
            try:
                log_dir = Path("data/trading_agent")
                report_files = sorted(log_dir.glob("session_*.md"), reverse=True)
                if report_files:
                    latest_report = report_files[0]
                    response_data["session_report"] = str(latest_report)
                    logger.info(f"Session report: {latest_report}")
            except Exception as e:
                logger.warning(f"Could not read session report: {e}")

            return response_data

        except concurrent.futures.TimeoutError:
            logger.error("Agent execution timed out")
            raise HTTPException(
                status_code=504,
                detail="Agent execution timed out (10 minute limit)"
            )
        except SystemExit as e:
            # Agent may exit with sys.exit()
            exit_code = e.code if isinstance(e.code, int) else 0
            end_time = datetime.now(timezone.utc)
            duration_seconds = (end_time - start_time).total_seconds()

            logger.info(f"Agent completed with exit code: {exit_code}")

            return {
                "status": "completed" if exit_code == 0 else "error",
                "message": f"Agent completed with exit code {exit_code}",
                "exit_code": exit_code,
                "timestamp": end_time.isoformat(),
                "duration_seconds": duration_seconds,
                "event_data": event_data
            }
        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Agent execution failed: {str(e)}"
            )

    finally:
        # Restore original sys.argv
        sys.argv = original_argv

        # Clean up temporary event file
        if event_file_path and os.path.exists(event_file_path):
            try:
                os.unlink(event_file_path)
                logger.info(f"Cleaned up event file: {event_file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up event file: {e}")


def main():
    """Run the API server."""
    port = int(os.getenv("PORT", "8012"))
    host = os.getenv("HOST", "0.0.0.0")

    logger.info("=" * 80)
    logger.info(f"Starting Trading Agent API on {host}:{port}")
    logger.info("=" * 80)
    logger.info("Endpoints:")
    logger.info("  GET  /health - Health check")
    logger.info("  POST /action - Trigger agent action")
    logger.info("=" * 80)

    uvicorn.run(
        app=app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info"),
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*",
        timeout_keep_alive=120,
    )


if __name__ == "__main__":
    main()
