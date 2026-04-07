const {
  app,
  BrowserWindow,
  ipcMain,
  dialog,
  shell,
  Menu,
} = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, execSync } = require('child_process');
const http = require('http');
const { checkForUpdates, startAutoUpdateChecks, stopAutoUpdateChecks } = require('./updater');

// ── Globals ──────────────────────────────────────────────────────────────────

let mainWindow = null;
let splashWindow = null;
let djangoProcess = null;
let expressServer = null;
let store = null; // electron-store instance (lazy-loaded, ESM module)
let ollamaRunning = false;
let isQuitting = false;

const isDev = !!process.env.ELECTRON_DEV || !app.isPackaged;

// ── Splash Screen ───────────────────────────────────────────────────────────

const SPLASH_HTML = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: linear-gradient(135deg, #001a38 0%, #002147 40%, #003366 100%);
    color: #fff;
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    -webkit-app-region: drag;
    user-select: none;
    overflow: hidden;
  }
  .logo { font-size: 32px; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; }
  .subtitle { font-size: 13px; color: #8ab4f8; margin-bottom: 32px; letter-spacing: 0.5px; }
  .progress-wrap {
    width: 280px;
    margin-bottom: 16px;
  }
  .progress-bar {
    width: 100%;
    height: 4px;
    background: rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    width: 0%;
    background: linear-gradient(90deg, #8ab4f8, #4d9fff);
    border-radius: 2px;
    transition: width 0.4s ease;
  }
  .progress-label {
    display: flex;
    justify-content: space-between;
    margin-top: 6px;
    font-size: 11px;
    color: rgba(255,255,255,0.5);
  }
  #status {
    font-size: 13px;
    color: rgba(255,255,255,0.7);
    text-align: center;
    min-height: 20px;
  }
  .footer {
    position: absolute;
    bottom: 16px;
    font-size: 11px;
    color: rgba(255,255,255,0.3);
  }
</style>
</head>
<body>
  <div class="logo">AICC IntelliDoc</div>
  <div class="subtitle">AI Document Analysis Platform</div>
  <div class="progress-wrap">
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
    <div class="progress-label"><span id="status">Initializing...</span><span id="percent">0%</span></div>
  </div>
  <div class="footer">AI Competency Centre, University of Oxford</div>
</body>
</html>`;

function createSplashWindow() {
  const splash = new BrowserWindow({
    width: 480,
    height: 320,
    frame: false,
    transparent: false,
    alwaysOnTop: true,
    resizable: false,
    center: true,
    skipTaskbar: false,
    backgroundColor: '#002147',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: true,
  });
  splash.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(SPLASH_HTML)}`);
  return splash;
}

function updateSplash(message, percent) {
  if (splashWindow && !splashWindow.isDestroyed()) {
    const pct = Math.min(100, Math.max(0, Math.round(percent || 0)));
    splashWindow.webContents.executeJavaScript(`
      document.getElementById('status').innerText = ${JSON.stringify(message)};
      document.getElementById('percent').innerText = '${pct}%';
      document.getElementById('progressFill').style.width = '${pct}%';
    `).catch(() => {});
  }
}

// ── Single Instance Lock ─────────────────────────────────────────────────────

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Lazily initialise electron-store (it is an ESM-only package from v9+).
 * Returns a Promise that resolves to the Store instance.
 */
async function getStore() {
  if (store) return store;
  const Store = (await import('electron-store')).default;
  store = new Store({
    defaults: {
      djangoPort: 8000,
      windowBounds: { width: 1400, height: 900 },
    },
  });
  return store;
}

/**
 * Parse a .env file and return a plain object of key=value pairs.
 */
