<!-- Password Change Modal Component -->
<!-- src/lib/components/PasswordChangeModal.svelte -->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { toasts } from '$lib/stores/toast';
  import { user } from '$lib/stores/auth';
  
  export let isOpen = false;
  
  const dispatch = createEventDispatcher();
  
  // Form state
  let currentPassword = '';
  let newPassword = '';
  let confirmPassword = '';
  let isSubmitting = false;
  let showCurrentPassword = false;
  let showNewPassword = false;
  let showConfirmPassword = false;
  
  // Validation state
  let errors: Record<string, string> = {};
  
  // Password strength indicators
  let passwordStrength = 0;
  let strengthText = '';
  let strengthColor = '';
  
  $: if (newPassword) {
    calculatePasswordStrength(newPassword);
  }
  
  function calculatePasswordStrength(password: string) {
    let strength = 0;
    let requirements = [];
    
    if (password.length >= 8) {
      strength += 20;
      requirements.push('✓ At least 8 characters');
    } else {
      requirements.push('✗ At least 8 characters');
    }
    
    if (/[a-z]/.test(password)) {
      strength += 20;
      requirements.push('✓ Lowercase letter');
    } else {
      requirements.push('✗ Lowercase letter');
    }
    
    if (/[A-Z]/.test(password)) {
      strength += 20;
      requirements.push('✓ Uppercase letter');
    } else {
      requirements.push('✗ Uppercase letter');
    }
    
    if (/\d/.test(password)) {
      strength += 20;
      requirements.push('✓ Number');
    } else {
      requirements.push('✗ Number');
    }
    
    if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
      strength += 20;
      requirements.push('✓ Special character');
    } else {
      requirements.push('✗ Special character');
    }
    
    passwordStrength = strength;
    
    if (strength < 40) {
      strengthText = 'Weak';
      strengthColor = '#ef4444';
    } else if (strength < 80) {
      strengthText = 'Fair';
      strengthColor = '#f59e0b';
    } else {
      strengthText = 'Strong';
      strengthColor = '#10b981';
    }
  }
  
  function validateForm() {
    errors = {};
    
    if (!currentPassword.trim()) {
      errors.currentPassword = 'Current password is required';
    }
    
    if (!newPassword.trim()) {
      errors.newPassword = 'New password is required';
    } else if (newPassword.length < 8) {
      errors.newPassword = 'Password must be at least 8 characters long';
    } else if (passwordStrength < 60) {
      errors.newPassword = 'Password is too weak. Please include uppercase, lowercase, numbers, and special characters.';
    }
    
    if (!confirmPassword.trim()) {
      errors.confirmPassword = 'Please confirm your new password';
    } else if (newPassword !== confirmPassword) {
      errors.confirmPassword = 'Passwords do not match';
    }
    
    if (currentPassword === newPassword) {
      errors.newPassword = 'New password must be different from current password';
    }
    
    return Object.keys(errors).length === 0;
  }
  
  async function handleSubmit() {
    if (!validateForm()) {
      return;
    }
    
    isSubmitting = true;
    
    try {
      // Get auth token from local storage
      const authStore = JSON.parse(localStorage.getItem('auth') || '{}');
      const token = authStore.token;
      
      if (!token) {
        toasts.error('Authentication required. Please log in again.');
        return;
      }
      
      // Call API to change password
      const response = await fetch('/api/change-password/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        toasts.success(data.message || 'Password changed successfully');
        closeModal();
        dispatch('passwordChanged');
      } else {
        // Handle specific error cases based on backend response
        if (data.errors) {
          // Handle validation errors from Django serializer
          if (data.errors.current_password) {
            errors.currentPassword = Array.isArray(data.errors.current_password) 
              ? data.errors.current_password[0] 
              : data.errors.current_password;
          }
          if (data.errors.new_password) {
            errors.newPassword = Array.isArray(data.errors.new_password) 
              ? data.errors.new_password[0] 
              : data.errors.new_password;
          }
          if (data.errors.non_field_errors) {
            toasts.error(Array.isArray(data.errors.non_field_errors) 
              ? data.errors.non_field_errors[0] 
              : data.errors.non_field_errors);
          }
        } else {
          toasts.error(data.detail || data.message || 'Failed to change password');
        }
      }
    } catch (error) {
      console.error('Password change error:', error);
      toasts.error('Failed to change password. Please try again.');
    } finally {
      isSubmitting = false;
    }
  }
  
  function closeModal() {
    isOpen = false;
    // Reset form
    currentPassword = '';
    newPassword = '';
    confirmPassword = '';
    errors = {};
    showCurrentPassword = false;
    showNewPassword = false;
    showConfirmPassword = false;
    dispatch('close');
  }
  
  function togglePasswordVisibility(field: string) {
    switch (field) {
      case 'current':
        showCurrentPassword = !showCurrentPassword;
        break;
      case 'new':
        showNewPassword = !showNewPassword;
        break;
      case 'confirm':
        showConfirmPassword = !showConfirmPassword;
        break;
    }
  }
