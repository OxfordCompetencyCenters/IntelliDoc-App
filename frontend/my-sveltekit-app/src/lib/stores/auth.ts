// src/lib/stores/auth.ts — Desktop Electron (auto-login)
import { writable, derived } from 'svelte/store';
import { browser } from '$app/environment';
import type { User } from '$lib/types';

// Try to restore from localStorage (may have a valid token from previous session)
const storedAuth = browser ? localStorage.getItem('auth') : null;
const parsed = storedAuth ? JSON.parse(storedAuth) : null;

const initialAuth = (parsed && parsed.token && parsed.token !== 'desktop-mode')
  ? parsed
  : {
      user: { id: 1, email: 'desktop@localhost', role: 'ADMIN', first_name: 'Desktop', last_name: 'User' },
      token: null,
      refreshToken: null,
      isAuthenticated: true,  // Always true for desktop
    };

// Create the store
const authStore = writable(initialAuth);

// Update localStorage when store changes
if (browser) {
  authStore.subscribe(value => {
    localStorage.setItem('auth', JSON.stringify(value));
  });

  // Auto-login: fetch real JWT from desktop-auth endpoint
  if (!initialAuth.token) {
    fetch('/api/desktop-auth/')
      .then(r => r.json())
      .then(data => {
        if (data.access) {
          authStore.set({
            user: data.user,
            token: data.access,
            refreshToken: data.refresh,
            isAuthenticated: true,
          });
          console.log('Desktop auto-login successful');
        }
      })
      .catch(err => console.warn('Desktop auto-login failed:', err));
  }
}

// Derived stores for convenience
export const user = derived(authStore, $auth => $auth.user);
export const isAuthenticated = derived(authStore, $auth => $auth.isAuthenticated);
export const isAdmin = derived(authStore, $auth => $auth.user?.role === 'ADMIN');

// Auth actions
export const login = (userData: User, token: string, refreshToken: string) => {
  authStore.set({
    user: userData,
    token,
    refreshToken,
    isAuthenticated: true,
  });
};

export const logout = () => {
  // Desktop: don't actually clear auth, just refresh token
  fetch('/api/desktop-auth/')
    .then(r => r.json())
    .then(data => {
      if (data.access) {
        authStore.set({
          user: data.user,
          token: data.access,
          refreshToken: data.refresh,
          isAuthenticated: true,
        });
      }
    })
    .catch(() => {});
};

export const updateUser = (userData: Partial<User>) => {
  authStore.update(state => ({
    ...state,
    user: { ...state.user, ...userData },
  }));
};

export default authStore;
