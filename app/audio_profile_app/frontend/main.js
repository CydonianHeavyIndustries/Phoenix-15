const { app, BrowserWindow, Menu, Tray } = require("electron");
const { spawn } = require("child_process");
const path = require("path");

let backendProcess = null;
let mainWindow = null;
let tray = null;
let isQuitting = false;

const rootDir = path.join(__dirname, "..", "..");
const iconPath = path.join(rootDir, "NewBjorgIcon.ico");

function startBackend() {
  if (backendProcess) {
    return;
  }
  const serverPath = path.join(rootDir, "server", "server.py");
  const pythonPath = process.env.BJORGSUN_PY || path.join(rootDir, "venv", "Scripts", "python.exe");

  backendProcess = spawn(pythonPath, [serverPath], {
    cwd: rootDir,
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });

  backendProcess.stdout.on("data", (data) => {
    console.log(`[bjorgsun] ${data.toString().trim()}`);
  });

  backendProcess.stderr.on("data", (data) => {
    console.error(`[bjorgsun] ${data.toString().trim()}`);
  });

  backendProcess.on("close", (code) => {
    console.log(`Bjorgsun backend exited with code ${code}`);
    backendProcess = null;
  });
}

function stopBackend() {
  if (!backendProcess) {
    return;
  }
  const pid = backendProcess.pid;
  backendProcess = null;
  if (!pid) {
    return;
  }
  try {
    spawn(
      "powershell",
      [
        "-NoLogo",
        "-NoProfile",
        "-Command",
        `Stop-Process -Id ${pid} -Force`,
      ],
      { windowsHide: true, stdio: "ignore" }
    );
  } catch (err) {
    console.error("Backend stop failed:", err);
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 800,
    backgroundColor: "#070c14",
    show: false,
    webPreferences: {
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  mainWindow.loadFile(path.join(__dirname, "index.html"));

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
}

function createTray() {
  tray = new Tray(iconPath);
  tray.setToolTip("Bjorgsun-26 Core");
  const contextMenu = Menu.buildFromTemplate([
    {
      label: "Open Bjorgsun",
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    {
      label: "Sleep (close backend)",
      click: () => {
        stopBackend();
      },
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);
  tray.setContextMenu(contextMenu);
  tray.on("double-click", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  app.whenReady().then(() => {
    startBackend();
    createWindow();
    createTray();
  });
}

app.on("before-quit", () => {
  isQuitting = true;
  stopBackend();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
