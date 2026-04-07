#!/bin/bash

# AI Catalogue - SSL Certificate Renewal Script
# This script renews Let's Encrypt SSL certificates

set -e

echo "🔄 AI Catalogue SSL Certificate Renewal"
echo "Domain: aicc.uksouth.cloudapp.azure.com"
echo ""

# Change to project directory
cd /home/alokkrsahu/ai_catalogue

# Load environment variables
if [ -f .env ]; then
    source .env
fi

# Renew certificates
echo "📜 Renewing SSL certificates..."
docker compose -f docker-compose.yml -f docker-compose.ssl.yml run --rm certbot renew

# Check if renewal was successful
if [ $? -eq 0 ]; then
    echo "✅ Certificate renewal successful!"
    
    # Reload nginx to use new certificates
    echo "🔄 Reloading Nginx configuration..."
    docker compose -f docker-compose.yml -f docker-compose.ssl.yml exec nginx nginx -s reload
    
    echo "🎉 SSL certificates renewed and Nginx reloaded successfully!"
    echo "📅 Next renewal check in ~60 days"
else
    echo "❌ Certificate renewal failed"
    echo "🔍 Check the output above for details"
    exit 1
fi