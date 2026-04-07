# 🚀 Quick Start Guide - Project API Key Management

## The syntax error has been fixed! Here's how to get started:

### Step 1: Generate Encryption Key
```bash
cd backend
python generate_encryption_key.py
```

This will output something like:
```
PROJECT_API_KEY_ENCRYPTION_KEY=your-generated-key-here
```

### Step 2: Set Environment Variable
```bash
# Temporarily (for this session):
export PROJECT_API_KEY_ENCRYPTION_KEY='your-generated-key-here'

# Or add to your .env file:
echo 'PROJECT_API_KEY_ENCRYPTION_KEY=your-generated-key-here' >> .env
```

### Step 3: Apply Database Migration
```bash
python manage.py migrate
```

### Step 4: Test the System
```bash
# Test encryption service
python manage.py setup_project_api_keys test-encryption

# List all projects 
python manage.py setup_project_api_keys list-projects

# Run the full test suite
python manage.py test project_api_keys
```

### Step 5: Start Using Project-Specific API Keys

#### Via Management Command
```bash
python manage.py setup_project_api_keys add-key \
  --project-id your-project-uuid \
  --provider openai \
  --api-key sk-your-openai-key \
  --user-email your@email.com \
  --validate
```

#### Via API
```bash
# Get available providers
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/project-api-keys/providers/

# Add API key
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_type": "openai",
    "api_key": "sk-your-key",
    "key_name": "Production Key",
    "validate_key": true
  }' \
  http://localhost:8000/api/project-api-keys/project/your-uuid/keys/

# Check project status
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/project-api-keys/project/your-uuid/status/
```

## What's Fixed ✅

- ✅ **Syntax Error**: Fixed literal `\n` characters in imports
- ✅ **File Structure**: All files properly formatted
- ✅ **Django Integration**: App registered and configured
- ✅ **Database Migration**: Ready to apply
- ✅ **Management Commands**: Working encryption key generation

## Available Commands

```bash
# Generate encryption key
python manage.py setup_project_api_keys generate-key

# Test encryption functionality  
python manage.py setup_project_api_keys test-encryption

# List all projects and their API key status
python manage.py setup_project_api_keys list-projects

# Add API key to a project
python manage.py setup_project_api_keys add-key \
  --project-id uuid \
  --provider openai \
  --api-key sk-... \
  --user-email user@example.com \
  --validate

# Validate existing API key
python manage.py setup_project_api_keys validate-key \
  --project-id uuid \
  --provider openai

# List API keys for a specific project
python manage.py setup_project_api_keys list-keys \
  --project-id uuid
```

## API Endpoints Available

- `GET /api/project-api-keys/providers/` - List available providers
- `GET /api/project-api-keys/project/{id}/status/` - Get project API key status
- `POST /api/project-api-keys/project/{id}/keys/` - Set/update API key
- `POST /api/project-api-keys/project/{id}/keys/{provider}/validate/` - Validate key
- `DELETE /api/project-api-keys/project/{id}/keys/{provider}/` - Delete key
- `GET /api/project-api-keys/project/{id}/keys/` - List project keys

## Next Steps

1. **Generate and set your encryption key** (Step 1-2 above)
2. **Apply the migration** (`python manage.py migrate`)
3. **Test the system** (`python manage.py setup_project_api_keys test-encryption`)
4. **Add API keys to your projects** (via command or API)
5. **Start Phase 2**: Update existing services to use project-specific keys

The foundation is complete and ready to use! 🎉
