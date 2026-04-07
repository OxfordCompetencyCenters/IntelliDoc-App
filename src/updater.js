/**
 * Auto-updater for AICC IntelliDoc Desktop App.
 *
 * Checks GitHub Releases for newer versions.
 * Downloads the installer in-app with progress.
 * Opens the installer for the user to complete the update.
 *
 * GitHub repo: OxfordCompetencyCenters/IntelliDoc-App
 */

const { app, dialog, shell, BrowserWindow } = require('electron');
const https = require('https');
const http = require('http');
const path = require('path');
const fs = require('fs');
const os = require('os');

const GITHUB_OWNER = 'OxfordCompetencyCenters';
const GITHUB_REPO = 'IntelliDoc-App';
const CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000; // 4 hours

let updateCheckTimer = null;
let lastDismissedVersion = null;
let isDownloading = false;

function getCurrentVersion() {
  return app.getVersion();
}

function compareVersions(a, b) {
  const pa = a.replace(/^v/, '').split('.').map(Number);
  const pb = b.replace(/^v/, '').split('.').map(Number);
  for (let i = 0; i < 3; i++) {
    const va = pa[i] || 0;
    const vb = pb[i] || 0;
    if (va > vb) return 1;
    if (va < vb) return -1;
  }
  return 0;
}

function fetchLatestRelease() {
  return new Promise((resolve, reject) => {
    https.get({
      hostname: 'api.github.com',
      path: `/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`,
      headers: {
        'User-Agent': `AICC-IntelliDoc/${getCurrentVersion()}`,
        'Accept': 'application/vnd.github.v3+json',
      },
    }, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        if (res.statusCode === 200) {
          try { resolve(JSON.parse(data)); } catch { reject(new Error('Parse error')); }
        } else if (res.statusCode === 404) {
          resolve(null);
        } else {
          reject(new Error(`GitHub API ${res.statusCode}`));
        }
      });
    }).on('error', reject).setTimeout(10000, function() { this.destroy(); reject(new Error('Timeout')); });
  });
}

/**
 * Find the best download asset for current platform.
 */
function findAsset(release) {
  if (!release?.assets?.length) return null;
  const platform = process.platform;
  const arch = process.arch;

  const assets = release.assets;

  // Score each asset for relevance
  let best = null;
  let bestScore = -1;

  for (const asset of assets) {
    const name = asset.name.toLowerCase();
    let score = 0;

    if (platform === 'darwin') {
      if (name.endsWith('.dmg')) score += 10;
      else if (name.endsWith('.zip') && !name.includes('win')) score += 5;
      else continue;
      if (arch === 'arm64' && name.includes('arm64')) score += 3;
      if (arch === 'x64' && name.includes('x64')) score += 3;
      if (!name.includes('arm64') && !name.includes('x64')) score += 1; // universal
    } else if (platform === 'win32') {
      if (name.endsWith('.exe')) score += 10;
      else if (name.endsWith('.msi')) score += 8;
      else continue;
      if (arch === 'x64' && (name.includes('x64') || name.includes('64'))) score += 3;
    } else if (platform === 'linux') {
      if (name.endsWith('.appimage')) score += 10;
      else if (name.endsWith('.deb')) score += 8;
      else continue;
      if (arch === 'x64' && (name.includes('x64') || name.includes('amd64'))) score += 3;
      if (arch === 'arm64' && name.includes('arm64')) score += 3;
    } else {
      continue;
    }

    if (score > bestScore) {
      bestScore = score;
      best = asset;
    }
  }

  return best;
}

/**
 * Download a file with progress callback. Follows redirects.
 */
