# api/permissions.py
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework import status

class IsAdminUser(permissions.BasePermission):
    """
    Custom permission to only allow admin users to access the view.
    """
    def has_permission(self, request, view):
        is_admin = hasattr(request.user, 'is_admin') and request.user.is_admin
        print(f"IsAdminUser check for {request.user.email} on {view.action}: {is_admin}")
        return request.user and is_admin

class IsAdminUserForDeletion(permissions.BasePermission):
    """
    Custom permission specifically for project deletion operations.
    Ensures only admin users can delete projects and provides detailed error messages.
    """
    def has_permission(self, request, view):
        # Only check for DELETE operations or destroy actions
        if request.method == 'DELETE' or (hasattr(view, 'action') and view.action == 'destroy'):
            # Must be authenticated
            if not request.user or not request.user.is_authenticated:
                return False
            
            # Must be admin user
            is_admin = hasattr(request.user, 'is_admin') and request.user.is_admin
            if not is_admin:
                print(f"🚫 PERMISSION: Non-admin user {request.user.email} attempted project deletion")
                return False
            
            print(f"✅ PERMISSION: Admin user {request.user.email} authorized for project deletion")
            return True
        
        # For non-deletion operations, use standard authenticated permission
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # For object-level permissions on deletion
        if request.method == 'DELETE' or (hasattr(view, 'action') and view.action == 'destroy'):
            is_admin = hasattr(request.user, 'is_admin') and request.user.is_admin
            if not is_admin:
                print(f"🚫 PERMISSION: Non-admin user {request.user.email} attempted to delete project {obj.name}")
                return False
            
            print(f"✅ PERMISSION: Admin user {request.user.email} authorized to delete project {obj.name}")
            return True
        
        return True
