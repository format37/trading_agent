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
from pydantic import BaseModel
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
    from trading_agent import main as agent_main
    AGENT_AVAILABLE = True
except ImportError as e:
    logger.error(f"Failed to import agent main: {e}")
    AGENT_AVAILABLE = False


class ActionRequest(BaseModel):
    """Request model for /action endpoint."""
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    event_data: Optional[Union[str, dict]] = None


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
async def trigger_action(action_request: ActionRequest):
    """
    Trigger the trading agent with optional prompts and event data.

    Args:
        action_request: Request containing optional system_prompt, user_prompt, and event_data

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

    # Log custom prompts if provided
    if action_request.system_prompt:
        logger.info("Using custom system prompt from request")
    if action_request.user_prompt:
        logger.info("Using custom user prompt from request")

    # Parse event data
    event_data = None
    if action_request.event_data:
        if isinstance(action_request.event_data, dict):
            event_data = action_request.event_data
            logger.info(f"Event data (JSON): {json.dumps(event_data, indent=2)}")
        elif isinstance(action_request.event_data, str):
            # Try to parse as JSON first
            try:
                event_data = json.loads(action_request.event_data)
                logger.info(f"Event data (parsed JSON): {json.dumps(event_data, indent=2)}")
            except json.JSONDecodeError:
                # Treat as plain text
                event_data = {"type": "text", "message": action_request.event_data}
                logger.info(f"Event data (text): {action_request.event_data}")
        else:
            logger.warning(f"Unknown event type: {type(action_request.event_data)}")
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
        sys.argv = ['trading_agent.py']
        if event_file_path:
            sys.argv.extend(['--event-file', event_file_path])

        logger.info(f"Running agent with args: {sys.argv}")

        # Run the agent
        start_time = datetime.now(timezone.utc)
        try:
            # The agent's main() function runs asyncio.run() internally
            # We need to run it in a separate thread to avoid event loop conflicts
            import concurrent.futures

            # Prepare kwargs for agent with custom prompts if provided
            agent_kwargs = {}
            if action_request.system_prompt:
                agent_kwargs['custom_system_prompt'] = action_request.system_prompt
            if action_request.user_prompt:
                agent_kwargs['custom_user_prompt'] = action_request.user_prompt

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, agent_main(**agent_kwargs))
                # Wait for completion and get result (with timeout)
                agent_result = future.result(timeout=600)  # 10 minute timeout

            end_time = datetime.now(timezone.utc)
            duration_seconds = (end_time - start_time).total_seconds()

            logger.info("=" * 80)
            logger.info(f"Agent execution completed in {duration_seconds:.2f} seconds")
            logger.info("=" * 80)

            # Build response with backward compatibility
            response_data = {
                "status": "success",
                "message": "Trading agent executed successfully",
                "timestamp": end_time.isoformat(),
                "duration_seconds": duration_seconds,
                "event_data": event_data
            }

            # Add new trading data fields if available
            if agent_result and isinstance(agent_result, dict):
                response_data["trading_notes"] = agent_result.get("trading_notes", "")
                response_data["actions"] = agent_result.get("actions", [])

                # Include session report path if available
                if agent_result.get("session_report_path"):
                    response_data["session_report"] = agent_result["session_report_path"]
                    logger.info(f"Session report: {agent_result['session_report_path']}")
            else:
                # Fallback: Try to read session report the old way
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
            # Agent may exit with sys.exit() (this shouldn't happen with new return-based approach)
            exit_code = e.code if isinstance(e.code, int) else 0
            end_time = datetime.now(timezone.utc)
            duration_seconds = (end_time - start_time).total_seconds()

            logger.info(f"Agent completed with exit code: {exit_code}")

            response_data = {
                "status": "completed" if exit_code == 0 else "error",
                "message": f"Agent completed with exit code {exit_code}",
                "exit_code": exit_code,
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
            except Exception as e:
                logger.warning(f"Could not read session report: {e}")

            return response_data
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
