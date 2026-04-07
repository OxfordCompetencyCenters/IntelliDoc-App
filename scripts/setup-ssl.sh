#!/bin/bash

# AI Catalogue - SSL Certificate Setup Script
# This script sets up Let's Encrypt SSL certificates for HTTPS

set -e

echo "🔐 AI Catalogue SSL Certificate Setup"
echo ""

# Check if running as root (required for certbot)
if [ "$EUID" -eq 0 ]; then
    echo "⚠️  Warning: Running as root. Make sure this is intentional."
fi

# Function to validate domain name
validate_domain() {
    local domain=$1
    if [[ ! $domain =~ ^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?\.[a-zA-Z]{2,}$ ]]; then
        echo "❌ Invalid domain name format: $domain"
        echo "   Please enter a valid domain name (e.g., example.com or subdomain.example.com)"
        return 1
    fi
    return 0
}

# Function to validate email
validate_email() {
    local email=$1
    if [[ ! $email =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        echo "❌ Invalid email format: $email"
        return 1
    fi
    return 0
}

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please create it first by running:"
    echo "   cp .env.example .env"
    exit 1
fi

# Load environment variables
source .env

# Get domain name and email if not set in .env
if [ -z "$DOMAIN_NAME" ]; then
    echo "📝 Domain Configuration"
    echo ""
    while true; do
        read -p "Enter your domain name (e.g., yourdomain.com): " DOMAIN_INPUT
        if validate_domain "$DOMAIN_INPUT"; then
            DOMAIN_NAME=$DOMAIN_INPUT
            break
        fi
    done
    
    # Add to .env file
    echo "" >> .env
    echo "# SSL Configuration" >> .env
    echo "DOMAIN_NAME=$DOMAIN_NAME" >> .env
    echo "✅ Domain added to .env file"
fi

if [ -z "$SSL_EMAIL" ]; then
    echo ""
    while true; do
        read -p "Enter your email for Let's Encrypt notifications: " EMAIL_INPUT
        if validate_email "$EMAIL_INPUT"; then
            SSL_EMAIL=$EMAIL_INPUT
            break
        fi
    done
    
    # Add to .env file
    echo "SSL_EMAIL=$SSL_EMAIL" >> .env
    echo "✅ Email added to .env file"
fi

echo ""
echo "🌐 Configuration:"
echo "   Domain: $DOMAIN_NAME"
echo "   Email: $SSL_EMAIL"
echo ""

# Verify domain points to this server
echo "🔍 Checking DNS configuration..."
DOMAIN_IP=$(dig +short $DOMAIN_NAME | tail -n1)
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s ipinfo.io/ip 2>/dev/null || echo "Unable to detect")

if [ -n "$DOMAIN_IP" ]; then
    echo "   Domain IP: $DOMAIN_IP"
    echo "   Server IP: $SERVER_IP"
    
    if [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
        echo ""
        echo "⚠️  WARNING: Domain DNS may not point to this server"
        echo "   Make sure your domain's A record points to: $SERVER_IP"
        echo ""
        read -p "Continue anyway? (y/N): " continue_anyway
        if [ "$continue_anyway" != "y" ] && [ "$continue_anyway" != "Y" ]; then
            echo "❌ SSL setup cancelled. Please configure DNS first."
            exit 1
        fi
    else
        echo "✅ DNS configuration looks correct"
    fi
else
    echo "⚠️  Unable to resolve domain. Make sure DNS is configured."
fi

echo ""

# Create necessary directories
echo "📁 Creating SSL directories..."
mkdir -p ./certbot/certs
mkdir -p ./certbot/www
mkdir -p ./certbot/logs
mkdir -p ./nginx/ssl

# Stop current services if running
echo "🛑 Stopping current services..."
docker compose down 2>/dev/null || true

# Start minimal HTTP server for certificate validation
echo "🌐 Starting temporary HTTP server for domain validation..."
docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d nginx --no-deps

# Wait for nginx to start
sleep 5

# Request SSL certificate
echo "📜 Requesting SSL certificate from Let's Encrypt..."
echo "   This may take a few minutes..."

# First, try dry run
echo "🧪 Testing certificate request (dry run)..."
docker compose -f docker-compose.yml -f docker-compose.ssl.yml run --rm certbot \
    certonly --webroot --webroot-path=/var/www/certbot \
    --email $SSL_EMAIL --agree-tos --no-eff-email \
    --dry-run -d $DOMAIN_NAME

if [ $? -eq 0 ]; then
    echo "✅ Dry run successful! Proceeding with real certificate..."
    
    # Real certificate request
    docker compose -f docker-compose.yml -f docker-compose.ssl.yml run --rm certbot \
        certonly --webroot --webroot-path=/var/www/certbot \
        --email $SSL_EMAIL --agree-tos --no-eff-email \
        -d $DOMAIN_NAME
    
    if [ $? -eq 0 ]; then
        echo "🎉 SSL certificate obtained successfully!"
        
        # Update environment variables for HTTPS
        echo ""
        echo "📝 Updating environment for HTTPS..."
        
        # Update CORS and CSRF settings in .env
        if grep -q "CORS_ALLOWED_ORIGINS" .env; then
            sed -i "s|CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=https://$DOMAIN_NAME|g" .env
        else
            echo "CORS_ALLOWED_ORIGINS=https://$DOMAIN_NAME" >> .env
        fi
        
        if grep -q "CSRF_TRUSTED_ORIGINS" .env; then
            sed -i "s|CSRF_TRUSTED_ORIGINS=.*|CSRF_TRUSTED_ORIGINS=https://$DOMAIN_NAME|g" .env
        else
            echo "CSRF_TRUSTED_ORIGINS=https://$DOMAIN_NAME" >> .env
        fi
        
        if grep -q "ALLOWED_HOSTS" .env; then
            sed -i "s|ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$DOMAIN_NAME,localhost,127.0.0.1,backend,frontend|g" .env
        else
            echo "ALLOWED_HOSTS=$DOMAIN_NAME,localhost,127.0.0.1,backend,frontend" >> .env
        fi
        
        echo "✅ Environment updated for HTTPS"
        
        # Restart with SSL configuration
        echo ""
        echo "🔄 Restarting services with SSL configuration..."
        docker compose down
        docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d
        
        echo ""
        echo "🎉 SSL setup completed successfully!"
        echo ""
        echo "🌟 Your application is now available at:"
        echo "   🔒 HTTPS: https://$DOMAIN_NAME"
        echo "   🔧 Admin: https://$DOMAIN_NAME/admin/"
        echo ""
        echo "📋 Certificate Information:"
        echo "   Location: ./certbot/certs/live/$DOMAIN_NAME/"
        echo "   Expires: ~90 days from now"
        echo "   Auto-renewal: Use the renewal script"
        echo ""
        echo "🔄 To renew certificates automatically, add this to your crontab:"
        echo "   0 2 * * * cd $(pwd) && ./scripts/renew-ssl.sh"
        
    else
        echo "❌ Failed to obtain SSL certificate"
        echo "🔍 Check the logs above for details"
        echo "💡 Common issues:"
        echo "   - Domain DNS not pointing to this server"
        echo "   - Port 80 not accessible from internet"
        echo "   - Firewall blocking HTTP traffic"
        exit 1
    fi
else
    echo "❌ Dry run failed"
    echo "🔍 Please check:"
    echo "   - Domain DNS configuration"
    echo "   - Port 80 accessibility"
    echo "   - Server firewall settings"
    exit 1
fi