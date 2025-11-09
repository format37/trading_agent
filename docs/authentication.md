# Claude CLI Authentication Guide

This guide covers how to authenticate Claude CLI with your trading agent container to use your Claude subscription instead of API keys.

## Authentication Workflow

### Step 1: Connect to the Running Container

```bash
docker exec -it trading-agent bash
```

### Step 2: Authenticate Claude CLI

Once inside the container, run:

```bash
claude
```

Follow the prompts to authenticate with your Claude account.

> **Note:** If you restart the container, you will need to repeat this authentication step.

## Troubleshooting

### Permission Denied Error

**Error Message:**
```
EACCES: permission denied, mkdir '/home/appuser/.claude/debug'
```

**Cause:** This occurs when the host directory doesn't have proper permissions for the container's appuser.

**Solution:**

1. **Fix permissions on the VPS host** (as ubuntu user):

```bash
# Create the .claude directory with correct permissions
sudo mkdir -p /home/ubuntu/.claude
sudo chown -R 1000:1000 /home/ubuntu/.claude
sudo chmod -R 755 /home/ubuntu/.claude
```

2. **Rebuild and restart the container:**

```bash
# Stop the existing container
docker-compose -f docker-compose.prod.yml down

# Rebuild and start with new permissions
docker-compose -f docker-compose.prod.yml up -d --build
```

3. **Try authentication again:**

```bash
# Enter the container
docker exec -it trading-agent bash

# Authenticate Claude CLI
claude login

# Exit the container
exit
```

### Why This Happens

The Docker volume mount uses the host directory's permissions. The container's `appuser` has UID 1000, which must match the host directory ownership for proper access.

## Volume Mount Configuration

The trading agent container mounts the Claude configuration directory:

```yaml
# docker-compose.prod.yml
volumes:
  - /home/ubuntu/.claude:/home/appuser/.claude
```

This ensures your Claude authentication persists across container restarts.

## Additional Notes

- Authentication credentials are stored locally in `/home/ubuntu/.claude`
- The authentication is tied to your Claude account subscription
- No API keys are required when using CLI authentication
- The container must have network access to reach Claude's authentication servers

## Security Considerations

- Keep your `.claude` directory permissions restrictive (755)
- Don't share or commit the `.claude` directory contents
- Regularly review and rotate your Claude account credentials
- Consider using Docker secrets for additional security in production