function loadEnvFile(envPath) {
  const env = {};
  if (!fs.existsSync(envPath)) return env;
  const lines = fs.readFileSync(envPath, 'utf8').split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    let value = trimmed.slice(eqIdx + 1).trim();
    // Strip surrounding quotes
    if ((value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

/**
 * Run Django migrations asynchronously (non-blocking).
 */
function runMigrations(pythonCmd, backendDir, envVars) {
  console.log('Running Django migrations...');
  return new Promise((resolve) => {
    const child = spawn(
      pythonCmd,
      [path.join(backendDir, 'manage.py'), 'migrate', '--no-input'],
      {
        cwd: backendDir,
        env: { ...process.env, ...envVars, PYTHONUNBUFFERED: '1', DATA_DIR: app.getPath('userData') },
        stdio: ['pipe', 'pipe', 'pipe'],
      }
    );
    child.stdout.on('data', (d) => process.stdout.write(`[migrate] ${d}`));
    child.stderr.on('data', (d) => process.stderr.write(`[migrate] ${d}`));
    child.on('close', (code) => {
      console.log(`Migrations finished (exit code ${code}).`);
      resolve();
    });
    child.on('error', (err) => {
      console.error('Migration failed:', err.message);
      resolve(); // non-fatal
    });
  });
}

/**
 * Locate a working Python executable.
 * Returns the command string or throws if none found.
 */
function findPython() {
  const candidates = ['python3', 'python'];
  for (const cmd of candidates) {
    try {
      const version = execSync(`${cmd} --version`, {
        encoding: 'utf8',
        timeout: 5000,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      console.log(`Found Python: ${cmd} (${version.trim()})`);
      return cmd;
    } catch {
      // try next candidate
    }
  }
  throw new Error(
    'Python not found. Please install Python 3.10+ and ensure it is on your PATH.'
  );
}

/**
 * Poll a URL until it responds (or give up after maxRetries).
 */
function waitForUrl(url, { interval = 500, maxRetries = 60 } = {}) {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    function poll() {
      attempts++;
      const req = http.get(url, (res) => {
        // Any response (even 4xx) means the server is alive.
        res.resume();
        resolve();
      });
      req.on('error', () => {
        if (attempts >= maxRetries) {
          reject(
            new Error(
              `Backend did not become ready after ${maxRetries} attempts (${url})`
            )
          );
        } else {
          setTimeout(poll, interval);
        }
      });
      req.setTimeout(2000, () => {
        req.destroy();
        if (attempts >= maxRetries) {
          reject(
            new Error(
              `Backend did not become ready after ${maxRetries} attempts (${url})`
            )
          );
        } else {
          setTimeout(poll, interval);
        }
      });
    }

    poll();
  });
}

/**
 * Kill any existing process listening on the given port.
 * Prevents "address already in use" when restarting the app.
 */
function killProcessOnPort(port) {
  try {
    if (process.platform === 'win32') {
      execSync(`for /f "tokens=5" %a in ('netstat -aon ^| findstr :${port}') do taskkill /F /PID %a`, { stdio: 'pipe', timeout: 5000 });
    } else {
      const pid = execSync(`lsof -ti :${port}`, { encoding: 'utf8', timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] }).trim();
      if (pid) {
        console.log(`Killing existing process on port ${port} (PID: ${pid})`);
        process.kill(parseInt(pid), 'SIGKILL');
      }
    }
  } catch {
    // No process on port — fine
  }
}

/**
 * Spawn the Django development server as a child process.
 * On POSIX systems, spawns with `detached: true` so we can kill the entire
 * process group on shutdown.
 */
function spawnDjango(pythonCmd, djangoPort, backendDir) {
  // Kill any stale Django on this port from a previous crashed session
  killProcessOnPort(djangoPort);
  const managePy = path.join(backendDir, 'manage.py');
  const useDetached = process.platform !== 'win32';

  console.log(`Starting Django: ${pythonCmd} ${managePy} runserver 127.0.0.1:${djangoPort} --noreload`);

  const child = spawn(
    pythonCmd,
    [managePy, 'runserver', `127.0.0.1:${djangoPort}`, '--noreload'],
    {
      cwd: backendDir,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        DATA_DIR: app.getPath('userData'),
      },
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: useDetached,
    }
  );

  child.stdout.on('data', (data) => {
    process.stdout.write(`[django] ${data}`);
  });

  child.stderr.on('data', (data) => {
    process.stderr.write(`[django] ${data}`);
  });

  child.on('error', (err) => {
    console.error('Failed to start Django process:', err.message);
  });

  child.on('exit', (code, signal) => {
    console.log(`Django process exited (code=${code}, signal=${signal})`);
    djangoProcess = null;
  });

  return child;
}

/**
 * Kill the Django child process tree.
 */
function killDjango() {
  if (!djangoProcess) return;
  try {
    console.log('Stopping Django process...');
    // On POSIX, kill the process group to clean up any children
    if (process.platform !== 'win32') {
      process.kill(-djangoProcess.pid, 'SIGTERM');
    } else {
      djangoProcess.kill('SIGTERM');
    }
  } catch (err) {
    // Process may already be gone
    console.warn('Error killing Django process:', err.message);
  }
  djangoProcess = null;
}

/**
 * Check if Docker is available on the system.
 */
function checkDocker() {
  try {
    execSync('docker info', { encoding: 'utf8', timeout: 10000, stdio: ['pipe', 'pipe', 'pipe'] });
    console.log('Docker is available');
    return true;
  } catch {
    console.warn('Docker not available - Ollama (local AI) will be unavailable');
    return false;
  }
}

/**
 * Start the Ollama Docker container (create if needed, start if stopped).
 */
async function startOllamaContainer() {
  try {
    // Check if container already running
    const running = execSync(
      'docker ps --filter name=aicc-ollama --format "{{.Status}}"',
      { encoding: 'utf8', timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] }
    ).trim();

    if (running) {
      console.log('Ollama container already running');
      return true;
    }

    // Check if container exists but stopped
    const exists = execSync(
      'docker ps -a --filter name=aicc-ollama --format "{{.Status}}"',
      { encoding: 'utf8', timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] }
    ).trim();

    if (exists) {
      console.log('Starting existing Ollama container...');
      execSync('docker start aicc-ollama', { encoding: 'utf8', timeout: 30000, stdio: ['pipe', 'pipe', 'pipe'] });
    } else {
      console.log('Creating new Ollama container...');
      execSync(
        'docker run -d --name aicc-ollama -p 11434:11434 -v aicc-ollama-models:/root/.ollama --restart unless-stopped ollama/ollama',
        { encoding: 'utf8', timeout: 120000, stdio: ['pipe', 'pipe', 'pipe'] }
      );
    }

    // Wait for Ollama to be ready
    await waitForUrl('http://127.0.0.1:11434/', { interval: 1000, maxRetries: 30 });
    console.log('Ollama container is ready');
    return true;
  } catch (err) {
    console.error('Failed to start Ollama container:', err.message);
    return false;
  }
}

