const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('quantDesktop', {
  platform: process.platform,
})
