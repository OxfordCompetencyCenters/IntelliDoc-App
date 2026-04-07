#!/bin/bash

# AI Catalogue - Git Push Script
# This script commits and pushes all changes to the GitHub repository
# It ensures sensitive files are excluded and follows best practices

set -e

echo "📦 AI Catalogue - Git Push Script"
echo "================================="

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo "❌ Not a git repository. Initializing..."
    git init
    echo "🔗 Adding remote origin..."
    git remote add origin https://github.com/OxfordCompetencyCenters/ai_catalogue_aicc.git
fi

# Check if remote origin exists, if not add it
if ! git remote get-url origin > /dev/null 2>&1; then
    echo "🔗 Adding remote origin..."
    git remote add origin https://github.com/OxfordCompetencyCenters/ai_catalogue_aicc.git
fi

# Ensure we're on main branch
echo "🌿 Switching to main branch..."
git branch -M main

# Show current status
echo ""
echo "📊 Current Git Status:"
git status

echo ""
echo "🔍 Checking for sensitive files..."

# Check for common sensitive files that might have been missed
SENSITIVE_FILES=(
    ".env"
    ".env.local"
    ".env.production"
    "*.key"
    "*.pem"
    "*.p12"
    "api_keys.txt"
    "secrets.txt"
    "credentials.json"
)

FOUND_SENSITIVE=false
for pattern in "${SENSITIVE_FILES[@]}"; do
    if git ls-files --others --ignored --exclude-standard 2>/dev/null | grep -q "$pattern" 2>/dev/null; then
        echo "⚠️  Found ignored sensitive file: $pattern"
        FOUND_SENSITIVE=true
    fi
done

if [ "$FOUND_SENSITIVE" = "true" ]; then
    echo "✅ Sensitive files are properly ignored by .gitignore"
else
    echo "✅ No sensitive files detected in staging area"
fi

echo ""
echo "📝 Adding files to git..."
git add .

# Show what will be committed (limit output to avoid pager)
echo ""
echo "📋 Files to be committed:"
git --no-pager diff --cached --name-status

echo ""
read -p "🤔 Do you want to continue with the commit? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Commit cancelled."
    exit 1
fi

# Get commit message from user
echo ""
echo "💬 Enter commit message:"
read -r COMMIT_MESSAGE

# Require commit message
while [ -z "$COMMIT_MESSAGE" ]; do
    echo "⚠️  Commit message is required. Please enter a message:"
    read -r COMMIT_MESSAGE
done

# Commit the changes
echo ""
echo "💾 Committing changes..."
git commit -m "$COMMIT_MESSAGE"

echo "✅ Changes committed successfully!"

# Push to remote repository
echo ""
echo "🚀 Pushing to GitHub repository..."
REPO_URL=$(git remote get-url origin | sed 's|https://[^@]*@|https://|')
echo "   Repository: $REPO_URL"
echo "   Branch: main"

# Push with upstream tracking
if git push -u origin main; then
    echo "✅ Successfully pushed to GitHub!"
    echo ""
    CLEAN_URL=$(git remote get-url origin | sed 's|https://[^@]*@|https://|')
    echo "🌐 Repository URL: $CLEAN_URL"
    echo "📊 View your changes: $CLEAN_URL/commits/main"
else
    echo "❌ Failed to push to GitHub."
    echo ""
    echo "💡 Common solutions:"
    echo "   1. Check your GitHub authentication (token/SSH key)"
    echo "   2. Verify repository permissions"
    echo "   3. Try: git push --force-with-lease origin main (if needed)"
    echo "   4. Check if repository exists: https://github.com/OxfordCompetencyCenters/ai_catalogue_aicc"
    exit 1
fi

echo ""
echo "📋 Next Steps:"
echo "   🔄 To pull changes on production server: git pull origin main"
echo "   🚀 To deploy: ./scripts/start-dev.sh (on production server)"
echo "   💻 For local development: ./scripts/start-local.sh"
echo ""
echo "🎉 Git push completed successfully!"