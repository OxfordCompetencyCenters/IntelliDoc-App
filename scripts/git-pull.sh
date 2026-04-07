#!/bin/bash

# AI Catalogue - Git Pull Script
# This script pulls the latest changes from the GitHub repository
# It handles conflicts gracefully and provides clear feedback

set -e

echo "📥 AI Catalogue - Git Pull Script"
echo "================================="

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Not a git repository. Please run git-push.sh first to initialize."
    exit 1
fi

# Check if remote origin exists
if ! git remote get-url origin > /dev/null 2>&1; then
    echo "❌ No remote origin found. Adding GitHub repository..."
    git remote add origin https://github.com/OxfordCompetencyCenters/ai_catalogue_aicc.git
fi

# Verify remote URL
REMOTE_URL=$(git remote get-url origin)
echo "🔗 Remote repository: $REMOTE_URL"

# Show current status before pull
echo ""
echo "📊 Current Git Status (before pull):"
git status --short

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo ""
    echo "⚠️  You have uncommitted changes!"
    echo "📋 Uncommitted changes:"
    git diff --name-status
    echo ""
    read -p "Do you want to stash these changes before pulling? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "📦 Stashing uncommitted changes..."
        git stash push -m "Auto-stash before pull $(date)"
        STASHED=true
        echo "✅ Changes stashed successfully!"
    else
        echo "⚠️  Proceeding with uncommitted changes. This may cause conflicts."
        STASHED=false
    fi
else
    STASHED=false
    echo "✅ Working directory is clean"
fi

# Fetch latest changes
echo ""
echo "📡 Fetching latest changes from GitHub..."
if git fetch origin; then
    echo "✅ Fetch completed successfully!"
else
    echo "❌ Failed to fetch from GitHub. Check your internet connection and authentication."
    exit 1
fi

# Check if we're behind the remote
BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
AHEAD=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo "0")

echo ""
echo "📈 Repository Status:"
echo "   📥 Commits behind remote: $BEHIND"
echo "   📤 Commits ahead of remote: $AHEAD"

if [ "$BEHIND" -eq 0 ]; then
    echo "✅ Already up to date!"
    if [ "$STASHED" = "true" ]; then
        echo ""
        read -p "Do you want to restore your stashed changes? (Y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo "📦 Restoring stashed changes..."
            git stash pop
            echo "✅ Stashed changes restored!"
        fi
    fi
    exit 0
fi

# Show what will be pulled
echo ""
echo "📋 New commits to be pulled:"
git log --oneline HEAD..origin/main | head -10
if [ "$BEHIND" -gt 10 ]; then
    echo "   ... and $((BEHIND - 10)) more commits"
fi

echo ""
read -p "🤔 Do you want to pull these changes? (Y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    echo "❌ Pull cancelled."
    if [ "$STASHED" = "true" ]; then
        echo "💡 Your changes are safely stashed. Use 'git stash pop' to restore them."
    fi
    exit 1
fi

# Perform the pull
echo ""
echo "📥 Pulling changes from GitHub..."
if git pull origin main; then
    echo "✅ Pull completed successfully!"
    
    # Show what was updated
    echo ""
    echo "📊 Updated files:"
    git diff --name-status HEAD@{1} HEAD | head -20
    
    # Check for important file changes
    if git diff --name-only HEAD@{1} HEAD | grep -q "requirements.txt\|package.json\|docker-compose.yml\|\.env\.example"; then
        echo ""
        echo "⚠️  Important files were updated!"
        echo "💡 You may need to:"
        if git diff --name-only HEAD@{1} HEAD | grep -q "requirements.txt"; then
            echo "   📦 Rebuild Python dependencies: pip install -r backend/requirements.txt"
        fi
        if git diff --name-only HEAD@{1} HEAD | grep -q "package.json"; then
            echo "   📦 Rebuild Node dependencies: cd frontend && npm install"
        fi
        if git diff --name-only HEAD@{1} HEAD | grep -q "docker-compose.yml"; then
            echo "   🐳 Rebuild Docker containers: docker compose build"
        fi
        if git diff --name-only HEAD@{1} HEAD | grep -q "\.env\.example"; then
            echo "   ⚙️  Update .env file with new configuration options"
        fi
    fi
    
else
    echo "❌ Pull failed due to conflicts or other issues."
    echo ""
    echo "💡 Common solutions:"
    echo "   1. Resolve conflicts manually and commit"
    echo "   2. Reset to remote state: git reset --hard origin/main"
    echo "   3. Check for merge conflicts: git status"
    echo "   4. Seek help with: git pull --help"
    
    if [ "$STASHED" = "true" ]; then
        echo "   5. Your changes are stashed - restore with: git stash pop"
    fi
    exit 1
fi

# Restore stashed changes if they were stashed
if [ "$STASHED" = "true" ]; then
    echo ""
    read -p "Do you want to restore your stashed changes? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        echo "📦 Restoring stashed changes..."
        if git stash pop; then
            echo "✅ Stashed changes restored!"
            echo "⚠️  Please review any conflicts that may have occurred."
        else
            echo "❌ Failed to restore stashed changes. There may be conflicts."
            echo "💡 Manual resolution needed. Check: git stash list"
        fi
    else
        echo "💾 Stashed changes preserved. Use 'git stash pop' when ready."
    fi
fi

echo ""
echo "📋 Next Steps:"
echo "   🔍 Review changes: git log --oneline -10"
echo "   🐳 Restart services: ./scripts/start-local.sh (local) or ./scripts/start-dev.sh (production)"
echo "   🔧 Check configuration: Compare .env with .env.example"
echo ""
echo "🎉 Git pull completed successfully!"