# Deployment Guide

Comprehensive guide for deploying the Crypto Trading Agent in production environments.

## Prerequisites

### System Requirements

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum (8GB recommended)
- 20GB disk space for data persistence
- Ubuntu 20.04+ or compatible Linux distribution

### Required Services

The trading agent depends on three MCP servers:

1. **mcp-polygon** - Market data provider
2. **mcp-binance** - Exchange integration
3. **mcp-perplexity** - Market intelligence

Deploy these services first using their respective repositories:
- [mcp-binance](https://github.com/format37/mcp-binance)
- [mcp-polygon](https://github.com/format37/mcp-polygon)
- [mcp-perplexity](https://github.com/format37/mcp-perplexity)

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/format37/trading_agent.git
cd trading_agent
```

### 2. Create Data Directories

```bash
# Create shared data directory for CSV persistence
sudo mkdir -p /home/ubuntu/mcp/data
sudo mkdir -p /home/ubuntu/mcp/data/trading_agent/logs

# Set proper permissions
sudo chown -R $USER:$USER /home/ubuntu/mcp/data

# Create Claude config directory (for CLI authentication)
sudo mkdir -p /home/ubuntu/.claude
sudo chown -R 1000:1000 /home/ubuntu/.claude
sudo chmod -R 755 /home/ubuntu/.claude
```

### 3. Configure Environment

Create `.env.prod` file:

```bash
# MCP Server URLs
POLYGON_URL=http://mcp-polygon:8006/polygon/
BINANCE_URL=http://mcp-binance-local:8010/binance/
PERPLEXITY_URL=http://mcp-perplexity-local:8011/perplexity/

# API Keys (if not using Claude CLI auth)
ANTHROPIC_API_KEY=your_api_key_here

# MCP Connectivity Check
# Set to "true" in production for fail-fast behavior
# Set to "false" in development to show warnings only
STRICT_MCP_CHECK=true

# Agent Configuration
AGENT_PORT=8012
AGENT_HOST=0.0.0.0
LOG_LEVEL=INFO

# Optional: Custom token for REST API authentication
API_TOKEN=your_secure_token_here
```

## Docker Configuration

### Network Setup

All services must communicate on the same Docker network:

```bash
# Create shared network (if not exists)
docker network create mcp-shared

# Verify network exists
docker network ls | grep mcp-shared
```

### Docker Compose Configuration

The `docker-compose.prod.yml` file:

```yaml
version: '3.8'

services:
  trading-agent:
    build:
      context: .
      dockerfile: Dockerfile.prod
    container_name: trading-agent
    hostname: trading-agent
    ports:
      - "8012:8012"
    environment:
      - POLYGON_URL=${POLYGON_URL}
      - BINANCE_URL=${BINANCE_URL}
      - PERPLEXITY_URL=${PERPLEXITY_URL}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - STRICT_MCP_CHECK=${STRICT_MCP_CHECK}
    volumes:
      # Data persistence
      - /home/ubuntu/mcp/data:/data
      # Claude CLI configuration
      - /home/ubuntu/.claude:/home/appuser/.claude
      # Logs
      - /home/ubuntu/mcp/data/trading_agent/logs:/app/logs
    networks:
      - mcp-shared
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8012/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  mcp-shared:
    external: true
```

### Build and Deploy

```bash
# Production deployment script
./compose_prod.sh

# Or manually:
docker-compose -f docker-compose.prod.yml up -d --build

# Check deployment status
docker ps | grep trading-agent

# View logs
docker logs -f trading-agent
```

## MCP Server Connectivity

### Pre-flight Connectivity Check

The agent performs connectivity checks at startup:

1. **HTTP connectivity test** - Verifies MCP servers are reachable
2. **MCP protocol validation** - Ensures servers implement MCP correctly

Control behavior with `STRICT_MCP_CHECK`:
- `true` (Production): Exit immediately if any server unreachable
- `false` (Development): Show warnings but continue

### Verify MCP Server Status

```bash
# Check if MCP servers are running
docker ps | grep -E "mcp-polygon|mcp-binance|mcp-perplexity"

# Test connectivity from host
curl http://localhost:8006/health  # Polygon
curl http://localhost:8010/health  # Binance
curl http://localhost:8011/health  # Perplexity

# Test connectivity from within network
docker run --rm --network mcp-shared alpine \
  wget -qO- http://mcp-polygon:8006/health
```

### Troubleshooting Connectivity

**Issue: "MCP server unreachable"**

1. Verify all services are on the same network:
```bash
docker network inspect mcp-shared | jq '.Containers'
```

2. Check service names match configuration:
```bash
# Service names in docker-compose must match URLs in .env.prod
docker ps --format "table {{.Names}}"
```

3. Test inter-container communication:
```bash
docker exec trading-agent ping mcp-polygon
docker exec trading-agent ping mcp-binance-local
```

**Issue: "Connection refused"**

1. Check MCP server ports:
```bash
docker exec mcp-polygon netstat -tlnp
docker exec mcp-binance-local netstat -tlnp
```

2. Verify firewall rules:
```bash
# No firewall should block internal Docker network
sudo iptables -L -n | grep DROP
```

## Volume Mounts

### Data Directory Structure

```
/home/ubuntu/mcp/data/
├── mcp-polygon/          # Polygon CSV outputs
│   ├── *.csv             # Market data files
│   └── cache/            # API response cache
├── mcp-binance/          # Binance CSV outputs
│   ├── *.csv             # Trading data files
│   └── trading_notes/    # Strategy notes
├── mcp-perplexity/       # Perplexity outputs
│   └── *.json            # Research results
└── trading_agent/        # Agent data
    ├── logs/             # Application logs
    └── state/            # Agent state files
```

### Permissions

Container runs as `appuser` (UID 1000):

```bash
# Fix permission issues
sudo chown -R 1000:1000 /home/ubuntu/mcp/data
sudo chmod -R 755 /home/ubuntu/mcp/data
```

## Health Monitoring

### Health Check Endpoint

```bash
# Check agent health
curl http://localhost:8012/health

# Expected response:
{
  "status": "healthy",
  "mcp_servers": {
    "polygon": "connected",
    "binance": "connected",
    "perplexity": "connected"
  },
  "uptime": "2h 15m",
  "version": "1.0.0"
}
```

### Container Health

```bash
# Docker health status
docker inspect trading-agent | jq '.[0].State.Health'

# Restart if unhealthy
docker-compose -f docker-compose.prod.yml restart trading-agent
```

## Logging

### Log Configuration

Logs are written to `/home/ubuntu/mcp/data/trading_agent/logs/`:

- `agent.log` - Main application logs
- `trades.log` - Trading execution logs
- `errors.log` - Error and exception logs

### Log Rotation

Configure logrotate for production:

```bash
# /etc/logrotate.d/trading-agent
/home/ubuntu/mcp/data/trading_agent/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 1000 1000
    sharedscripts
    postrotate
        docker exec trading-agent kill -USR1 1
    endscript
}
```

### Monitoring Logs

```bash
# Real-time logs
docker logs -f trading-agent

# Tail specific log file
tail -f /home/ubuntu/mcp/data/trading_agent/logs/agent.log

# Search for errors
grep ERROR /home/ubuntu/mcp/data/trading_agent/logs/errors.log
```

## Security

### API Token Authentication

Protect the REST API endpoint:

1. Generate secure token:
```bash
openssl rand -base64 32
```

2. Set in `.env.prod`:
```bash
API_TOKEN=your_generated_token_here
```

3. Use in requests:
```bash
curl -H "Authorization: Bearer your_generated_token_here" \
  http://localhost:8012/action
```

### Network Security

```bash
# Restrict port access (example with UFW)
sudo ufw allow from 10.0.0.0/8 to any port 8012
sudo ufw deny 8012
```

### Secret Management

For production, use Docker secrets:

```bash
# Create secret
echo "your_api_key" | docker secret create anthropic_key -

# Reference in compose file
services:
  trading-agent:
    secrets:
      - anthropic_key
    environment:
      - ANTHROPIC_API_KEY_FILE=/run/secrets/anthropic_key
```

## Backup and Recovery

### Data Backup

```bash
# Backup script
#!/bin/bash
BACKUP_DIR="/backup/trading_agent"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
tar -czf ${BACKUP_DIR}/data_${DATE}.tar.gz /home/ubuntu/mcp/data/

# Keep only last 30 days
find ${BACKUP_DIR} -name "data_*.tar.gz" -mtime +30 -delete
```

### Recovery Procedure

```bash
# Stop services
docker-compose -f docker-compose.prod.yml down

# Restore data
tar -xzf /backup/trading_agent/data_20240115_120000.tar.gz -C /

# Restart services
docker-compose -f docker-compose.prod.yml up -d
```

## Performance Tuning

### Docker Resource Limits

```yaml
# docker-compose.prod.yml
services:
  trading-agent:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G
```

### Python Optimization

Environment variables for performance:

```bash
# Reduce Python overhead
PYTHONUNBUFFERED=1
PYTHONDONTWRITEBYTECODE=1

# Optimize pandas
PANDAS_COPY_ON_WRITE=1
```

## Maintenance

### Update Procedure

```bash
# Pull latest changes
git pull origin main

# Rebuild container
docker-compose -f docker-compose.prod.yml build

# Deploy with zero downtime
docker-compose -f docker-compose.prod.yml up -d --no-deps trading-agent
```

### Container Cleanup

```bash
# Remove unused images
docker image prune -a

# Clean build cache
docker builder prune

# Remove old containers
docker container prune
```

## Troubleshooting

### Common Issues

**Agent not starting:**
```bash
# Check logs
docker logs trading-agent --tail 100

# Verify environment variables
docker exec trading-agent env | grep -E "POLYGON|BINANCE|PERPLEXITY"
```

**CSV files not persisting:**
```bash
# Check volume mounts
docker inspect trading-agent | jq '.[0].Mounts'

# Verify write permissions
docker exec trading-agent touch /data/test.txt
```

**Memory issues:**
```bash
# Check memory usage
docker stats trading-agent

# Increase memory limit in docker-compose.yml
```

### Debug Mode

Enable debug logging:

```bash
# .env.prod
LOG_LEVEL=DEBUG

# Restart to apply
docker-compose -f docker-compose.prod.yml restart trading-agent
```