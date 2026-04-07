<!-- src/routes/login/+page.svelte -->
<script lang="ts">
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';
  import { loginUser } from '$lib/services/api';
  import { login, isAuthenticated } from '$lib/stores/auth';


  let email = '';
  let password = '';
  let loading = false;
  let error = '';

  $: if ($isAuthenticated) {
    goto('/');
  }

  async function handleSubmit() {
    error = '';
    loading = true;
    
    try {
      const response = await loginUser(email, password);
      login(response.user, response.access, response.refresh);
      goto('/');
    } catch (err: any) {
      if (err.response?.data) {
        error = err.response.data.detail || 'Login failed. Please check your credentials.';
      } else {
        error = 'Network error. Please try again later.';
      }
    } finally {
      loading = false;
    }
  }
</script>



<div class="min-h-screen bg-gray-100 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
  <div class="sm:mx-auto sm:w-full sm:max-w-md">
    <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
      Sign in to your account
    </h2>
  </div>

  <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
    <div class="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
      <form on:submit|preventDefault={handleSubmit} class="space-y-6">
        {#if error}
          <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        {/if}
        
        <div>
          <label for="email" class="form-label">
            Email address
          </label>
          <div class="mt-1">
            <input
              id="email"
              name="email"
              type="email"
              autocomplete="email"
              required
              bind:value={email}
              class="form-input"
            />
          </div>
        </div>

        <div>
          <label for="password" class="form-label">
            Password
          </label>
          <div class="mt-1">
            <input
              id="password"
              name="password"
              type="password"
              autocomplete="current-password"
              required
              bind:value={password}
              class="form-input"
            />
          </div>
        </div>

        <div class="flex items-center justify-between">
          <div class="flex items-center">
            <input
              id="remember-me"
              name="remember-me"
              type="checkbox"
              class="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
            />
            <label for="remember-me" class="ml-2 block text-sm text-gray-900">
              Remember me
            </label>
          </div>

          <div class="text-sm">
            <a href="/reset-password" class="font-medium text-blue-600 hover:text-blue-500">
              Forgot your password?
            </a>
          </div>
        </div>

        <div>
          <button
            type="submit"
            disabled={loading}
            class="w-full btn btn-primary {loading ? 'opacity-70 cursor-not-allowed' : ''}"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </div>
      </form>
    </div>
  </div>
</div>
