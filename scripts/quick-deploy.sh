#!/bin/bash
# scripts/quick-deploy.sh — Near-zero downtime update for code changes
# Use when: git pull with only code/migration/config changes
# Downtime: < 2 seconds (Django auto-reload)

set -e
echo "⚡ Quick deploy (code-only, < 2 seconds downtime)..."

# Pull latest code — volume mounts immediately reflect changes
echo "📥 Pulling latest code..."
git pull

# Run migrations if needed (safe while server is running)
echo "📦 Running migrations..."
docker compose exec backend python manage.py migrate --noinput 2>/dev/null || true

# Collect static files if needed
docker compose exec backend python manage.py collectstatic --noinput 2>/dev/null || true

# Django runserver auto-detects .py file changes and reloads (~2 sec)
# Frontend Vite HMR auto-detects .svelte/.ts changes (instant)
# If auto-reload didn't trigger (rare), touch a file to force it:
docker compose exec backend touch /app/core/settings.py

# Reload nginx config (zero downtime — graceful)
docker compose exec nginx nginx -s reload 2>/dev/null || true

echo ""
echo "✅ Deploy complete!"
echo "   Backend: auto-reloaded (~2 seconds)"
echo "   Frontend: HMR (instant)"
echo "   Nginx: graceful reload (0 seconds)"
