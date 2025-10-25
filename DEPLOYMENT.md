# Trading Agent - Production Deployment Guide

## Overview

This guide explains how to deploy the Trading Agent as a Dockerized FastAPI service on your VPS with Caddy reverse proxy.

## Architecture

```
Internet → Caddy (HTTPS) → trading-agent:8012 (HTTP)
                         → mcp-polygon:8009
                         → mcp-binance:8010
                         → mcp-perplexity:8011
```

## Prerequisites

1. **VPS with Docker and Docker Compose** installed
2. **Caddy reverse proxy** running with SSL configured
3. **MCP servers** running on the `mcp-shared` Docker network:
   - mcp-polygon (port 8009)
   - mcp-binance (port 8010)
   - mcp-perplexity (port 8011)
4. **Shared data directory** for CSV files

## Configuration

### 1. Update Caddyfile

Add the trading agent routing to your Caddyfile **before** the catch-all n8n handler:

```caddyfile
scriptlab.duckdns.org {
    tls /server/fullchain.pem /server/privkey.pem

    # Existing handlers...
    handle /openscad* {
        reverse_proxy mcp-openscad:8004
    }

    handle /perplexity* {
        reverse_proxy mcp-perplexity:8011
    }

    handle /polygon* {
        reverse_proxy mcp-polygon:8006
    }

    # NEW: Trading Agent
    handle /trading-agent* {
        reverse_proxy trading-agent:8012
    }

    handle_path /webhook-test* {
        reverse_proxy host.docker.internal:8321
    }

    # n8n webhooks - preserve the full path
    handle /webhook/* {
        reverse_proxy n8n:5678
    }

    # n8n main interface - catches all other paths
    handle {
        reverse_proxy n8n:5678
    }

    # Basic hardening headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "no-referrer"
    }
}
```

**Important**: Place the `/trading-agent*` handler before any catch-all handlers.

### 2. Configure Environment Variables

Edit `.env.prod` and set your actual values:

```bash
# Required: Anthropic API Key
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx...

# Required: Generate secure tokens
# Example: openssl rand -hex 32
AGENT_TOKENS=your_secure_token_here,another_optional_token

# Enable authentication
AGENT_REQUIRE_AUTH=true

# Telemetry (disabled by default)
ENABLE_TELEMETRY=false
```

### 3. Ensure Data Directory Exists

```bash
# On your VPS
mkdir -p ./data/trading_agent/logs
mkdir -p ./data/mcp-binance
mkdir -p ./data/mcp-polygon
mkdir -p ./data/mcp-perplexity
```

### 4. Create mcp-shared Network (if not exists)

```bash
docker network create mcp-shared
```

## Deployment Steps

### 1. Build the Docker Image

```bash
cd /path/to/trading_agent
docker-compose -f docker-compose.prod.yml build
```

### 2. Start the Service

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 3. Verify the Service is Running

```bash
# Check container status
docker ps | grep trading-agent

# Check logs
docker logs trading-agent

# Check health
docker exec trading-agent python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8012/health').read())"
```

### 4. Reload Caddy Configuration

```bash
# If Caddy is running in Docker
docker exec caddy caddy reload --config /etc/caddy/Caddyfile

# If Caddy is running as a system service
sudo systemctl reload caddy
```

### 5. Test the Endpoints

#### Test Health Check (No Auth Required)

```bash
curl https://scriptlab.duckdns.org/trading-agent/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "trading-agent",
  "timestamp": "2025-10-26T12:34:56.789012+00:00",
  "agent_available": true
}
```

#### Test Action Endpoint (Auth Required)

```bash
# Simple scheduled check (no event data)
curl -X POST \
  -H "Authorization: Bearer your_secure_token_here" \
  https://scriptlab.duckdns.org/trading-agent/action

# With event data (JSON)
curl -X POST \
  -H "Authorization: Bearer your_secure_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "scheduled",
    "message": "Daily market analysis"
  }' \
  https://scriptlab.duckdns.org/trading-agent/action

# With event data (market alert)
curl -X POST \
  -H "Authorization: Bearer your_secure_token_here" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "market_alert",
    "message": "Bitcoin price crossed $100,000 USD",
    "symbol": "BTC",
    "price": 100000
  }' \
  https://scriptlab.duckdns.org/trading-agent/action
```

## API Endpoints

### GET /health

Health check endpoint (no authentication required).

**Response:**
```json
{
  "status": "healthy",
  "service": "trading-agent",
  "timestamp": "ISO-8601 timestamp",
  "agent_available": true
}
```

### POST /action

Trigger the trading agent with optional event data.

**Authentication:** Required (Bearer token)

**Request Body (Optional):**
- JSON object with event data
- Plain text (will be converted to event)
- Empty body (runs standard analysis)

**Example Event JSON:**
```json
{
  "type": "scheduled|market_alert|price_change|custom",
  "message": "Description of the event",
  "symbol": "BTC",
  "price": 100000,
  "custom_field": "any value"
}
```

**Response:**
```json
{
  "status": "success|completed|error",
  "message": "Human-readable status message",
  "timestamp": "ISO-8601 timestamp",
  "duration_seconds": 123.45,
  "event_data": { /* echoed event data */ },
  "session_report": "path/to/report.md",
  "exit_code": 0
}
```

## Monitoring

### View Logs

