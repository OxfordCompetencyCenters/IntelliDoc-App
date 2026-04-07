# Admin-Only Project Deletion API

## Overview

This document describes the admin-only project deletion functionality implemented in the AI Catalogue system. Only users with admin role can delete projects, and deletion requires password confirmation for security.

## Security Features

- **Role-based Access**: Only users with `role=ADMIN` can delete projects
- **Password Confirmation**: Admin users must provide their password to confirm deletion
- **Detailed Logging**: All deletion attempts are logged with user information
- **Atomic Operations**: Deletions are performed in database transactions
- **Complete Cleanup**: Deletes associated files, vector collections, and workflows

## API Endpoints

### 1. Universal Project API (Recommended)

```http
DELETE /api/projects/{project_id}/
Content-Type: application/json
Authorization: Bearer <admin_jwt_token>

{
    "password": "admin_password"
}
```

### 2. Legacy Project API

```http
DELETE /api/intellidoc-projects/{project_id}/
Content-Type: application/json
Authorization: Bearer <admin_jwt_token>

{
    "password": "admin_password"
}
```

## Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| project_id | UUID/String | Yes | The unique identifier of the project to delete |
| password | String | Yes | Admin user's password for confirmation |

## Response Codes

| Status Code | Description | Response Body |
|-------------|-------------|---------------|
| 200 | Success | Detailed deletion confirmation |
| 400 | Bad Request | Missing password field |
| 401 | Unauthorized | Invalid password |
| 403 | Forbidden | Non-admin user attempted deletion |
| 404 | Not Found | Project doesn't exist |
| 500 | Server Error | Deletion failed due to system error |

## Success Response Example

```json
{
    "message": "Project \"My Test Project\" deleted successfully",
    "project_id": "123e4567-e89b-12d3-a456-426614174000",
    "project_name": "My Test Project",
    "deleted_documents": 5,
    "deleted_files": 5,
    "deleted_workflows": 2,
    "deleted_by": "admin@example.com",
    "deleted_at": "2024-01-15T10:30:00Z",
    "api_version": "universal_v1"
}
```

## Error Response Examples

### Non-Admin User (403 Forbidden)
```json
{
    "error": "Permission denied",
    "detail": "Only administrators can delete projects",
    "user_role": "USER",
    "required_role": "ADMIN",
    "api_version": "universal_v1"
}
```

### Missing Password (400 Bad Request)
```json
{
    "error": "Password confirmation required",
    "detail": "Project deletion requires password confirmation for security",
    "required_field": "password",
    "api_version": "universal_v1"
}
```

### Invalid Password (401 Unauthorized)
```json
{
    "error": "Authentication failed",
    "detail": "Invalid password provided",
    "api_version": "universal_v1"
}
```

## What Gets Deleted

When a project is deleted, the following items are removed:

1. **Project Record**: The main project database entry
2. **Documents**: All uploaded documents in the project
3. **Files**: Physical files stored on disk/cloud storage
4. **Vector Collections**: Milvus/ChromaDB vector data
5. **Agent Workflows**: All associated AI workflows
6. **Permissions**: User and group permissions for the project
7. **Execution History**: Workflow execution logs and results

## Security Considerations

### Access Control
- Only users with `UserRole.ADMIN` can delete projects
- Project creators cannot delete their own projects unless they are admins
- Staff users (`UserRole.STAFF`) cannot delete projects

### Password Security
- Password is verified using Django's built-in `check_password()` method
- Passwords are never logged or stored in responses
- Failed password attempts are logged for security monitoring

### Audit Trail
- All deletion attempts (successful and failed) are logged
- Logs include user email, project information, and timestamps
- Successful deletions include detailed cleanup statistics

## Implementation Details

### Permission Classes
- `IsAdminUserForDeletion`: Custom permission class for deletion operations
- Provides detailed logging and error messages
- Separates deletion permissions from general admin permissions

### Database Transactions
- All deletion operations use `transaction.atomic()`
- Ensures data consistency if any part of deletion fails
- Rollback protection for partial failures

### File Cleanup
- Physical files are deleted from storage (local/cloud)
- Graceful handling of missing or corrupted files
- Continues deletion even if some files cannot be removed

## Testing

Run the test script to verify admin-only deletion functionality:

```bash
cd backend
python test_admin_deletion.py
```

The test script verifies:
- Regular users cannot delete projects
- Staff users cannot delete projects  
- Admin users with wrong passwords cannot delete
- Admin users without passwords cannot delete
- Admin users with correct passwords can delete successfully

## Frontend Integration

### JavaScript Example

```javascript
async function deleteProject(projectId, adminPassword) {
    const response = await fetch(`/api/projects/${projectId}/`, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${adminToken}`
        },
        body: JSON.stringify({
            password: adminPassword
        })
    });
    
    if (response.ok) {
        const result = await response.json();
        console.log('Project deleted:', result.message);
        return result;
    } else {
        const error = await response.json();
        throw new Error(error.detail || 'Deletion failed');
    }
}
```

### UI Recommendations

1. **Confirmation Dialog**: Show a confirmation dialog before deletion
2. **Password Input**: Require admin password in the confirmation dialog
3. **Progress Indicator**: Show deletion progress for large projects
4. **Error Handling**: Display specific error messages to users
5. **Success Feedback**: Show detailed deletion results

## Troubleshooting

### Common Issues

1. **403 Forbidden**: User is not an admin
   - Solution: Ensure user has `role=ADMIN` in the database

2. **401 Unauthorized**: Wrong password
   - Solution: Verify admin password is correct

3. **500 Server Error**: File system issues
   - Solution: Check file permissions and storage availability

### Debug Mode

Enable debug logging in Django settings to see detailed deletion logs:

```python
LOGGING = {
    'loggers': {
        'api.universal_project_views': {
            'level': 'DEBUG',
        }
    }
}
```

## Version History

- **v1.0**: Initial implementation with basic admin-only deletion
- **v1.1**: Added password confirmation requirement
- **v1.2**: Enhanced error handling and detailed responses
- **v1.3**: Added comprehensive cleanup and atomic transactions