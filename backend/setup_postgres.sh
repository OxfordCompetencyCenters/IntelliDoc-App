#!/bin/bash
# PostgreSQL Setup Script for AI Catalogue Backend

echo "🚀 Setting up PostgreSQL for AI Catalogue Backend..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed. Please install it first:"
    echo "   macOS: brew install postgresql"
    echo "   Ubuntu: sudo apt-get install postgresql postgresql-contrib"
    echo "   Windows: Download from https://www.postgresql.org/download/"
    exit 1
fi

# Start PostgreSQL service if not running
if ! pgrep -x "postgres" > /dev/null; then
    echo "🔄 Starting PostgreSQL service..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        brew services start postgresql
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        sudo systemctl start postgresql
    fi
fi

# Wait a moment for PostgreSQL to start
sleep 2

# Run the Python setup script
echo "🔄 Running Python setup script..."
python3 setup_postgres.py

if [ $? -eq 0 ]; then
    echo "✅ Setup completed successfully!"
    echo "🚀 You can now start the Django server with:"
    echo "   python manage.py runserver"
else
    echo "❌ Setup failed. Please check the error messages above."
    exit 1
fi