</script>

{#if isOpen}
  <!-- Modal Overlay -->
  <div 
    class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
    on:click={closeModal}
    role="dialog"
    aria-modal="true"
    aria-labelledby="password-change-title"
  >
    <!-- Modal Content -->
    <div 
      class="bg-white rounded-lg shadow-xl max-w-md w-full max-h-screen overflow-y-auto"
      on:click|stopPropagation
    >
      <!-- Modal Header -->
      <div class="bg-oxford-blue text-white p-6 rounded-t-lg">
        <div class="flex items-center justify-between">
          <h2 id="password-change-title" class="text-xl font-semibold flex items-center text-white">
            <i class="fas fa-key mr-2 text-white"></i>
            Change Password
          </h2>
          <button 
            on:click={closeModal}
            class="text-white hover:text-gray-300 transition-colors"
            aria-label="Close modal"
          >
            <i class="fas fa-times text-xl text-white"></i>
          </button>
        </div>
        <p class="text-white text-sm mt-2">
          Update your password for {$user?.email}
        </p>
      </div>
      
      <!-- Modal Body -->
      <form on:submit|preventDefault={handleSubmit} class="p-6 space-y-4">
        <!-- Current Password -->
        <div class="form-group">
          <label for="currentPassword" class="block text-sm font-medium text-gray-700 mb-1">
            Current Password
          </label>
          <div class="relative">
            <input
              id="currentPassword"
              type={showCurrentPassword ? 'text' : 'password'}
              bind:value={currentPassword}
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-oxford-blue focus:border-transparent"
              placeholder="Enter your current password"
              required
            />
            <button
              type="button"
              class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
              on:click={() => togglePasswordVisibility('current')}
            >
              <i class="fas {showCurrentPassword ? 'fa-eye-slash' : 'fa-eye'}"></i>
            </button>
          </div>
          {#if errors.currentPassword}
            <p class="text-red-600 text-sm mt-1">
              <i class="fas fa-exclamation-circle mr-1"></i>
              {errors.currentPassword}
            </p>
          {/if}
        </div>
        
        <!-- New Password -->
        <div class="form-group">
          <label for="newPassword" class="block text-sm font-medium text-gray-700 mb-1">
            New Password
          </label>
          <div class="relative">
            <input
              id="newPassword"
              type={showNewPassword ? 'text' : 'password'}
              bind:value={newPassword}
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-oxford-blue focus:border-transparent"
              placeholder="Enter your new password"
              required
            />
            <button
              type="button"
              class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
              on:click={() => togglePasswordVisibility('new')}
            >
              <i class="fas {showNewPassword ? 'fa-eye-slash' : 'fa-eye'}"></i>
            </button>
          </div>
          
          <!-- Password Strength Indicator -->
          {#if newPassword}
            <div class="mt-2">
              <div class="flex items-center justify-between text-sm">
                <span class="text-gray-600">Password Strength:</span>
                <span class="font-medium" style="color: {strengthColor}">{strengthText}</span>
              </div>
              <div class="w-full bg-gray-200 rounded-full h-2 mt-1">
                <div 
                  class="h-2 rounded-full transition-all duration-300"
                  style="width: {passwordStrength}%; background-color: {strengthColor}"
                ></div>
              </div>
            </div>
          {/if}
          
          {#if errors.newPassword}
            <p class="text-red-600 text-sm mt-1">
              <i class="fas fa-exclamation-circle mr-1"></i>
              {errors.newPassword}
            </p>
          {/if}
        </div>
        
        <!-- Confirm Password -->
        <div class="form-group">
          <label for="confirmPassword" class="block text-sm font-medium text-gray-700 mb-1">
            Confirm New Password
          </label>
          <div class="relative">
            <input
              id="confirmPassword"
              type={showConfirmPassword ? 'text' : 'password'}
              bind:value={confirmPassword}
              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-oxford-blue focus:border-transparent"
              placeholder="Confirm your new password"
              required
            />
            <button
              type="button"
              class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
              on:click={() => togglePasswordVisibility('confirm')}
            >
              <i class="fas {showConfirmPassword ? 'fa-eye-slash' : 'fa-eye'}"></i>
            </button>
          </div>
          {#if errors.confirmPassword}
            <p class="text-red-600 text-sm mt-1">
              <i class="fas fa-exclamation-circle mr-1"></i>
              {errors.confirmPassword}
            </p>
          {/if}
        </div>
        
        <!-- Password Requirements -->
        <div class="bg-gray-50 rounded-md p-3">
          <h4 class="text-sm font-medium text-gray-700 mb-2">Password Requirements:</h4>
          <ul class="text-xs text-gray-600 space-y-1">
            <li class="flex items-center">
              <i class="fas {newPassword.length >= 8 ? 'fa-check text-green-500' : 'fa-times text-red-500'} mr-2"></i>
              At least 8 characters
            </li>
            <li class="flex items-center">
              <i class="fas {/[a-z]/.test(newPassword) ? 'fa-check text-green-500' : 'fa-times text-red-500'} mr-2"></i>
              Lowercase letter
            </li>
            <li class="flex items-center">
              <i class="fas {/[A-Z]/.test(newPassword) ? 'fa-check text-green-500' : 'fa-times text-red-500'} mr-2"></i>
              Uppercase letter
            </li>
            <li class="flex items-center">
              <i class="fas {/\d/.test(newPassword) ? 'fa-check text-green-500' : 'fa-times text-red-500'} mr-2"></i>
              Number
            </li>
            <li class="flex items-center">
              <i class="fas {/[!@#$%^&*(),.?":{}|<>]/.test(newPassword) ? 'fa-check text-green-500' : 'fa-times text-red-500'} mr-2"></i>
              Special character
            </li>
          </ul>
        </div>
        
        <!-- Modal Footer -->
        <div class="flex space-x-3 pt-4">
          <button
            type="button"
            on:click={closeModal}
            class="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-gray-500 transition-colors"
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="submit"
            class="flex-1 px-4 py-2 bg-oxford-blue text-white rounded-md hover:bg-oxford-blue-dark focus:outline-none focus:ring-2 focus:ring-oxford-blue focus:ring-offset-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={isSubmitting || passwordStrength < 60}
          >
            {#if isSubmitting}
              <i class="fas fa-spinner fa-spin mr-2"></i>
              Changing...
            {:else}
              <i class="fas fa-save mr-2"></i>
              Change Password
            {/if}
          </button>
        </div>
      </form>
    </div>
  </div>
{/if}

<style>
  .form-group {
    @apply mb-4;
  }
  
  /* Oxford Blue theme colors */
  .bg-oxford-blue {
    background-color: #002147;
  }
  
  .text-oxford-blue {
    color: #002147;
  }
  
  .ring-oxford-blue {
    --tw-ring-color: #002147;
  }
  
  .focus\:ring-oxford-blue:focus {
    --tw-ring-color: #002147;
  }
  
  .bg-oxford-blue-dark {
    background-color: #001122;
  }
  
  .hover\:bg-oxford-blue-dark:hover {
    background-color: #001122;
  }
</style>