const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectFiles: (options) => ipcRenderer.invoke('dialog:openFiles', options),
  selectDirectory: () => ipcRenderer.invoke('dialog:openDirectory'),
  getConfig: (key) => ipcRenderer.invoke('get-config', key),
  setConfig: (key, value) => ipcRenderer.invoke('set-config', key, value),
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  checkBackend: () => ipcRenderer.invoke('check-backend'),
  platform: process.platform,
  isElectron: true
});
