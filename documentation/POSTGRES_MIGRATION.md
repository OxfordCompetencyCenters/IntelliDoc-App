# PostgreSQL Migration Guide

This guide explains how to migrate from SQLite to PostgreSQL for the AI Catalogue Backend.

## Prerequisites

- Python 3.13+
- PostgreSQL 15+ installed locally OR Docker for containerized setup

## Migration Overview

This migration completely replaces SQLite with PostgreSQL. **No data migration is performed** - this is a fresh start with PostgreSQL.

## Setup Options

### Option 1: Local PostgreSQL Installation

#### 1. Install PostgreSQL

**macOS (using Homebrew):**
```bash
brew install postgresql
brew services start postgresql
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql
```

**Windows:**
Download and install from [PostgreSQL.org](https://www.postgresql.org/download/windows/)

#### 2. Run Automated Setup

```bash
cd backend
chmod +x setup_postgres.sh
./setup_postgres.sh
```

This script will:
- Install Python PostgreSQL dependencies
- Create database and user
- Generate Django migrations
- Apply migrations
- Create superuser account

### Option 2: Docker Setup (Recommended)

#### 1. Start PostgreSQL Container

```bash
cd backend
docker-compose -f docker-compose-postgres.yml up -d
```

This will start:
- PostgreSQL database on port 5432
- pgAdmin web interface on port 8080

#### 2. Run Django Setup

```bash
python setup_postgres.py
```

## Manual Setup (Advanced)

If you prefer manual setup:

### 1. Install Dependencies

```bash
pip install psycopg2-binary psycopg
```

### 2. Create Database

```sql
-- Connect as postgres superuser
CREATE USER ai_catalogue_user WITH PASSWORD 'ai_catalogue_password';
CREATE DATABASE ai_catalogue_db OWNER ai_catalogue_user;
GRANT ALL PRIVILEGES ON DATABASE ai_catalogue_db TO ai_catalogue_user;
```

### 3. Environment Configuration

Create `.env` file:
```env
DB_NAME=ai_catalogue_db
DB_USER=ai_catalogue_user
DB_PASSWORD=ai_catalogue_password
DB_HOST=localhost
DB_PORT=5432
```

### 4. Django Migrations

```bash
python manage.py makemigrations users
python manage.py makemigrations templates
python manage.py makemigrations
python manage.py migrate
```

### 5. Create Superuser

```bash
python manage.py createsuperuser
```

## Database Configuration

The Django settings have been updated to use PostgreSQL:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'ai_catalogue_db'),
        'USER': os.getenv('DB_USER', 'ai_catalogue_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'ai_catalogue_password'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 60,
        },
    }
}
```

## Access Information

### Default Credentials

**Database:**
- Host: localhost
- Port: 5432
- Database: ai_catalogue_db
- User: ai_catalogue_user
- Password: ai_catalogue_password

**Django Admin:**
- Email: admin@example.com
- Password: admin123

**pgAdmin (Docker setup only):**
- URL: http://localhost:8080
- Email: admin@example.com
- Password: admin123

## Verification

### 1. Test Database Connection

```bash
python manage.py dbshell
```

### 2. Run Django Server

```bash
python manage.py runserver
```

### 3. Access Admin Interface

Visit: http://localhost:8000/admin/

## PostgreSQL Advantages

1. **Better Performance**: Optimized for concurrent connections
2. **Advanced Features**: JSON fields, full-text search, extensions
3. **Scalability**: Handles large datasets efficiently
4. **Production Ready**: Battle-tested for enterprise applications
5. **ACID Compliance**: Full transaction support
6. **Extensibility**: Custom functions and data types

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Ensure PostgreSQL is running
   - Check host/port configuration
   - Verify firewall settings

2. **Authentication Failed**
   - Verify username/password
   - Check pg_hba.conf configuration

3. **Database Does Not Exist**
   - Run setup script again
   - Manually create database

4. **Permission Denied**
   - Ensure user has proper privileges
   - Check database ownership

### Useful Commands

```bash
# Check PostgreSQL status
sudo systemctl status postgresql  # Linux
brew services list | grep postgresql  # macOS

# Connect to database
psql -h localhost -U ai_catalogue_user -d ai_catalogue_db

# View Django migrations
python manage.py showmigrations

# Reset migrations (if needed)
python manage.py migrate --fake-initial
```

## Production Considerations

For production deployment:

1. Use strong passwords
2. Configure SSL/TLS encryption
3. Set up connection pooling
4. Configure backups
5. Monitor performance
6. Use environment variables for secrets

## Support

If you encounter issues:

1. Check PostgreSQL logs
2. Verify Django database configuration
3. Test connection manually
4. Review migration history

The migration removes all existing SQLite data and starts fresh with PostgreSQL.