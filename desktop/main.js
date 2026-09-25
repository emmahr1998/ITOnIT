const { app, BrowserWindow, Menu, net, protocol, shell } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

// Thin shell around the shared React app. Two ways to load it:
//   dev  (default)   - the Vite dev server started in desktop mode
//                      (npm run dev:desktop in frontend/), at its normal origin.
//   prod (--prod)    - the built desktop bundle (frontend/dist-desktop) served
//                      from a custom app:// origin, so BrowserRouter routes,
//                      root-absolute asset paths and localStorage all behave
//                      exactly as they do on the web (file:// would break them).
const isProd = app.isPackaged || process.argv.includes("--prod");

const DEV_ORIGIN = "http://localhost:5173";
const PROD_ORIGIN = "app://itonit";
const APP_ORIGIN = isProd ? PROD_ORIGIN : DEV_ORIGIN;
// Packaged: electron-builder copies the built renderer to <resources>/renderer.
// Unpackaged: read it straight from the repo's desktop build output.
const DIST_DIR = app.isPackaged
  ? path.join(process.resourcesPath, "renderer")
  : path.join(__dirname, "..", "frontend", "dist-desktop");

protocol.registerSchemesAsPrivileged([
  { scheme: "app", privileges: { standard: true, secure: true, supportFetchAPI: true } },
]);

function serveBuiltApp() {
  protocol.handle("app", (request) => {
    const { pathname } = new URL(request.url);
    const requested = path.normalize(path.join(DIST_DIR, decodeURIComponent(pathname)));
    if (requested !== DIST_DIR && !requested.startsWith(DIST_DIR + path.sep)) {
      return new Response("Forbidden", { status: 403 });
    }
    if (fs.existsSync(requested) && fs.statSync(requested).isFile()) {
      return net.fetch(pathToFileURL(requested).toString());
    }
    // A path with a file extension that doesn't exist is a genuinely missing
    // asset; anything else is a client-side route, so hand it to the SPA.
    if (path.extname(pathname)) {
      return new Response("Not found", { status: 404 });
    }
    return net.fetch(pathToFileURL(path.join(DIST_DIR, "index.html")).toString());
  });
}

// Keeps application routes inside the window; genuine external http(s) links
// go to the system browser instead of replacing the ITOnIT app.
function openExternally(url) {
  if (/^https?:\/\//i.test(url)) {
    shell.openExternal(url);
  }
}

function isInternal(url) {
  try {
    return new URL(url).origin === APP_ORIGIN;
  } catch {
    return false;
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: "ITOnIT",
    backgroundColor: "#f6f7fb",
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  // The page <title> is the marketing one; the desktop window is just "ITOnIT".
  win.on("page-title-updated", (event) => event.preventDefault());
  win.once("ready-to-show", () => win.show());

  win.webContents.setWindowOpenHandler(({ url }) => {
    openExternally(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    if (!isInternal(url)) {
      event.preventDefault();
      openExternally(url);
    }
  });

  win.loadURL(`${APP_ORIGIN}/`);
  return win;
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    const [win] = BrowserWindow.getAllWindows();
    if (win) {
      if (win.isMinimized()) win.restore();
      win.focus();
    }
  });

  app.whenReady().then(() => {
    if (isProd) {
      serveBuiltApp();
      // No menu (and so no reload/devtools shortcuts) in prod behavior.
      Menu.setApplicationMenu(null);
    }
    createWindow();
  });

  app.on("window-all-closed", () => app.quit());
}
