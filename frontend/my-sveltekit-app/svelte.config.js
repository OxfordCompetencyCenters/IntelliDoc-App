import adapterNode from '@sveltejs/adapter-node';
import adapterStatic from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const isElectron = process.env.ADAPTER === 'static';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),

	kit: {
		adapter: isElectron
			? adapterStatic({
				pages: 'build-static',
				assets: 'build-static',
				fallback: '200.html',
				precompress: false,
				strict: false,
			})
			: adapterNode({
				out: 'build',
				precompress: false,
				envPrefix: ''
			})
	}
};

export default config;
