<!-- src/routes/reset-password/+page.svelte -->
<script lang="ts">
  import { requestPasswordReset } from '$lib/services/api';
  import Navigation from '$lib/components/Navigation.svelte';

  let email = '';
  let loading = false;
  let submitted = false;
  let error = '';

  async function handleSubmit() {
    error = '';
    loading = true;
    
    try {
      await requestPasswordReset(email);
      submitted = true;
    } catch (err: any) {
      error = 'An error occurred. Please try again later.';
      console.error(err);
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
    <p class="mt-2 text-center text-sm text-gray-600">
      Or
      <a href="/login" class="font-medium text-blue-600 hover:text-blue-500">
        sign in to your account
      </a>
    </p>
  </div>

  <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
    <div class="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
      {#if submitted}
        <div class="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded mb-4">
          If an account exists with that email, we have sent password reset instructions.
        </div>
        <div class="text-center">
          <a href="/login" class="font-medium text-blue-600 hover:text-blue-500">
            Return to login
          </a>
        </div>
      {:else}
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
            <button
              type="submit"
              disabled={loading}
              class="w-full btn btn-primary {loading ? 'opacity-70 cursor-not-allowed' : ''}"
            >
              {loading ? 'Sending instructions...' : 'Send reset instructions'}
            </button>
          </div>
        </form>
      {/if}
    </div>
  </div>
</div>
