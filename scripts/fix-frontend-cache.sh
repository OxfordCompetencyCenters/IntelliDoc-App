#!/bin/bash
# Fix frontend 404s for chunk-*.js and "Failed to fetch dynamically imported module"
# Caused by stale Vite cache or browser using old chunk URLs after container restart.
# This is NOT a permissions issue.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend/my-sveltekit-app"

echo "🧹 Clearing Vite and browser-related caches..."

# Remove Vite cache (so next dev run regenerates chunks)
if [ -d "$FRONTEND_DIR/.vite_cache" ]; then
  rm -rf "$FRONTEND_DIR/.vite_cache"
  echo "   Removed .vite_cache"
fi
if [ -d "$FRONTEND_DIR/node_modules/.vite" ]; then
  rm -rf "$FRONTEND_DIR/node_modules/.vite"
  echo "   Removed node_modules/.vite"
fi

echo ""
echo "✅ Done. Next steps:"
echo "   1. Restart the dev stack: ./scripts/start-dev.sh"
echo "   2. In the browser: hard refresh (Ctrl+Shift+R or Cmd+Shift+R) on http://localhost:5173"
echo "      Or clear site data for localhost:5173 (DevTools → Application → Storage → Clear site data)"
echo ""
echo "   If using Docker frontend: restart the frontend container so it starts with a clean cache."