// ── Application Menu ─────────────────────────────────────────────────────────

function buildAppMenu() {
  const isMac = process.platform === 'darwin';

  const template = [
    // macOS app menu
    ...(isMac
      ? [
          {
            label: app.name,
            submenu: [
              { role: 'about' },
              { type: 'separator' },
              { role: 'services' },
              { type: 'separator' },
              { role: 'hide' },
              { role: 'hideOthers' },
              { role: 'unhide' },
              { type: 'separator' },
              { role: 'quit' },
            ],
          },
        ]
      : []),

    // File
    {
      label: 'File',
      submenu: [
        {
          label: 'Settings',
          accelerator: 'CmdOrCtrl+,',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'Settings',
              message: 'Settings panel will be available in a future release.',
            });
          },
        },
        { type: 'separator' },
        isMac ? { role: 'close' } : { role: 'quit' },
      ],
    },

    // Edit
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectAll' },
      ],
    },

    // View
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { role: 'resetZoom' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },

    // Window
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        ...(isMac ? [{ role: 'zoom' }] : []),
        { role: 'close' },
      ],
    },

    // Help
    {
      label: 'Help',
      submenu: [
        {
          label: 'Check for Updates...',
          click: () => checkForUpdates(false),
        },
        { type: 'separator' },
        {
          label: 'About AICC IntelliDoc',
          click: async () => {
            const result = await dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About AICC IntelliDoc',
              message: `AICC IntelliDoc v${app.getVersion()}`,
              detail:
                'AI Document Analysis Desktop App\n\nDeveloped by AI Competency Centre, University of Oxford\n\nDeveloper: Alok Kumar Sahu',
              buttons: ['OK', 'Developer GitHub Profile'],
              defaultId: 0,
            });
            if (result.response === 1) {
              shell.openExternal('https://github.com/alokkrsahu');
            }
          },
        },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// ── IPC Handlers ─────────────────────────────────────────────────────────────

