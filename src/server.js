const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');

function createServer(djangoPort, staticDir) {
  const app = express();
  const backendUrl = `http://127.0.0.1:${djangoPort}`;

  // Proxy /api/** and /admin/** to Django — full path preserved
  app.use(createProxyMiddleware({
    target: backendUrl,
    changeOrigin: true,
    pathFilter: ['/api/**', '/admin/**'],
    timeout: 1500000,
    proxyTimeout: 1500000,
    onError: (err, req, res) => {
      console.error('Proxy error:', err.message);
      if (!res.headersSent) {
        res.status(502).json({
          error: 'Backend Unavailable',
          message: `Cannot connect to backend at ${backendUrl}`,
        });
      }
    },
  }));

  // WebSocket proxy for /ws/**
  const wsProxy = createProxyMiddleware({
    target: backendUrl,
    changeOrigin: true,
    pathFilter: '/ws/**',
    ws: true,
    logLevel: 'warn',
  });
  app.use(wsProxy);

  // Proxy /ollama/** to Ollama Docker container
  app.use(createProxyMiddleware({
    target: 'http://127.0.0.1:11434',
    changeOrigin: true,
    pathFilter: '/ollama/**',
    pathRewrite: { '^/ollama': '' },  // Strip /ollama prefix: /ollama/api/tags → /api/tags
    timeout: 600000,  // 10 min for model downloads
    proxyTimeout: 600000,
    onError: (err, req, res) => {
      if (!res.headersSent) {
        res.status(502).json({ error: 'Ollama unavailable', message: 'Docker container may not be running' });
      }
    },
  }));

  // Serve static SvelteKit build
  app.use(express.static(staticDir));

  // SPA fallback
  app.get('*', (req, res) => {
    res.sendFile(path.join(staticDir, '200.html'));
  });

  return new Promise((resolve) => {
    const server = app.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      console.log(`Express proxy server listening on http://127.0.0.1:${port}`);
      resolve({ server, port });
    });
    server.on('upgrade', wsProxy.upgrade);
  });
}

module.exports = { createServer };
