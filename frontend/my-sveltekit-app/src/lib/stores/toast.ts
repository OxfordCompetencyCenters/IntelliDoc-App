import { writable } from 'svelte/store';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

// Generate a simple unique ID without relying on uuid package
function generateId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substring(2);
}

function createToastStore() {
  const { subscribe, update } = writable<Toast[]>([]);

  function addToast(type: ToastType, message: string, duration: number = 5000) {
    const id = generateId();
    update(toasts => [
      ...toasts,
      { id, type, message, duration }
    ]);

    // Auto-remove toast after duration
    if (duration !== Infinity) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }

    return id;
  }

  function removeToast(id: string) {
    update(toasts => toasts.filter(t => t.id !== id));
  }

  return {
    subscribe,
    success: (message: string, duration?: number) => addToast('success', message, duration),
    error: (message: string, duration?: number) => addToast('error', message, duration),
    info: (message: string, duration?: number) => addToast('info', message, duration),
    warning: (message: string, duration?: number) => addToast('warning', message, duration),
    remove: removeToast
  };
}

export const toasts = createToastStore();
