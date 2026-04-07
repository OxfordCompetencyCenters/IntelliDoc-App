// src/hooks.server.ts
import type { Handle } from '@sveltejs/kit';

// This server-side hook can be used to validate session cookies
// For our app, we will handle auth on the client side with JWT

export const handle: Handle = async ({ event, resolve }) => {
  return await resolve(event);
};
