<!-- src/lib/components/Navigation.svelte -->

<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { isAuthenticated, isAdmin, user, logout } from '$lib/stores/auth';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { toasts } from '$lib/stores/toast';
  import PasswordChangeModal from './PasswordChangeModal.svelte';
  
  let isMenuOpen = false;
  let isDropdownOpen = false;
  let showPasswordModal = false;
  
  // Initialize with default values in case page is not loaded yet
  $: pathname = $page?.url?.pathname || '/';
  
  // Close dropdowns when navigating to a new page
  $: if (pathname) {
    closeDropdown();
    closeMenu();
  }
  
  function handleLogout() {
    logout();
    toasts.success('Logged out successfully');
    goto('/login');
  }
  
  function toggleMenu() {
    isMenuOpen = !isMenuOpen;
  }
  
  function toggleDropdown() {
    isDropdownOpen = !isDropdownOpen;
  }
  
  function closeMenu() {
    isMenuOpen = false;
  }
  
  function closeDropdown() {
    isDropdownOpen = false;
  }
  
  // Close dropdown when clicking outside
  function handleClickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('[data-dropdown-container]')) {
      closeDropdown();
    }
  }
  
  function handleProfileClick() {
    // You can implement navigation to profile page here
    goto('/profile');
    closeDropdown();
  }
  
  function openPasswordModal() {
    showPasswordModal = true;
    closeDropdown();
  }
  
  function handlePasswordChanged() {
    // Optional: Show success message or perform any additional actions
    toasts.success('Password updated successfully');
  }
  
  // Setup click outside listener on mount
  onMount(() => {
    if (typeof document !== 'undefined') {
      document.addEventListener('click', handleClickOutside);
    }
  });
  
  // Cleanup click outside listener on destroy
  onDestroy(() => {
    if (typeof document !== 'undefined') {
      document.removeEventListener('click', handleClickOutside);
    }
  });
</script>

