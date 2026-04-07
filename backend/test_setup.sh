#!/bin/bash

# Quick test script to generate encryption key and validate setup
cd /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend

echo "🔧 Testing Project API Keys Setup..."
echo "=================================="

echo ""
echo "1. Checking Django syntax..."
python manage.py check --deploy --settings=core.settings 2>&1

echo ""
echo "2. Generating encryption key..."
python manage.py setup_project_api_keys generate-key 2>&1

echo ""
echo "3. Testing encryption..."
python manage.py setup_project_api_keys test-encryption 2>&1

echo ""
echo "✅ Setup test completed!"
