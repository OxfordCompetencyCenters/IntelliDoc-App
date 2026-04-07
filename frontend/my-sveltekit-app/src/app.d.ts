// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};

interface ElectronAPI {
	selectFiles: (options?: { filters?: Array<{ name: string; extensions: string[] }> }) => Promise<string[] | null>;
	selectDirectory: () => Promise<string | null>;
	getConfig: (key: string) => Promise<any>;
	setConfig: (key: string, value: any) => Promise<void>;
	getAppVersion: () => Promise<string>;
	checkBackend: () => Promise<{ ok: boolean; status?: number; error?: string }>;
	platform: string;
	isElectron: boolean;
}

declare global {
	interface Window {
		electronAPI?: ElectronAPI;
	}
}
