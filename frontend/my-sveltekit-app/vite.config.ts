import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [
    // Guard against malformed URIs from bot probes crashing the SvelteKit dev server
    {
      name: 'malformed-uri-guard',
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          try {
            decodeURI(req.url || '');
          } catch {
            // Invalid percent-encoding in URL — reject before SvelteKit sees it
            _res.statusCode = 400;
            _res.end('Bad Request');
            return;
          }
          next();
        });
      },
    },
    sveltekit(),
  ],
  
  // Server configuration with improved WebSocket handling and API proxy
  server: {
    hmr: {
      overlay: true,
      ...(process.env.ELECTRON_DEV ? {} : {
        clientPort: parseInt(process.env.HMR_CLIENT_PORT || '443'),
        protocol: process.env.HMR_PROTOCOL || 'wss',
      }),
    },
    port: 5173,
    strictPort: false,
    host: '0.0.0.0',
    allowedHosts: ['aicc.uksouth.cloudapp.azure.com'],
    // Add watch configuration to ignore node_modules
    watch: {
      ignored: ['**/node_modules/**', '**/dist/**', '**/.DS_Store']
    },
    // Proxy API calls to Django backend (development only)
    proxy: {
      '/api': {
        target: process.env.BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => {
          console.log(`🔄 Proxying: ${path} -> ${process.env.BACKEND_URL || 'http://127.0.0.1:8000'}${path}`);
          return path;
        },
        configure: (proxy, options) => {
          proxy.on('error', (err, req, res) => {
            console.log('❌ Proxy Error:', err.message);
          });
          proxy.on('proxyReq', (proxyReq, req, res) => {
            console.log('📡 Proxy Request:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('✅ Proxy Response:', proxyRes.statusCode, req.url);
          });
        }
      },
      '/ws': {
        target: process.env.BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
        secure: false,
      }
    }
  },
  
  // Updated optimizeDeps configuration with explicit exclusions
  optimizeDeps: {
    include: [
      'svelte',
      'svelte/store',
      'svelte/transition',
      'axios'
    ],
    exclude: [
      '@sveltejs/kit',
      '@sveltejs/kit/hooks',
      '@sveltejs/kit/node',
      '@sveltejs/kit/node/polyfills',
      '@sveltejs/kit/vite'
    ],
    esbuildOptions: {
      target: 'esnext'
    }
  },
  
  // Build configuration
  build: {
    reportCompressedSize: false,
    target: 'esnext',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1000
  },
  
  // Use a different cache directory
  cacheDir: '.vite_cache',
  
  // Resolve configuration
  resolve: {
    dedupe: ['svelte', 'svelte/transition', 'svelte/store']
  }
});
