// src/routes/+layout.ts — Electron Desktop (no login required)
import { browser } from '$app/environment';
import type { LayoutLoad } from './$types';

export const ssr = false;

export const load: LayoutLoad = async ({ url }) => {
    if (!browser) {
        return { isAuthenticated: true, user: null, url: url?.pathname || '/' };
    }

    // Desktop app: always authenticated, no login required
    const desktopUser = {
        id: 1,
        username: 'desktop-user',
        email: 'user@localhost',
        role: 'ADMIN',
        first_name: 'Desktop',
        last_name: 'User',
    };

    return {
        isAuthenticated: true,
        user: desktopUser,
        url: url?.pathname || '/'
    };
};