function downloadFile(url, destPath, onProgress) {
  return new Promise((resolve, reject) => {
    const doRequest = (reqUrl) => {
      const mod = reqUrl.startsWith('https') ? https : http;
      mod.get(reqUrl, { headers: { 'User-Agent': 'AICC-IntelliDoc' } }, (res) => {
        // Follow redirects (GitHub uses 302)
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          return doRequest(res.headers.location);
        }
        if (res.statusCode !== 200) {
          return reject(new Error(`Download failed: HTTP ${res.statusCode}`));
        }

        const totalBytes = parseInt(res.headers['content-length'] || '0', 10);
        let downloadedBytes = 0;
        const file = fs.createWriteStream(destPath);

        res.on('data', (chunk) => {
          downloadedBytes += chunk.length;
          file.write(chunk);
          if (onProgress && totalBytes > 0) {
            onProgress(downloadedBytes, totalBytes);
          }
        });

        res.on('end', () => {
          file.end();
          resolve(destPath);
        });

        res.on('error', (err) => {
          file.destroy();
          fs.unlink(destPath, () => {});
          reject(err);
        });
      }).on('error', reject);
    };
    doRequest(url);
  });
}

/**
 * Show update dialog, download with progress, and open installer.
 */
async function showUpdateDialog(release, asset) {
  const currentVersion = getCurrentVersion();
  const newVersion = release.tag_name.replace(/^v/, '');
  const mainWindow = BrowserWindow.getAllWindows()[0];

  const sizeFormatted = asset ? `${(asset.size / 1024 / 1024).toFixed(0)} MB` : '';
  const assetInfo = asset ? `\nDownload size: ${sizeFormatted}` : '';

  const result = await dialog.showMessageBox(mainWindow, {
    type: 'info',
    title: 'Update Available',
    message: `AICC IntelliDoc v${newVersion} is available`,
    detail: `You are running v${currentVersion}.${assetInfo}\n\n${(release.body || 'Improvements and bug fixes.').slice(0, 400)}`,
    buttons: ['Download & Install', 'Remind Me Later', 'Skip This Version'],
    defaultId: 0,
    cancelId: 1,
  });

  if (result.response === 0) {
    if (asset) {
      await downloadAndInstall(asset, newVersion, mainWindow);
    } else {
      shell.openExternal(`https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`);
    }
  } else if (result.response === 2) {
    lastDismissedVersion = release.tag_name;
  }
}

/**
 * Download the update and open/run the installer.
 */