```bash
# Real-time logs
docker logs -f trading-agent

# Last 100 lines
docker logs --tail 100 trading-agent

# Logs since 1 hour ago
docker logs --since 1h trading-agent
```

### Check Container Health

```bash
docker ps --filter name=trading-agent --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### View Session Reports

```bash
# List recent reports
ls -lht data/trading_agent/session_*.md | head -5

# View latest report
cat $(ls -t data/trading_agent/session_*.md | head -1)
```

## Automation Examples

### Cron Job (Scheduled Analysis)

```bash
# Run every 4 hours
0 */4 * * * curl -X POST -H "Authorization: Bearer YOUR_TOKEN" https://scriptlab.duckdns.org/trading-agent/action >> /var/log/trading-agent-cron.log 2>&1
```

### N8N Webhook Integration

Create an n8n workflow that sends webhooks to the trading agent:

1. Add HTTP Request node
2. Method: POST
3. URL: `https://scriptlab.duckdns.org/trading-agent/action`
4. Authentication: Header Auth
   - Name: `Authorization`
   - Value: `Bearer YOUR_TOKEN`
5. Body: JSON with event data

### Python Script Integration

```python
import requests

def trigger_trading_agent(event_data=None):
    url = "https://scriptlab.duckdns.org/trading-agent/action"
    headers = {
        "Authorization": "Bearer YOUR_TOKEN",
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=event_data, headers=headers)
    return response.json()

# Trigger with event
result = trigger_trading_agent({
    "type": "scheduled",
    "message": "Daily analysis"
})
print(result)
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs for errors
docker logs trading-agent

# Check if MCP servers are running
docker ps | grep mcp-

# Verify network exists
docker network ls | grep mcp-shared

# Test network connectivity
docker run --rm --network mcp-shared alpine ping -c 3 mcp-polygon
```

### Authentication Errors

```bash
# Check if token is configured
docker exec trading-agent env | grep AGENT_TOKENS

# Verify token in .env.prod
cat .env.prod | grep AGENT_TOKENS

# Test without auth (if AGENT_REQUIRE_AUTH=false)
curl -X POST https://scriptlab.duckdns.org/trading-agent/action
```

### Agent Not Connecting to MCP Servers

```bash
# Check MCP server URLs in container
docker exec trading-agent env | grep -E "(POLYGON|BINANCE|PERPLEXITY)_URL"

# Test connectivity from container
docker exec trading-agent curl http://mcp-polygon:8009/polygon/health
docker exec trading-agent curl http://mcp-binance:8010/binance/health
docker exec trading-agent curl http://mcp-perplexity:8011/perplexity/health
```

### Caddy Not Routing to Service

```bash
# Check if trading-agent is accessible from Caddy container
docker exec caddy wget -O- http://trading-agent:8012/health

# Verify Caddy configuration
docker exec caddy caddy validate --config /etc/caddy/Caddyfile

# Check Caddy logs
docker logs caddy | grep trading-agent
```

## Updating the Service

### Update Code Only

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build
```

### Update Configuration Only

```bash
# Edit .env.prod
nano .env.prod

# Restart service (no rebuild needed)
docker-compose -f docker-compose.prod.yml restart trading-agent
```

### Full Cleanup and Redeploy

```bash
# Stop and remove
docker-compose -f docker-compose.prod.yml down

# Rebuild from scratch
docker-compose -f docker-compose.prod.yml build --no-cache

# Start
docker-compose -f docker-compose.prod.yml up -d
```

## Security Recommendations

1. **Use Strong Tokens**: Generate with `openssl rand -hex 32`
2. **Rotate Tokens Regularly**: Update `.env.prod` and restart
3. **Enable Caddy SSL**: Already configured in your Caddyfile
4. **Restrict Network Access**: Use firewall rules if needed
5. **Monitor Logs**: Set up alerts for suspicious activity
6. **Backup Data**: Regularly backup `./data/trading_agent/`

## Enabling Telemetry (Optional)

If you want to enable telemetry for observability:

1. **Edit `.env.prod`:**
```bash
ENABLE_TELEMETRY=true
OTEL_EXPORTER_TYPE=otlp-grpc
OTEL_EXPORTER_OTLP_ENDPOINT=http://your-collector:4317
```

2. **Uncomment telemetry packages in `requirements-prod.txt`**

3. **Rebuild the Docker image:**
```bash
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

## Support

- Check logs: `docker logs trading-agent`
- Review session reports: `data/trading_agent/session_*.md`
- Test health: `curl https://scriptlab.duckdns.org/trading-agent/health`

## Files Structure

```
trading_agent/
├── api.py                      # FastAPI service
├── main.py                     # Agent core (modified for optional telemetry)
├── Dockerfile.prod            # Production container
├── docker-compose.prod.yml    # Production deployment
├── requirements-prod.txt      # Production dependencies
├── .env.prod                  # Production environment (configure this!)
├── DEPLOYMENT.md              # This file
├── system_prompt.md           # Agent system prompt
├── user_prompt.md             # Agent user prompt
├── entrance.md                # Agent entrance message
├── prompts/                   # Subagent prompts
│   ├── btc_researcher.md
│   ├── eth_researcher.md
│   └── ...
└── data/                      # Mounted volume
    ├── trading_agent/         # Session logs and reports
    ├── mcp-binance/           # Binance CSV data
    ├── mcp-polygon/           # Polygon CSV data
    └── mcp-perplexity/        # Perplexity data
```