function registerIpcHandlers(djangoPort) {
  ipcMain.handle('dialog:openFiles', async (_event, options) => {
    const defaultFilters = [
      {
        name: 'Documents',
        extensions: ['pdf', 'doc', 'docx', 'txt', 'md', 'rtf'],
      },
    ];
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openFile', 'multiSelections'],
      filters: (options && options.filters) || defaultFilters,
    });
    if (result.canceled) return [];
    return result.filePaths;
  });

  ipcMain.handle('dialog:openDirectory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      properties: ['openDirectory'],
    });
    if (result.canceled) return null;
    return result.filePaths[0];
  });

  ipcMain.handle('get-config', async (_event, key) => {
    const s = await getStore();
    return s.get(key);
  });

  ipcMain.handle('set-config', async (_event, key, value) => {
    const s = await getStore();
    s.set(key, value);
  });

  ipcMain.handle('get-app-version', () => {
    return app.getVersion();
  });

  ipcMain.handle('check-backend', async () => {
    const url = `http://127.0.0.1:${djangoPort}/api/`;
    return new Promise((resolve) => {
      const req = http.get(url, (res) => {
        res.resume();
        resolve({ ok: true, status: res.statusCode });
      });
      req.on('error', (err) => {
        resolve({ ok: false, error: err.message });
      });
      req.setTimeout(3000, () => {
        req.destroy();
        resolve({ ok: false, error: 'Request timed out' });
      });
    });
  });
}

// ── Window Management ────────────────────────────────────────────────────────

