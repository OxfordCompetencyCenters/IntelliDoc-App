# Role-Based Access Control Components

This guide explains how to use the role-based access control components to ensure proper UI visibility based on user roles.

## Components

### 1. RoleBasedAccess.svelte
A general-purpose component for wrapping any content that should be role-restricted.

#### Props
- `requiredRole`: `'ADMIN' | 'STAFF' | 'USER'` (default: 'USER')
- `requireAuth`: `boolean` (default: true)
- `fallback`: `boolean` (default: false) - Show fallback content instead of hiding
- `fallbackMessage`: `string` (default: 'Access restricted')

#### Usage Examples

```svelte
<!-- Only show to admin users -->
<RoleBasedAccess requiredRole="ADMIN">
  <button class="danger">Delete All Projects</button>
</RoleBasedAccess>

<!-- Show to staff and admin users -->
<RoleBasedAccess requiredRole="STAFF">
  <div class="admin-panel">Staff controls</div>
</RoleBasedAccess>

<!-- Show fallback message for restricted content -->
<RoleBasedAccess requiredRole="ADMIN" fallback={true} fallbackMessage="Admin access required">
  <AdminPanel />
</RoleBasedAccess>
```

### 2. AdminDeleteButton.svelte
A specialized delete button that only appears for admin users and includes built-in confirmation.

#### Props
- `title`: `string` (default: 'Delete (Admin only)')
- `confirmMessage`: `string` (default: 'Are you sure you want to delete this item?')
- `size`: `'small' | 'medium' | 'large'` (default: 'medium')
- `variant`: `'danger' | 'warning'` (default: 'danger')
- `disabled`: `boolean` (default: false)
- `requireConfirmation`: `boolean` (default: true)
- `itemName`: `string` (default: '') - Used for specific confirmation messages

#### Events
- `on:delete` - Triggered when user confirms deletion

#### Usage Examples

```svelte
<!-- Basic admin delete button -->
<AdminDeleteButton on:delete={handleDelete} />

<!-- Small delete button with custom item name -->
<AdminDeleteButton
  size="small"
  itemName={project.name}
  on:delete={() => deleteProject(project.id)}
/>

<!-- Warning variant without confirmation -->
<AdminDeleteButton
  variant="warning"
  requireConfirmation={false}
  on:delete={handleSoftDelete}
>
  Archive
</AdminDeleteButton>
```

## Role Hierarchy

The system uses a role hierarchy where higher roles have access to lower-level content:

1. **ADMIN** (Level 3) - Full access to everything
2. **STAFF** (Level 2) - Access to staff and user content
3. **USER** (Level 1) - Access to user content only

## Auth Store Integration

The components automatically integrate with the auth store:

```typescript
// Auth store provides these derived stores:
export const isAdmin = derived(authStore, $auth => $auth.user?.role === 'ADMIN');
export const user = derived(authStore, $auth => $auth.user);
export const isAuthenticated = derived(authStore, $auth => $auth.isAuthenticated);
```

## Implementation Checklist

### ✅ Completed Updates

1. **Project List Page** (`/routes/features/intellidoc/+page.svelte`)
   - ✅ Delete buttons only show for admin users
   - ✅ Uses AdminDeleteButton component
   - ✅ Proper confirmation messages

2. **Individual Project Page** (`/routes/features/intellidoc/project/[id]/+page.svelte`)
   - ✅ Document delete buttons only show for admin users
   - ✅ Uses AdminDeleteButton component

3. **AICC Template Component** (`/lib/templates/aicc-intellidoc/components/ProjectInterface.svelte`)
   - ✅ Document delete buttons only show for admin users
   - ✅ Uses AdminDeleteButton component

### Additional Considerations

#### Project Creation
- Project creation is already restricted to admin users in both frontend and backend
- Create button shows only for admin users with `{#if $isAdmin}` check

#### Document Upload
- Document upload is typically allowed for users who have access to the project
- No additional role restrictions needed for upload functionality

#### Other Admin Actions
Consider applying role-based restrictions to:
- Project settings/configuration
- User management pages
- System settings
- Bulk operations

## Best Practices

### 1. Always Use Role Checks for Destructive Actions
```svelte
<!-- ❌ Bad: No role check -->
<button on:click={deleteProject}>Delete</button>

<!-- ✅ Good: Role-based visibility -->
<AdminDeleteButton on:delete={deleteProject} />
```

### 2. Combine with Backend Security
```svelte
<!-- Frontend role check + backend API security -->
<RoleBasedAccess requiredRole="ADMIN">
  <button on:click={callAdminAPI}>Admin Action</button>
</RoleBasedAccess>
```

### 3. Provide Clear Feedback
```svelte
<!-- Show why content is hidden -->
<RoleBasedAccess 
  requiredRole="ADMIN" 
  fallback={true} 
  fallbackMessage="Administrator privileges required"
>
  <AdminPanel />
</RoleBasedAccess>
```

### 4. Use Semantic HTML
```svelte
<!-- Keep buttons semantic even when role-restricted -->
<AdminDeleteButton
  title="Delete project (requires admin role)"
  on:delete={handleDelete}
>
  Delete Project
</AdminDeleteButton>
```

## Testing Role-Based Access

### Manual Testing
1. Log in as different user roles (USER, STAFF, ADMIN)
2. Verify delete buttons only appear for admins
3. Test that non-admin API calls are rejected
4. Verify fallback messages appear when expected

### Automated Testing
```typescript
// Example test case
test('delete buttons only visible to admins', () => {
  // Mock non-admin user
  mockAuthStore({ user: { role: 'USER' } });
  render(ProjectList);
  
  // Verify delete buttons don't exist
  expect(screen.queryByTitle(/delete/i)).toBeNull();
  
  // Mock admin user
  mockAuthStore({ user: { role: 'ADMIN' } });
  render(ProjectList);
  
  // Verify delete buttons exist
  expect(screen.getByTitle(/delete/i)).toBeInTheDocument();
});
```

## Security Notes

⚠️ **Important**: Frontend role checks are for UX only. Always enforce access control on the backend:

- Frontend: Hide UI elements for better user experience
- Backend: Validate roles and permissions for security

The backend already implements proper admin-only deletion with:
- Role checking (`request.user.is_admin`)
- Password confirmation required
- Detailed audit logging
- Atomic operations with proper cleanup