/**
 * Auto-updater for AICC IntelliDoc Desktop App.
 *
 * Checks GitHub Releases for newer versions.
 * Shows a notification dialog when an update is available.
 * Downloads and opens the installer for the user.
 *
 * GitHub repo: OxfordCompetencyCenters/IntelliDoc-App
 */

const { app, dialog, shell, BrowserWindow, net } = require('electron');
const https = require('https');
const path = require('path');
const fs = require('fs');

const GITHUB_OWNER = 'OxfordCompetencyCenters';
const GITHUB_REPO = 'IntelliDoc-App';
const RELEASES_URL = `https://api.github.com/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`;
const CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000; // Check every 4 hours

let updateCheckTimer = null;
let lastDismissedVersion = null;

/**
 * Get current app version from package.json.
 */
function getCurrentVersion() {
  return app.getVersion();
}

/**
 * Compare semantic versions. Returns:
 *  1 if a > b, -1 if a < b, 0 if equal
 */
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

/**
 * Fetch the latest release from GitHub.
 */
function fetchLatestRelease() {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.github.com',
      path: `/repos/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`,
      method: 'GET',
      headers: {
        'User-Agent': `AICC-IntelliDoc/${getCurrentVersion()}`,
        'Accept': 'application/vnd.github.v3+json',
      },
    };

    const req = https.get(options, (res) => {
      let data = '';
      res.on('data', (chunk) => data += chunk);
      res.on('end', () => {
        if (res.statusCode === 200) {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            reject(new Error('Failed to parse release data'));
          }
        } else if (res.statusCode === 404) {
          resolve(null); // No releases yet
        } else {
          reject(new Error(`GitHub API returned ${res.statusCode}`));
        }
      });
    });

    req.on('error', reject);
    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error('GitHub API request timed out'));
    });
  });
}

/**
 * Find the download URL for the current platform.
 */
function findAssetUrl(release) {
  if (!release || !release.assets) return null;

  const platform = process.platform;
  const arch = process.arch;

  for (const asset of release.assets) {
    const name = asset.name.toLowerCase();

    if (platform === 'darwin') {
      // macOS: prefer .dmg, then .zip
      if (name.endsWith('.dmg') && (name.includes('arm64') || !name.includes('x64'))) {
        return asset.browser_download_url;
      }
    } else if (platform === 'win32') {
      if (name.endsWith('.exe') || name.endsWith('.msi')) {
        return asset.browser_download_url;
      }
    } else if (platform === 'linux') {
      if (name.endsWith('.appimage') || name.endsWith('.deb')) {
        return asset.browser_download_url;
      }
    }
  }

  // Fallback: any matching extension
  for (const asset of release.assets) {
    const name = asset.name.toLowerCase();
    if (platform === 'darwin' && (name.endsWith('.dmg') || name.endsWith('.zip'))) {
      return asset.browser_download_url;
    }
    if (platform === 'win32' && name.endsWith('.exe')) {
      return asset.browser_download_url;
    }
    if (platform === 'linux' && name.endsWith('.appimage')) {
      return asset.browser_download_url;
    }
  }

  return null;
}

/**
 * Show update notification to the user.
 */
async function showUpdateDialog(release, downloadUrl) {
  const currentVersion = getCurrentVersion();
  const newVersion = release.tag_name.replace(/^v/, '');

  const mainWindow = BrowserWindow.getAllWindows()[0];

  const result = await dialog.showMessageBox(mainWindow, {
    type: 'info',
    title: 'Update Available',
    message: `AICC IntelliDoc v${newVersion} is available`,
    detail: `You are currently running v${currentVersion}.\n\n${release.body ? release.body.slice(0, 300) : 'A new version is available with improvements and bug fixes.'}\n\nWould you like to download and install the update?`,
    buttons: ['Install Now', 'Remind Me Later', 'Skip This Version'],
    defaultId: 0,
    cancelId: 1,
  });

  if (result.response === 0) {
    // Install Now — open download URL in browser
    if (downloadUrl) {
      shell.openExternal(downloadUrl);
    } else {
      // No direct download — open releases page
      shell.openExternal(`https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}/releases/latest`);
    }
  } else if (result.response === 2) {
    // Skip This Version
    lastDismissedVersion = release.tag_name;
    console.log(`Update v${newVersion} skipped by user.`);
  }
  // else: Remind Me Later — do nothing, will check again next interval
}

/**
 * Check for updates and notify the user if available.
 */
async function checkForUpdates(silent = true) {
  try {
    console.log('🔄 Checking for updates...');
    const release = await fetchLatestRelease();

    if (!release) {
      if (!silent) {
        dialog.showMessageBox({
          type: 'info',
          title: 'No Updates',
          message: 'No releases found. You are running the latest version.',
        });
      }
      return;
    }

    const currentVersion = getCurrentVersion();
    const latestVersion = release.tag_name.replace(/^v/, '');

    console.log(`Current: v${currentVersion}, Latest: v${latestVersion}`);

    if (compareVersions(latestVersion, currentVersion) > 0) {
      // Skip if user dismissed this version
      if (lastDismissedVersion === release.tag_name) {
        console.log(`Update v${latestVersion} was previously skipped.`);
        return;
      }

      const downloadUrl = findAssetUrl(release);
      console.log(`🆕 Update available: v${latestVersion} (download: ${downloadUrl ? 'yes' : 'no'})`);
      await showUpdateDialog(release, downloadUrl);
    } else {
      console.log('✅ App is up to date.');
      if (!silent) {
        dialog.showMessageBox({
          type: 'info',
          title: 'Up to Date',
          message: `You are running the latest version (v${currentVersion}).`,
        });
      }
    }
  } catch (err) {
    console.warn('Update check failed:', err.message);
    if (!silent) {
      dialog.showMessageBox({
        type: 'warning',
        title: 'Update Check Failed',
        message: `Could not check for updates: ${err.message}`,
      });
    }
  }
}

/**
 * Start periodic update checks.
 */
function startAutoUpdateChecks() {
  // Initial check after 30 seconds (let app finish loading)
  setTimeout(() => checkForUpdates(true), 30000);

  // Periodic checks
  updateCheckTimer = setInterval(() => checkForUpdates(true), CHECK_INTERVAL_MS);
}

/**
 * Stop periodic update checks.
 */
function stopAutoUpdateChecks() {
  if (updateCheckTimer) {
    clearInterval(updateCheckTimer);
    updateCheckTimer = null;
  }
}

module.exports = {
  checkForUpdates,
  startAutoUpdateChecks,
  stopAutoUpdateChecks,
  getCurrentVersion,
  GITHUB_OWNER,
  GITHUB_REPO,
};