async function createMainWindow(loadUrl) {
  const s = await getStore();
  const bounds = s.get('windowBounds') || { width: 1400, height: 900 };

  mainWindow = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    x: bounds.x,
    y: bounds.y,
    minWidth: 1024,
    minHeight: 768,
    title: 'AICC IntelliDoc',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Show when ready — close splash and reveal main window
  mainWindow.once('ready-to-show', () => {
    if (splashWindow && !splashWindow.isDestroyed()) {
      splashWindow.close();
      splashWindow = null;
    }
    mainWindow.show();
  });

  // Persist window bounds on resize / move
  const saveBounds = () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      const currentBounds = mainWindow.getBounds();
      getStore().then((st) => st.set('windowBounds', currentBounds));
    }
  };
  mainWindow.on('resize', saveBounds);
  mainWindow.on('move', saveBounds);

  // Open external links in system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  // Also intercept navigation to external URLs
  mainWindow.webContents.on('will-navigate', (event, url) => {
    const internal =
      url.startsWith('http://localhost') ||
      url.startsWith('http://127.0.0.1');
    if (!internal) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  // macOS: hide on close instead of quitting
  mainWindow.on('close', (event) => {
    if (process.platform === 'darwin' && !isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Load the application URL
  await mainWindow.loadURL(loadUrl);

  // Dev mode: open DevTools
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }

  return mainWindow;
}

// ── App Lifecycle ────────────────────────────────────────────────────────────

app.on('before-quit', () => {
  isQuitting = true;
});

app.on('will-quit', () => {
  stopAutoUpdateChecks();
  killDjango();
  // Optionally stop Ollama container (leave running for faster next launch)
  // try { execSync('docker stop aicc-ollama', { timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] }); } catch {}
  if (expressServer) {
    try {
      expressServer.close();
    } catch {
      // ignore
    }
    expressServer = null;
  }
});

// macOS: re-show window on dock click
app.on('activate', () => {
  if (mainWindow) {
    mainWindow.show();
  }
});

// ── Main Entry ───────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  try {
    // Show splash immediately — user sees feedback within 1 second
    splashWindow = createSplashWindow();

    const s = await getStore();
    const djangoPort = s.get('djangoPort') || 8000;
    let loadUrl;

    if (isDev) {
      // Dev mode: frontend dev server is already running via concurrently
      updateSplash('Connecting to dev server...', 50);
      loadUrl = 'http://localhost:5173';
    } else {
      // Production mode: spawn Django + Express proxy
      updateSplash('Finding Python...', 5);
      let pythonCmd;
      try {
        pythonCmd = findPython();
      } catch (err) {
        if (splashWindow && !splashWindow.isDestroyed()) splashWindow.close();
        dialog.showErrorBox(
          'Python Not Found',
          'AICC IntelliDoc requires Python 3.10+ to run.\n\n' +
          'Please install Python from https://python.org and ensure it is on your PATH.\n\n' +
          'On macOS: brew install python3\n' +
          'On Windows: Download from python.org'
        );
        app.quit();
        return;
      }

      const backendDir = app.isPackaged
        ? path.join(process.resourcesPath, 'backend')
        : path.join(__dirname, '..', 'backend');

      // Load .env from backend directory
      updateSplash('Loading configuration...', 10);
      const envPath = path.join(backendDir, '.env');
      const dotEnvVars = loadEnvFile(envPath);
      console.log(`.env loaded from ${envPath} (${Object.keys(dotEnvVars).length} vars)`);
      Object.assign(process.env, dotEnvVars);

      // Run migrations (async, non-blocking)
      updateSplash('Running database migrations...', 15);
      await runMigrations(pythonCmd, backendDir, dotEnvVars);

      // Spawn Django
      updateSplash('Starting backend server...', 25);
      djangoProcess = spawnDjango(pythonCmd, djangoPort, backendDir);

      // Wait for Django to come up — update splash with counter and progress
      console.log(`Waiting for Django on http://127.0.0.1:${djangoPort}/api/ ...`);
      let waitSeconds = 0;
      const maxExpectedSeconds = 45; // typical Django startup time
      const statusInterval = setInterval(() => {
        waitSeconds++;
        // Progress: 25% (start) → 85% (django ready), scaled by elapsed/expected
        const pct = Math.min(85, 25 + Math.round((waitSeconds / maxExpectedSeconds) * 60));
        updateSplash(`Starting backend server... (${waitSeconds}s)`, pct);
      }, 1000);

      await waitForUrl(`http://127.0.0.1:${djangoPort}/api/`, {
        interval: 500,
        maxRetries: 240,
      });
      clearInterval(statusInterval);
      console.log('Django is ready.');

      // Start Ollama Docker container (non-blocking — app works without it)
      if (checkDocker()) {
        updateSplash('Starting local AI engine...', 88);
        ollamaRunning = await startOllamaContainer();
        if (!ollamaRunning) {
          console.warn('Ollama container failed to start - local AI unavailable');
        }
      } else {
        console.log('Docker not found - skipping Ollama');
      }

      // Start Express proxy
      updateSplash('Starting application...', 90);
      const staticDir = app.isPackaged
        ? path.join(process.resourcesPath, 'static-app')
        : path.join(__dirname, '..', 'resources', 'static-app');

      const { createServer } = require('./server');
      const { server, port } = await createServer(djangoPort, staticDir);
      expressServer = server;

      loadUrl = `http://127.0.0.1:${port}`;
    }

    // Register IPC handlers before creating window
    registerIpcHandlers(djangoPort);

    // Build application menu
    buildAppMenu();

    // Create and show the main window (splash closes on ready-to-show)
    updateSplash('Almost ready...', 95);
    await createMainWindow(loadUrl);

    // Start automatic update checks (first check after 30s, then every 4 hours)
    startAutoUpdateChecks();
  } catch (err) {
    console.error('Fatal error during startup:', err);
    if (splashWindow && !splashWindow.isDestroyed()) splashWindow.close();
    dialog.showErrorBox(
      'Startup Error',
      `AICC IntelliDoc failed to start.\n\n${err.message}`
    );
    app.quit();
  }
});
