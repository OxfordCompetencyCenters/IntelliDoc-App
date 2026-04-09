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
 * Locate a working Python 3.10+ executable.
 * macOS GUI apps get a minimal PATH, so we also check common install locations.
 * Returns the command string or throws if none found.
 */
function findPython() {
  // Common Python paths on macOS / Linux / Windows
  const extraPaths = [
    '/opt/anaconda3/bin',
    '/opt/homebrew/bin',
    '/usr/local/bin',
    '/opt/miniconda3/bin',
    path.join(process.env.HOME || '', 'anaconda3', 'bin'),
    path.join(process.env.HOME || '', 'miniconda3', 'bin'),
    path.join(process.env.HOME || '', '.pyenv', 'shims'),
  ];
  // Prepend extra paths to PATH for this search
  const origPath = process.env.PATH || '';
  const searchPath = [...extraPaths, ...origPath.split(path.delimiter)].join(path.delimiter);

  const candidates = ['python3', 'python'];
  for (const cmd of candidates) {
    try {
      const version = execSync(`${cmd} --version`, {
        encoding: 'utf8',
        timeout: 5000,
        stdio: ['pipe', 'pipe', 'pipe'],
        env: { ...process.env, PATH: searchPath },
      });
      const versionMatch = version.match(/(\d+)\.(\d+)/);
      const major = versionMatch ? parseInt(versionMatch[1]) : 0;
      const minor = versionMatch ? parseInt(versionMatch[2]) : 0;
      if (major < 3 || (major === 3 && minor < 10)) {
        console.log(`Skipping ${cmd} (${version.trim()}) — need 3.10+`);
        continue;
      }
      console.log(`Found Python: ${cmd} (${version.trim()})`);
      // Also update process.env.PATH so subsequent calls find the same Python
      process.env.PATH = searchPath;
      return cmd;
    } catch {
      // try next candidate
    }
  }

  // Last resort: check for exact paths
  const absoluteCandidates = [
    '/opt/homebrew/bin/python3',
    '/opt/anaconda3/bin/python3',
    '/usr/local/bin/python3',
  ];
  for (const cmd of absoluteCandidates) {
    try {
      if (!fs.existsSync(cmd)) continue;
      const version = execSync(`"${cmd}" --version`, {
        encoding: 'utf8',
        timeout: 5000,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      console.log(`Found Python: ${cmd} (${version.trim()})`);
      return cmd;
    } catch {
      // try next
    }
  }

  throw new Error(
    'Python 3.10+ not found. Please install Python from https://python.org and ensure it is on your PATH.'
  );
}

/**
 * Ensure a virtual environment exists with all backend dependencies installed.
 * Creates the venv in userData/python-env/ and installs requirements.txt.
 * Re-installs if requirements.txt has changed (based on hash).
 * Returns the path to the venv's Python executable.
 */
async function ensureVenv(pythonCmd, backendDir) {
  const crypto = require('crypto');
  const venvDir = path.join(app.getPath('userData'), 'python-env');
  const venvPython = process.platform === 'win32'
    ? path.join(venvDir, 'Scripts', 'python.exe')
    : path.join(venvDir, 'bin', 'python');
  const hashFile = path.join(venvDir, '.requirements-hash');
  const requirementsPath = path.join(backendDir, 'requirements.txt');

  // Compute hash of current requirements.txt
  let currentHash = '';
  if (fs.existsSync(requirementsPath)) {
    const content = fs.readFileSync(requirementsPath, 'utf8');
    currentHash = crypto.createHash('sha256').update(content).digest('hex');
  }

  // Check if venv exists and is up to date
  let needsInstall = false;
  if (!fs.existsSync(venvPython)) {
    console.log('Creating Python virtual environment...');
    updateSplash('Creating Python environment...', 12);
    execSync(`${pythonCmd} -m venv "${venvDir}"`, {
      encoding: 'utf8',
      timeout: 60000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    needsInstall = true;
  } else {
    // Check if requirements changed
    let storedHash = '';
    if (fs.existsSync(hashFile)) {
      storedHash = fs.readFileSync(hashFile, 'utf8').trim();
    }
    if (storedHash !== currentHash) {
      console.log('Requirements changed, reinstalling dependencies...');
      needsInstall = true;
    } else {
      console.log('Virtual environment is up to date.');
    }
  }

  if (needsInstall && fs.existsSync(requirementsPath)) {
    console.log('Installing Python dependencies (this may take a few minutes on first launch)...');
    updateSplash('Installing Python dependencies... (first launch only)', 14);

    // Upgrade pip first
    try {
      execSync(`"${venvPython}" -m pip install --upgrade pip`, {
        encoding: 'utf8',
        timeout: 120000,
        stdio: ['pipe', 'pipe', 'pipe'],
      });
    } catch (e) {
      console.warn('pip upgrade failed (non-fatal):', e.message);
    }

    // Install requirements using spawn for live progress
    const pipCmd = process.platform === 'win32'
      ? path.join(venvDir, 'Scripts', 'pip')
      : path.join(venvDir, 'bin', 'pip');

    await new Promise((resolve, reject) => {
      const pipProcess = spawn(
        pipCmd,
        ['install', '-r', requirementsPath],
        {
          cwd: backendDir,
          env: { ...process.env, PYTHONUNBUFFERED: '1' },
          stdio: ['pipe', 'pipe', 'pipe'],
        }
      );

      let installedCount = 0;
      const handleOutput = (data) => {
        const text = data.toString();
        process.stdout.write(`[pip] ${text}`);
        // Count installed packages for progress
        const matches = text.match(/Successfully installed/g);
        if (matches) installedCount += matches.length;
        // Show current package being installed
        const collecting = text.match(/Collecting (\S+)/);
        if (collecting) {
          updateSplash(`Installing: ${collecting[1]}...`, 15);
        }
        const downloading = text.match(/Downloading/);
        if (downloading) {
          updateSplash('Downloading dependencies...', 16);
        }
      };

      pipProcess.stdout.on('data', handleOutput);
      pipProcess.stderr.on('data', handleOutput);

      pipProcess.on('close', (code) => {
        if (code === 0) {
          console.log('Python dependencies installed successfully.');
          resolve();
        } else {
          reject(new Error(`pip install failed with exit code ${code}`));
        }
      });

      pipProcess.on('error', (err) => {
        reject(new Error(`Failed to run pip: ${err.message}`));
      });

      // 10-minute timeout for large packages like torch
      setTimeout(() => {
        try { pipProcess.kill(); } catch {}
        reject(new Error('pip install timed out after 10 minutes'));
      }, 600000);
    });

    // Save hash
    fs.writeFileSync(hashFile, currentHash, 'utf8');
    console.log('Python dependencies installed successfully.');
  }

  return venvPython;
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
 * Find a random available port. Eliminates all port conflicts.
 */
function getRandomPort() {
  return new Promise((resolve, reject) => {
    const server = require('net').createServer();
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}

/**
 * Spawn Django on the given port. Returns { child, startupPromise }.
 * startupPromise rejects early if Django crashes (port conflict, import error, etc.).
 */
function spawnDjango(pythonCmd, djangoPort, backendDir) {
  const managePy = path.join(backendDir, 'manage.py');
  const useDetached = process.platform !== 'win32';

  console.log(`Starting Django: ${pythonCmd} ${managePy} runserver 127.0.0.1:${djangoPort} --noreload`);

  let startupReject = null;
  const startupPromise = new Promise((_, reject) => { startupReject = reject; });

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
    const text = data.toString();
    process.stderr.write(`[django] ${text}`);
    // Detect fatal startup errors early
    // Detect fatal startup errors early and capture details
    const fatalPatterns = [
      /Address already in use/,
      /SyntaxError/,
      /IndentationError/,
      /ModuleNotFoundError: No module named '([^']+)'/,
      /ImportError: cannot import name '([^']+)'/,
      /ImproperlyConfigured/,
    ];
    for (const pattern of fatalPatterns) {
      const match = text.match(pattern);
      if (match && startupReject) {
        const detail = match[1] ? `${match[0]}` : match[0];
        startupReject(new Error(`Django startup failed:\n${detail}`));
        startupReject = null;
        break;
      }
    }
  });

  child.on('error', (err) => {
    console.error('Failed to start Django process:', err.message);
    if (startupReject) { startupReject(err); startupReject = null; }
  });

  child.on('exit', (code, signal) => {
    console.log(`Django process exited (code=${code}, signal=${signal})`);
    if (code !== 0 && startupReject) {
      startupReject(new Error(`Django exited with code ${code}`));
      startupReject = null;
    }
    djangoProcess = null;
  });

  return { child, startupPromise };
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
 * Check if Docker Desktop is installed (not just the CLI).
 */
function isDockerDesktopInstalled() {
  if (process.platform === 'darwin') {
    return fs.existsSync('/Applications/Docker.app');
  } else if (process.platform === 'win32') {
    return (
      fs.existsSync('C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe') ||
      fs.existsSync(path.join(process.env.LOCALAPPDATA || '', 'Docker', 'Docker Desktop.exe'))
    );
  }
  // Linux: check if docker CLI exists (daemon runs as a service)
  try {
    execSync('which docker', { timeout: 3000, stdio: ['pipe', 'pipe', 'pipe'] });
    return true;
  } catch {
    return false;
  }
}

/**
 * Ensure Docker is available. Handles three scenarios:
 *   1. Docker running       → return true immediately
 *   2. Docker installed      → auto-launch and wait
 *   3. Docker not installed  → prompt user to install, then retry
 * Returns true if Docker is ready, false if user skipped or install failed.
 */
async function ensureDocker() {
  // ── Scenario 1: Docker daemon already running ──
  try {
    execSync('docker info', { encoding: 'utf8', timeout: 5000, stdio: ['pipe', 'pipe', 'pipe'] });
    console.log('Docker daemon is already running');
    return true;
  } catch {
    // Not running — continue
  }

  // ── Scenario 3: Docker not installed at all ──
  if (!isDockerDesktopInstalled()) {
    console.log('Docker Desktop not installed — prompting user');
    const downloadUrls = {
      darwin: 'https://www.docker.com/products/docker-desktop/',
      win32: 'https://www.docker.com/products/docker-desktop/',
      linux: 'https://docs.docker.com/engine/install/',
    };
    const result = await dialog.showMessageBox(mainWindow || splashWindow, {
      type: 'info',
      title: 'Docker Required for Local AI',
      message: 'Docker Desktop is needed for Ollama (local AI models).',
      detail:
        'AICC IntelliDoc uses Docker to run Ollama, which provides local AI models ' +
        'that work without internet or API keys.\n\n' +
        'Without Docker, you can still use cloud AI providers (OpenAI, Anthropic, Google) ' +
        'if you configure API keys.\n\n' +
        'Would you like to download Docker Desktop now?',
      buttons: ['Download Docker', 'Skip for now'],
      defaultId: 0,
      cancelId: 1,
    });

    if (result.response === 0) {
      shell.openExternal(downloadUrls[process.platform] || downloadUrls.linux);
      // Show a follow-up dialog telling user to restart the app after installing
      await dialog.showMessageBox(mainWindow || splashWindow, {
        type: 'info',
        title: 'Install Docker Desktop',
        message: 'After installing Docker Desktop, restart AICC IntelliDoc.',
        detail:
          'Docker Desktop is downloading in your browser.\n\n' +
          '1. Install Docker Desktop\n' +
          '2. Launch Docker Desktop once to complete setup\n' +
          '3. Restart AICC IntelliDoc — Ollama will start automatically',
        buttons: ['OK'],
      });
    }
    return false;
  }

  // ── Scenario 2: Docker installed but daemon not running — auto-launch ──
  console.log('Docker daemon not running — launching Docker Desktop...');
  updateSplash('Starting Docker...', 86);

  try {
    if (process.platform === 'darwin') {
      execSync('open -a Docker', { timeout: 10000, stdio: ['pipe', 'pipe', 'pipe'] });
    } else if (process.platform === 'win32') {
      spawn('cmd', ['/c', 'start', '', 'C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe'], {
        detached: true, stdio: 'ignore',
      });
    } else {
      execSync('systemctl start docker', { timeout: 10000, stdio: ['pipe', 'pipe', 'pipe'] });
    }
  } catch (err) {
    console.warn('Failed to launch Docker Desktop:', err.message);
    return false;
  }

  // Wait for Docker daemon to become ready (up to 60 seconds)
  const maxWait = 60;
  for (let i = 0; i < maxWait; i++) {
    try {
      execSync('docker info', { encoding: 'utf8', timeout: 3000, stdio: ['pipe', 'pipe', 'pipe'] });
      console.log(`Docker daemon ready after ${i + 1}s`);
      return true;
    } catch {
      if (i % 5 === 0) {
        updateSplash(`Starting Docker... (${i}s)`, 86);
      }
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
  }

  console.warn(`Docker daemon did not start within ${maxWait}s`);
  return false;
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
    // Use a random available port — eliminates all port conflicts
    const djangoPort = await getRandomPort();
    console.log(`Selected random port: ${djangoPort}`);
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

      // Ensure Python virtual environment with all dependencies
      updateSplash('Checking Python environment...', 12);
      let venvPython;
      try {
        venvPython = await ensureVenv(pythonCmd, backendDir);
        console.log(`Using venv Python: ${venvPython}`);
      } catch (err) {
        if (splashWindow && !splashWindow.isDestroyed()) splashWindow.close();
        dialog.showErrorBox(
          'Dependency Installation Failed',
          `Failed to install Python dependencies.\n\n${err.message}\n\nPlease ensure you have internet access and try again.`
        );
        app.quit();
        return;
      }

      // Run migrations (async, non-blocking)
      updateSplash('Running database migrations...', 20);
      await runMigrations(venvPython, backendDir, dotEnvVars);

      // Spawn Django on random port
      updateSplash('Starting backend server...', 30);
      const { child: djangoChild, startupPromise } = spawnDjango(venvPython, djangoPort, backendDir);
      djangoProcess = djangoChild;

      // Wait for Django — race between health check and startup errors
      console.log(`Waiting for Django on http://127.0.0.1:${djangoPort}/api/ ...`);
      let waitSeconds = 0;
      const maxExpectedSeconds = 45;
      const statusInterval = setInterval(() => {
        waitSeconds++;
        const pct = Math.min(85, 30 + Math.round((waitSeconds / maxExpectedSeconds) * 55));
        updateSplash(`Starting backend server... (${waitSeconds}s)`, pct);
      }, 1000);

      // Race: either Django becomes ready OR it crashes with a fatal error
      await Promise.race([
        waitForUrl(`http://127.0.0.1:${djangoPort}/api/`, { interval: 500, maxRetries: 240 }),
        startupPromise, // Rejects immediately on fatal Django errors
      ]);
      clearInterval(statusInterval);
      console.log('Django is ready.');

      // Start Docker (if needed) and Ollama container
      const dockerReady = await ensureDocker();
      if (dockerReady) {
        updateSplash('Starting local AI engine...', 88);
        ollamaRunning = await startOllamaContainer();
        if (!ollamaRunning) {
          console.warn('Ollama container failed to start - local AI unavailable');
        }
      } else {
        console.log('Docker not available - skipping Ollama');
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