<nav class="nav-oxford">
  <div class="w-full px-4 sm:px-6 lg:px-8">
    <div class="flex items-center justify-between h-16">
      <div class="flex items-center">
        <div class="flex-shrink-0">
          <a href="/" class="flex items-center space-x-3">
            <img src="/logo.svg" alt="AI Competency Centre Logo" class="h-12 w-auto" />
            <span class="logo-text text-xl hidden sm:block">AI Competency Centre</span>
            <span class="logo-text text-lg block sm:hidden">AICC</span>
          </a>
        </div>
        <div class="hidden md:block">
          <div class="ml-10 flex items-baseline space-x-4">
            {#if $isAuthenticated}
              <a
                href="/features/intellidoc"
                class={pathname?.startsWith('/features/intellidoc')
                  ? 'bg-[#001122] text-white px-3 py-2 rounded-md text-sm font-medium'
                  : 'text-gray-300 hover:bg-[#003366] hover:text-white px-3 py-2 rounded-md text-sm font-medium'}
                aria-current={pathname?.startsWith('/features/intellidoc') ? 'page' : undefined}
              >
                Projects
              </a>
            {/if}
          </div>
        </div>
      </div>
      
      <!-- User avatar removed for desktop app -->
      
      <div class="-mr-2 flex md:hidden">
        <!-- Mobile menu button -->
        <button 
          type="button" 
          class="bg-[#002147] inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-white hover:bg-[#003366] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#002147] focus:ring-white" 
          aria-controls="mobile-menu" 
          aria-expanded={isMenuOpen}
          on:click={toggleMenu}
        >
          <span class="sr-only">Open main menu</span>
          <!-- Icon when menu is closed -->
          <svg 
            class={isMenuOpen ? 'hidden' : 'block'} 
            xmlns="http://www.w3.org/2000/svg" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor" 
            aria-hidden="true"
            width="24"
            height="24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <!-- Icon when menu is open -->
          <svg 
            class={isMenuOpen ? 'block' : 'hidden'} 
            xmlns="http://www.w3.org/2000/svg" 
            fill="none" 
            viewBox="0 0 24 24" 
            stroke="currentColor" 
            aria-hidden="true"
            width="24"
            height="24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  </div>

  <!-- Mobile menu, show/hide based on menu state. -->
  <div class={isMenuOpen ? 'block' : 'hidden'} id="mobile-menu">
    <div class="px-2 pt-2 pb-3 space-y-1 sm:px-3">
      {#if $isAuthenticated}
        <a 
          href="/" 
          class={pathname === '/' 
            ? 'bg-[#001122] text-white block px-3 py-2 rounded-md text-base font-medium' 
            : 'text-gray-300 hover:bg-[#003366] hover:text-white block px-3 py-2 rounded-md text-base font-medium'}
          aria-current={pathname === '/' ? 'page' : undefined}
          on:click={closeMenu}
        >
          Dashboard
        </a>
        
        {#if $isAdmin}
          <a 
            href="/admin" 
            class={pathname?.startsWith('/admin') 
              ? 'bg-[#001122] text-white block px-3 py-2 rounded-md text-base font-medium' 
              : 'text-gray-300 hover:bg-[#003366] hover:text-white block px-3 py-2 rounded-md text-base font-medium'}
            aria-current={pathname?.startsWith('/admin') ? 'page' : undefined}
            on:click={closeMenu}
          >
            Admin
          </a>
        {/if}
      {:else}
        <a 
          href="/login" 
          class={pathname === '/login' 
            ? 'bg-[#001122] text-white block px-3 py-2 rounded-md text-base font-medium' 
            : 'text-gray-300 hover:bg-[#003366] hover:text-white block px-3 py-2 rounded-md text-base font-medium'}
          aria-current={pathname === '/login' ? 'page' : undefined}
          on:click={closeMenu}
        >
          Login
        </a>
      {/if}
    </div>
    
    {#if $isAuthenticated}
      <div class="pt-4 pb-3 border-t border-gray-700">
        <div class="flex items-center px-5">
          <div class="flex-shrink-0">
            <!-- Logo in mobile menu -->
            <img src="/logo.svg" alt="AI Competency Centre Logo" class="h-12 w-auto" />
          </div>
          <div class="ml-3">
            <div class="text-base font-medium leading-none text-white">
              {$user?.first_name || ''} {$user?.last_name || ''}
            </div>
            <div class="text-sm font-medium leading-none text-gray-400 mt-1">
              {$user?.email || ''}
            </div>
          </div>
        </div>
        <div class="mt-3 px-2 space-y-1">
          
          {#if $isAdmin}
            <a 
              href="/admin" 
              class="block px-3 py-2 rounded-md text-base font-medium text-gray-400 hover:text-white hover:bg-[#003366]"
              on:click={closeMenu}
            >
              Admin Dashboard
            </a>
          {/if}
          
          <button 
            on:click={handleProfileClick}
            class="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-gray-400 hover:text-white hover:bg-[#003366]"
          >
            <i class="fas fa-user mr-2"></i>
            Profile
          </button>
          
          <button 
            on:click={() => { openPasswordModal(); closeMenu(); }}
            class="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-gray-400 hover:text-white hover:bg-[#003366]"
          >
            <i class="fas fa-key mr-2"></i>
            Change Password
          </button>
          
          <button 
            on:click={handleLogout}
            class="block w-full text-left px-3 py-2 rounded-md text-base font-medium text-gray-400 hover:text-white hover:bg-[#003366]"
          >
            <i class="fas fa-sign-out-alt mr-2"></i>
            Sign out
          </button>
        </div>
      </div>
    {/if}
  </div>
</nav>

<!-- Password Change Modal -->
<PasswordChangeModal 
  bind:isOpen={showPasswordModal}
  on:passwordChanged={handlePasswordChanged}
  on:close={() => showPasswordModal = false}
/>
