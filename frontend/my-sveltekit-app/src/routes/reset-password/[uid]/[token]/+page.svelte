<!-- src/routes/reset-password/[uid]/[token]/+page.svelte -->
<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { confirmPasswordReset } from '$lib/services/api';
  import Navigation from '$lib/components/Navigation.svelte';

  const uid = $page.params.uid;
  const token = $page.params.token;
  
  let newPassword = '';
  let confirmPassword = '';
  let loading = false;
  let success = false;
  let error = '';

  async function handleSubmit() {
    error = '';
    loading = true;
    
    if (newPassword !== confirmPassword) {
      error = 'Passwords do not match';
      loading = false;
      return;
    }
    
    try {
      await confirmPasswordReset({
        uid,
        token,
        new_password: newPassword,
        new_password2: confirmPassword
      });
      success = true;
      setTimeout(() => {
        goto('/login');
      }, 3000);
    } catch (err: any) {
      if (err.response?.data?.detail) {
        error = err.response.data.detail;
      } else {
        error = 'An error occurred. Please try again.';
      }
    } finally {
      loading = false;
    }
  }
</script>

<Navigation />

<div class="min-h-screen bg-gray-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
  <div class="sm:mx-auto sm:w-full sm:max-w-md">
    <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
      Reset your password
    </h2>
  </div>

  <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
    <div class="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
      {#if success}
        <div class="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mb-4">
          Your password has been reset successfully. Redirecting to login...
        </div>
      {:else}
        <form on:submit|preventDefault={handleSubmit} class="space-y-6">
          {#if error}
            <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          {/if}
          
          <div>
            <label for="new-password" class="form-label">
              New password
            </label>
            <div class="mt-1">
              <input
                id="new-password"
                name="new-password"
                type="password"
                autocomplete="new-password"
                required
                bind:value={newPassword}
                class="form-input"
              />
            </div>
          </div>

          <div>
            <label for="confirm-password" class="form-label">
              Confirm new password
            </label>
            <div class="mt-1">
              <input
                id="confirm-password"
                name="confirm-password"
                type="password"
                autocomplete="new-password"
                required
                bind:value={confirmPassword}
                class="form-input"
              />
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={loading}
              class="w-full btn btn-primary {loading ? 'opacity-70 cursor-not-allowed' : ''}"
            >
              {loading ? 'Resetting password...' : 'Reset password'}
            </button>
          </div>
        </form>
      {/if}
    </div>
  </div>
</div>
