/**
 * Auto-updater using electron-updater (differential updates).
 *
 * Checks GitHub Releases for newer versions.
 * Downloads only changed blocks (differential/delta updates).
 * Installs automatically on app restart.
 *
 * Fallback: if electron-updater fails (unsigned builds), uses manual GitHub check.
 */

const { app, dialog, shell, BrowserWindow } = require('electron');
const path = require('path');

const GITHUB_OWNER = 'OxfordCompetencyCenters';
const GITHUB_REPO = 'IntelliDoc-App';

let autoUpdater = null;
let useManualFallback = false;

/**
 * Initialize the updater. Try electron-updater first, fall back to manual.
 */
function initUpdater() {
  try {
    const { autoUpdater: au } = require('electron-updater');
    autoUpdater = au;

    autoUpdater.autoDownload = false; // User must approve
    autoUpdater.autoInstallOnAppQuit = true;

    autoUpdater.on('checking-for-update', () => {
      console.log('🔄 Checking for updates...');
    });

    autoUpdater.on('update-available', (info) => {
      console.log(`🆕 Update available: v${info.version}`);
      const mainWindow = BrowserWindow.getAllWindows()[0];
      dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: 'Update Available',
        message: `AICC IntelliDoc v${info.version} is available`,
        detail: `You are running v${app.getVersion()}.\n\nThe update will be downloaded in the background. You'll be notified when it's ready to install.`,
        buttons: ['Download Now', 'Later'],
        defaultId: 0,
      }).then((result) => {
        if (result.response === 0) {
          autoUpdater.downloadUpdate();
        }
      });
    });

    autoUpdater.on('update-not-available', (info) => {
      console.log('✅ App is up to date.');
    });

    autoUpdater.on('download-progress', (progress) => {
      console.log(`📥 Download: ${progress.percent.toFixed(1)}% (${(progress.transferred / 1024 / 1024).toFixed(1)}/${(progress.total / 1024 / 1024).toFixed(1)} MB)`);
    });

    autoUpdater.on('update-downloaded', (info) => {
      console.log(`✅ Update v${info.version} downloaded.`);
      const mainWindow = BrowserWindow.getAllWindows()[0];
      dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: 'Update Ready',
        message: `AICC IntelliDoc v${info.version} has been downloaded`,
        detail: 'The update will be installed when you restart the app.',
        buttons: ['Restart Now', 'Later'],
        defaultId: 0,
      }).then((result) => {
        if (result.response === 0) {
          autoUpdater.quitAndInstall();
        }
      });
    });

    autoUpdater.on('error', (err) => {
      console.warn('electron-updater error:', err.message);
      // Fall back to manual check on error
      useManualFallback = true;
    });

    console.log('✅ electron-updater initialized');
  } catch (err) {
    console.warn('electron-updater not available, using manual fallback:', err.message);
    useManualFallback = true;
  }
}

/**
 * Manual fallback: check GitHub API directly.
 */
async function manualCheckForUpdates(silent = true) {
  const https = require('https');

  return new Promise((resolve) => {
    https.get({
      hostname: 'api.github.com',
      path: `/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`,
      headers: { 'User-Agent': `AICC-IntelliDoc/${app.getVersion()}`, 'Accept': 'application/vnd.github.v3+json' },
    }, (res) => {
      let data = '';
      res.on('data', (c) => data += c);
      res.on('end', () => {
        try {
          if (res.statusCode !== 200) { resolve(); return; }
          const release = JSON.parse(data);
          const latest = release.tag_name.replace(/^v/, '');
          const current = app.getVersion();

          const cmp = compareVersions(latest, current);
          if (cmp > 0) {
            console.log(`🆕 Manual check: v${latest} available`);
            const mainWindow = BrowserWindow.getAllWindows()[0];
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'Update Available',
              message: `AICC IntelliDoc v${latest} is available`,
              detail: `You are running v${current}.\n\n${(release.body || '').slice(0, 300)}`,
              buttons: ['Download', 'Later'],
            }).then((result) => {
              if (result.response === 0) {
                shell.openExternal(`https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`);
              }
            });
          } else if (!silent) {
            dialog.showMessageBox({ type: 'info', title: 'Up to Date', message: `You are running the latest version (v${current}).` });
          }
        } catch {}
        resolve();
      });
    }).on('error', () => resolve());
  });
}

function compareVersions(a, b) {
  const pa = a.replace(/^v/, '').split('.').map(Number);
  const pb = b.replace(/^v/, '').split('.').map(Number);
  for (let i = 0; i < 3; i++) {
    if ((pa[i] || 0) > (pb[i] || 0)) return 1;
    if ((pa[i] || 0) < (pb[i] || 0)) return -1;
  }
  return 0;
}

/**
 * Check for updates (uses electron-updater or manual fallback).
 */
async function checkForUpdates(silent = true) {
  if (autoUpdater && !useManualFallback) {
    try {
      await autoUpdater.checkForUpdates();
    } catch (err) {
      console.warn('Auto-update check failed, trying manual:', err.message);
      await manualCheckForUpdates(silent);
    }
  } else {
    await manualCheckForUpdates(silent);
  }
}

let updateCheckTimer = null;

function startAutoUpdateChecks() {
  initUpdater();
  setTimeout(() => checkForUpdates(true), 30000);
  updateCheckTimer = setInterval(() => checkForUpdates(true), 4 * 60 * 60 * 1000);
}

function stopAutoUpdateChecks() {
  if (updateCheckTimer) { clearInterval(updateCheckTimer); updateCheckTimer = null; }
}

function getCurrentVersion() {
  return app.getVersion();
}

module.exports = {
  checkForUpdates,
  startAutoUpdateChecks,
  stopAutoUpdateChecks,
  getCurrentVersion,
  GITHUB_OWNER,
  GITHUB_REPO,
};
