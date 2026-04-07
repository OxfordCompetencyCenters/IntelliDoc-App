#!/bin/bash

cd /Users/alok/Documents/AICC/ai_catalogue/ai_catalogue/backend
source venv/bin/activate

echo "🔄 Checking migration status..."
python manage.py showmigrations users | tail -10

echo ""
echo "🔄 Running migration 0020..."
python manage.py migrate users 0020

echo ""
echo "🔄 Final migration status..."
python manage.py showmigrations users | tail -10

echo ""
echo "✅ Migration process completed!"
