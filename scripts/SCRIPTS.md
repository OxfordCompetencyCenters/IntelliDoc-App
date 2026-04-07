# Deployment Scripts Guide

## Which script to use?

| Scenario | Script | Downtime |
|----------|--------|----------|
| Code changes (`.py`, `.svelte`, `.ts`) | `quick-deploy.sh` | ~2 seconds |
| New migrations | `quick-deploy.sh` | ~2 seconds |
| nginx config changes | `quick-deploy.sh` | 0 seconds |
| New pip/npm packages | `rebuild-deploy.sh` | ~10 seconds |
| Dockerfile changes | `rebuild-deploy.sh` | ~10 seconds |
| Fresh install / infra changes | `start-dev.sh` | ~8-12 minutes |

## Scripts

### `quick-deploy.sh` — Daily use (< 2 seconds downtime)

For the common case after `git pull` with code-only changes.

```bash
./scripts/quick-deploy.sh
```

What it does:
1. `git pull` — volume mounts reflect changes instantly
2. Runs pending database migrations (safe while server is running)
3. Collects static files
4. Triggers Django auto-reload (~2 seconds)
5. Frontend picks up changes via Vite HMR (instant)
6. Gracefully reloads nginx (0 seconds)

### `rebuild-deploy.sh` — Dependency changes (< 10 seconds downtime)

For when `requirements.txt`, `package.json`, or Dockerfiles change.

```bash
./scripts/rebuild-deploy.sh
```

What it does:
1. `git pull`
2. Builds new Docker images **while old app still serves traffic**
3. Swaps backend and frontend containers (databases stay running)
4. Waits for backend health check
5. Reloads nginx

### `start-dev.sh` — Full stack setup (~8-12 minutes downtime)

For first-time setup or infrastructure changes (new DB versions, docker-compose changes).

```bash
./scripts/start-dev.sh
```

What it does:
1. Stops all containers
2. Pulls latest database images
3. Rebuilds everything from scratch (`--no-cache`)
4. Starts all services sequentially with health checks
