const {contextBridge, ipcRenderer} = require("electron");

contextBridge.exposeInMainWorld("trademonkeDesktop", {
  getBootStatus: () => ipcRenderer.invoke("boot-status"),
  getBootLog: () => ipcRenderer.invoke("boot-log"),
  onBootStatus: (handler) => {
    const listener = (_event, payload) => handler(payload);
    ipcRenderer.on("boot-status", listener);
    return () => ipcRenderer.removeListener("boot-status", listener);
  },
  onBootLog: (handler) => {
    const listener = (_event, payload) => handler(payload);
    ipcRenderer.on("boot-log", listener);
    return () => ipcRenderer.removeListener("boot-log", listener);
  },
});