async function downloadAndInstall(asset, newVersion, mainWindow) {
  if (isDownloading) return;
  isDownloading = true;

  const downloadDir = path.join(os.tmpdir(), 'aicc-intellidoc-updates');
  fs.mkdirSync(downloadDir, { recursive: true });
  const destPath = path.join(downloadDir, asset.name);

  // Create progress window
  const progressWin = new BrowserWindow({
    width: 420, height: 160,
    parent: mainWindow,
    modal: true,
    resizable: false,
    frame: false,
    center: true,
    webPreferences: { nodeIntegration: false, contextIsolation: true },
  });

  const progressHTML = `<!DOCTYPE html><html><head><style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #fff; padding: 24px; }
    h3 { font-size: 14px; color: #1e293b; margin-bottom: 8px; }
    .bar-wrap { width: 100%; height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; margin-bottom: 8px; }
    .bar { height: 100%; width: 0%; background: linear-gradient(90deg, #002147, #2563eb); border-radius: 3px; transition: width 0.3s; }
    .info { font-size: 12px; color: #64748b; }
  </style></head><body>
    <h3>Downloading AICC IntelliDoc v${newVersion}...</h3>
    <div class="bar-wrap"><div class="bar" id="bar"></div></div>
    <div class="info" id="info">Starting download...</div>
  </body></html>`;

  progressWin.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(progressHTML)}`);

  try {
    await downloadFile(asset.browser_download_url, destPath, (downloaded, total) => {
      const pct = Math.round((downloaded / total) * 100);
      const dlMB = (downloaded / 1024 / 1024).toFixed(1);
      const totalMB = (total / 1024 / 1024).toFixed(1);
      if (!progressWin.isDestroyed()) {
        progressWin.webContents.executeJavaScript(`
          document.getElementById('bar').style.width = '${pct}%';
          document.getElementById('info').innerText = '${dlMB} MB / ${totalMB} MB (${pct}%)';
        `).catch(() => {});
      }
    });

    if (!progressWin.isDestroyed()) progressWin.close();

    // Open the downloaded installer
    const ext = path.extname(destPath).toLowerCase();
    const platform = process.platform;

    if (platform === 'darwin' && ext === '.dmg') {
      // macOS: open the .dmg so user can drag to Applications
      shell.openPath(destPath);
      dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: 'Update Downloaded',
        message: 'Update downloaded successfully!',
        detail: `The installer has been opened.\n\nDrag "AICC IntelliDoc" to your Applications folder to update.\n\nThe app will close. Reopen it after updating.`,
        buttons: ['Quit & Update'],
      }).then(() => {
        app.quit();
      });
    } else if (platform === 'win32' && (ext === '.exe' || ext === '.msi')) {
      // Windows: run the installer
      const { exec } = require('child_process');
      exec(`start "" "${destPath}"`);
      setTimeout(() => app.quit(), 1000);
    } else if (platform === 'linux' && ext === '.appimage') {
      // Linux: make executable and inform user
      fs.chmodSync(destPath, '755');
      dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: 'Update Downloaded',
        message: 'Update downloaded!',
        detail: `The new AppImage has been saved to:\n${destPath}\n\nReplace your current AppImage with this file and restart.`,
        buttons: ['Open Folder', 'OK'],
      }).then((res) => {
        if (res.response === 0) {
          shell.showItemInFolder(destPath);
        }
      });
    } else {
      // Unknown: open containing folder
      shell.showItemInFolder(destPath);
    }

  } catch (err) {
    if (!progressWin.isDestroyed()) progressWin.close();
    dialog.showMessageBox(mainWindow, {
      type: 'error',
      title: 'Download Failed',
      message: `Failed to download update: ${err.message}`,
      detail: 'You can download the update manually from the releases page.',
      buttons: ['Open Releases Page', 'Cancel'],
    }).then((res) => {
      if (res.response === 0) {
        shell.openExternal(`https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`);
      }
    });
  } finally {
    isDownloading = false;
  }
}

/**
 * Check for updates.
 */
async function checkForUpdates(silent = true) {
  try {
    console.log('🔄 Checking for updates...');
    const release = await fetchLatestRelease();

    if (!release) {
      if (!silent) {
        dialog.showMessageBox({ type: 'info', title: 'Up to Date', message: 'No releases found. You are running the latest version.' });
      }
      return;
    }

    const currentVersion = getCurrentVersion();
    const latestVersion = release.tag_name.replace(/^v/, '');

    console.log(`Current: v${currentVersion}, Latest: v${latestVersion}`);

    if (compareVersions(latestVersion, currentVersion) > 0) {
      if (lastDismissedVersion === release.tag_name) {
        console.log(`Update v${latestVersion} was skipped by user.`);
        return;
      }

      const asset = findAsset(release);
      console.log(`🆕 Update available: v${latestVersion} (asset: ${asset?.name || 'none'})`);
      await showUpdateDialog(release, asset);
    } else {
      console.log('✅ App is up to date.');
      if (!silent) {
        dialog.showMessageBox({ type: 'info', title: 'Up to Date', message: `You are running the latest version (v${currentVersion}).` });
      }
    }
  } catch (err) {
    console.warn('Update check failed:', err.message);
    if (!silent) {
      dialog.showMessageBox({ type: 'warning', title: 'Update Check Failed', message: `Could not check for updates: ${err.message}` });
    }
  }
}

function startAutoUpdateChecks() {
  setTimeout(() => checkForUpdates(true), 30000);
  updateCheckTimer = setInterval(() => checkForUpdates(true), CHECK_INTERVAL_MS);
}

function stopAutoUpdateChecks() {
  if (updateCheckTimer) { clearInterval(updateCheckTimer); updateCheckTimer = null; }
}

module.exports = {
  checkForUpdates,
  startAutoUpdateChecks,
  stopAutoUpdateChecks,
  getCurrentVersion,
  GITHUB_OWNER,
  GITHUB_REPO,
};
