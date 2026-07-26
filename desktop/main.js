const {app, BrowserWindow, dialog, ipcMain} = require("electron");
const {spawn, spawnSync} = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const PACKAGE_ROOT = process.env.TRADEMONKE_PACKAGE_ROOT || "/usr/lib/trademonke";
const DEFAULT_INSTALL = process.env.TRADEMONKE_INSTALL_ROOT || "/opt/trademonke";
// Desktop-launched Electron often has a stripped PATH; never rely on bare "bash".
const BASH = fs.existsSync("/bin/bash") ? "/bin/bash" : "/usr/bin/bash";
const SAFE_PATH = ["/usr/local/bin", "/usr/bin", "/bin", process.env.PATH || ""].filter(Boolean).join(":");

function resolveAppIcon() {
  const candidates = [
    path.join(__dirname, "assets", "trade-monke-icon.png"),
    path.join(__dirname, "assets", "trademonke.png"),
    path.join(PACKAGE_ROOT, "desktop", "assets", "trade-monke-icon.png"),
    path.join(PACKAGE_ROOT, "desktop", "assets", "trademonke.png"),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate)) || undefined;
}
const APP_ICON = resolveAppIcon();

function resolveRoot() {
  if (process.env.TRADEMONKE_ROOT) return process.env.TRADEMONKE_ROOT;
  if (fs.existsSync(path.join(DEFAULT_INSTALL, "docker-compose.yml"))) return DEFAULT_INSTALL;
  const sibling = path.resolve(__dirname, "..");
  if (fs.existsSync(path.join(sibling, "docker-compose.yml"))) return sibling;
  return DEFAULT_INSTALL;
}

let ROOT = resolveRoot();

function logDir() {
  const base = process.env.TRADEMONKE_LOG_DIR
    || path.join(process.env.XDG_DATA_HOME || path.join(os.homedir(), ".local", "share"), "trademonke", "logs", "desktop");
  fs.mkdirSync(path.join(base, "errors"), {recursive: true});
  return base;
}

function appendLog(line) {
  const dir = logDir();
  const stamp = new Date().toISOString();
  const text = `${stamp} ${line}\n`;
  fs.appendFileSync(path.join(dir, "trademonke-desktop.log"), text, "utf8");
  return text;
}

function captureCmd(command, args, cwd) {
  try {
    const result = spawnSync(command, args, {
      cwd: cwd || workingCwd(),
      env: childEnv(),
      encoding: "utf8",
      timeout: 15000,
    });
    return [
      `$ ${command} ${args.join(" ")}`,
      (result.stdout || "").trim(),
      (result.stderr || "").trim(),
      `exit=${result.status}`,
    ].filter(Boolean).join("\n");
  } catch (error) {
    return `$ ${command} ${args.join(" ")}\nERROR: ${error.message || error}`;
  }
}

function writeErrorReport(title, error) {
  const dir = logDir();
  const stamp = new Date().toISOString().replace(/[:.]/g, "").replace("T", "-").slice(0, 15);
  const reportPath = path.join(dir, "errors", `${stamp}-error.log`);
  const latestPath = path.join(dir, "latest-error.log");
  const sessionLog = path.join(dir, "trademonke-desktop.log");
  const parts = [
    "=== TradeMonke error report ===",
    `utc: ${new Date().toISOString()}`,
    `title: ${title}`,
    `user: ${os.userInfo().username}`,
    `host: ${os.hostname()}`,
    `ROOT: ${ROOT}`,
    `PACKAGE_ROOT: ${PACKAGE_ROOT}`,
    `cwd: ${workingCwd()}`,
    `platform: ${process.platform} ${os.release()}`,
    `electron: ${process.versions.electron || "unknown"}`,
    `node: ${process.versions.node}`,
    "",
    "=== error ===",
    String(error && (error.stack || error.message || error)),
    "",
    "=== error fields ===",
    `code=${error && error.code}`,
    `stdout=${error && error.stdout ? String(error.stdout).slice(-8000) : ""}`,
    `stderr=${error && error.stderr ? String(error.stderr).slice(-8000) : ""}`,
    "",
    "=== docker context ===",
    captureCmd("docker", ["context", "show"]),
    "",
    "=== docker ps ===",
    captureCmd("docker", ["ps", "-a", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"]),
    "",
  ];
  if (fs.existsSync(path.join(ROOT, "docker-compose.yml"))) {
    parts.push(
      `=== compose ps (${ROOT}) ===`,
      captureCmd("docker", ["compose", "ps", "-a"], ROOT),
      "",
      "=== compose logs (tail) ===",
      captureCmd("docker", ["compose", "logs", "--no-color", "--tail=80", "platform-api", "research-gui", "market-data", "postgres", "migrate"], ROOT),
      "",
    );
  }
  if (fs.existsSync(sessionLog)) {
    parts.push("=== recent desktop log ===", fs.readFileSync(sessionLog, "utf8").split("\n").slice(-120).join("\n"), "");
  }
  fs.writeFileSync(reportPath, parts.join("\n"), "utf8");
  fs.copyFileSync(reportPath, latestPath);
  appendLog(`ERROR_REPORT ${reportPath}`);
  return reportPath;
}

function workingCwd() {
  // Node reports spawn ENOENT when cwd does not exist — /opt/trademonke is missing
  // until first-run bootstrap creates it.
  if (ROOT && fs.existsSync(ROOT)) return ROOT;
  if (fs.existsSync(PACKAGE_ROOT)) return PACKAGE_ROOT;
  if (fs.existsSync(__dirname)) return __dirname;
  return "/tmp";
}

function scriptPath(...parts) {
  const userScripts = process.env.TRADEMONKE_USER_SCRIPTS;
  if (userScripts) {
    const fromUser = path.join(userScripts, ...parts);
    if (fs.existsSync(fromUser)) return fromUser;
  }
  const fromRoot = path.join(ROOT, "scripts", "desktop", ...parts);
  if (fs.existsSync(fromRoot)) return fromRoot;
  const fromPackage = path.join(PACKAGE_ROOT, "scripts", "desktop", ...parts);
  if (fs.existsSync(fromPackage)) return fromPackage;
  return fromRoot;
}

function needsBootstrap() {
  if (!fs.existsSync(path.join(ROOT, "docker-compose.yml"))) return true;
  if (!fs.existsSync(path.join(ROOT, ".git"))) return true;
  if (!fs.existsSync(path.join(ROOT, ".env"))) return true;
  return false;
}

let splash = null;
let mainWindow = null;
let bootStatus = {message: "Preparing…", phase: "running"};
const bootLog = [];
const BOOT_LOG_LIMIT = 4000;
let stopOnQuit = process.env.TRADEMONKE_STOP_ON_QUIT === "1";

function emitBoot(channel, payload) {
  if (splash && !splash.isDestroyed()) {
    splash.webContents.send(channel, payload);
  }
}

function appendBootLog(text, stream = "stdout") {
  const cleaned = String(text ?? "").replace(/\r/g, "");
  if (!cleaned) return;
  const entry = {text: cleaned, stream, ts: new Date().toISOString()};
  bootLog.push(entry);
  while (bootLog.length > BOOT_LOG_LIMIT) bootLog.shift();
  emitBoot("boot-log", entry);
}

function readEnvToken() {
  if (process.env.TRADEMONKE_GUI_TOKEN) return process.env.TRADEMONKE_GUI_TOKEN;
  const envPath = path.join(ROOT, ".env");
  if (!fs.existsSync(envPath)) return "";
  const line = fs.readFileSync(envPath, "utf8").split("\n").find((row) => row.startsWith("PLATFORM_GUI_ACCESS_TOKEN="));
  return line ? line.slice("PLATFORM_GUI_ACCESS_TOKEN=".length).trim() : "";
}

function guiUrl() {
  if (process.env.TRADEMONKE_GUI_URL) return process.env.TRADEMONKE_GUI_URL;
  const envPath = path.join(ROOT, ".env");
  let port = "3000";
  if (fs.existsSync(envPath)) {
    const line = fs.readFileSync(envPath, "utf8").split("\n").find((row) => row.startsWith("PLATFORM_GUI_PORT="));
    if (line) port = line.slice("PLATFORM_GUI_PORT=".length).trim() || "3000";
  }
  return `http://127.0.0.1:${port}/`;
}

function setStatus(message, phase = "running", {echo = true} = {}) {
  bootStatus = {message, phase};
  appendLog(`STATUS ${message}`);
  if (echo) appendBootLog(`STATUS: ${message}`, "status");
  emitBoot("boot-status", bootStatus);
}

function handleOutputLine(line, stream) {
  const text = line.replace(/\s+$/, "");
  if (!text) return;
  appendLog(`${stream === "stderr" ? "STDERR" : "STDOUT"} ${text}`);
  appendBootLog(text, text.startsWith("STATUS:") ? "status" : stream);
  if (text.startsWith("STATUS:")) {
    setStatus(text.slice("STATUS:".length).trim(), "running", {echo: false});
  }
}

function attachLineReader(readable, stream) {
  if (!readable) return () => {};
  let buffer = "";
  const onData = (chunk) => {
    buffer += chunk.toString();
    // Normalize CR progress updates from docker/apt into discrete lines.
    buffer = buffer.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
    const parts = buffer.split("\n");
    buffer = parts.pop() || "";
    for (const part of parts) handleOutputLine(part, stream);
  };
  const flush = () => {
    if (buffer) {
      handleOutputLine(buffer, stream);
      buffer = "";
    }
  };
  readable.on("data", onData);
  return flush;
}

function childEnv(extra = {}) {
  return {
    ...process.env,
    PATH: SAFE_PATH,
    TRADEMONKE_ROOT: ROOT,
    TRADEMONKE_PACKAGE_ROOT: PACKAGE_ROOT,
    TRADEMONKE_LOG_DIR: logDir(),
    // Prefer line-oriented docker/buildkit output in the progress window.
    BUILDKIT_PROGRESS: "plain",
    COMPOSE_PROGRESS: "plain",
    PYTHONUNBUFFERED: "1",
    ...extra,
  };
}

function run(command, args, opts = {}) {
  return new Promise((resolve, reject) => {
    const {env: envExtra, cwd, ...rest} = opts;
    const workdir = cwd || workingCwd();
    appendLog(`RUN ${command} ${JSON.stringify(args)} cwd=${workdir}`);
    appendBootLog(`$ ${command} ${args.join(" ")}`, "meta");
    // Line-buffer child output when stdbuf is available (apt/docker stay readable).
    let spawnCmd = command;
    let spawnArgs = args;
    if (command === BASH && fs.existsSync("/usr/bin/stdbuf")) {
      spawnCmd = "/usr/bin/stdbuf";
      spawnArgs = ["-oL", "-eL", command, ...args];
    }
    const child = spawn(spawnCmd, spawnArgs, {
      cwd: workdir,
      env: childEnv(envExtra),
      ...rest,
    });
    let stdout = "";
    let stderr = "";
    const flushOut = attachLineReader(child.stdout, "stdout");
    const flushErr = attachLineReader(child.stderr, "stderr");
    if (child.stdout) {
      child.stdout.on("data", (chunk) => {
        stdout += chunk.toString();
      });
    }
    if (child.stderr) {
      child.stderr.on("data", (chunk) => {
        stderr += chunk.toString();
      });
    }
    child.on("error", (err) => {
      err.message = `${err.message} (cmd=${command} cwd=${workdir} args=${JSON.stringify(args)})`;
      reject(err);
    });
    child.on("close", (code) => {
      flushOut();
      flushErr();
      appendLog(`EXIT ${command} code=${code}`);
      appendBootLog(`[exit ${code}] ${command}`, "meta");
      if (code === 0) resolve({stdout, stderr, code});
      else {
        const error = new Error(`${command} exited ${code}: ${stderr || stdout}`);
        error.code = code;
        error.stdout = stdout;
        error.stderr = stderr;
        reject(error);
      }
    });
  });
}

function dockerReachable() {
  return new Promise((resolve) => {
    const child = spawn("docker", ["info"], {stdio: "ignore", env: childEnv()});
    child.on("error", () => resolve(false));
    child.on("close", (code) => resolve(code === 0));
  });
}

function installRootWritable() {
  const target = DEFAULT_INSTALL;
  try {
    if (fs.existsSync(target)) {
      fs.accessSync(target, fs.constants.W_OK);
      return true;
    }
    const parent = path.dirname(target);
    fs.accessSync(parent, fs.constants.W_OK);
    return true;
  } catch {
    return false;
  }
}

async function maybeBootstrap() {
  const force = process.env.TRADEMONKE_FORCE_BOOTSTRAP === "1";
  if (!force && !needsBootstrap() && (await dockerReachable())) {
    return;
  }
  setStatus("First-run setup: installing dependencies and cloning the app…");
  const bootstrap = scriptPath("bootstrap.sh");
  if (!fs.existsSync(bootstrap)) {
    throw new Error(`Bootstrap script missing: ${bootstrap}`);
  }
  const args = ["--package"];
  // --user-only only when Docker works AND /opt/trademonke is writable.
  // Otherwise bootstrap elevates (pkexec/sudo) so it can create /opt/trademonke.
  if ((await dockerReachable()) && installRootWritable()) {
    args.unshift("--user-only");
  }
  // Always run bootstrap from an existing directory (package root), not missing /opt.
  await run(BASH, [bootstrap, ...args], {cwd: workingCwd()});
  ROOT = resolveRoot();
  setStatus("Bootstrap complete");
}

async function maybeUpdate() {
  const check = scriptPath("check-update.sh");
  const update = scriptPath("trademonke-update.sh");
  if (!fs.existsSync(check)) return;
  setStatus("Checking for updates on origin/main…");
  try {
    await run(BASH, [check]);
  } catch (error) {
    if (error.code === 1) return; // current
    setStatus("Update check skipped (offline or no remote).");
    appendLog(`UPDATE_CHECK_SKIP ${error.message || error}`);
    return;
  }
  const result = await dialog.showMessageBox({
    type: "question",
    buttons: ["Update", "Later"],
    defaultId: 0,
    cancelId: 1,
    title: "TradeMonke update",
    message: "An update is available on origin/main.",
    detail: "Update now rebuilds Docker images. Your .env and runtime data are preserved.",
  });
  if (result.response !== 0) return;
  setStatus("Updating from origin/main…");
  await run(BASH, [update]);
}

async function bootStack() {
  const start = scriptPath("trademonke-start.sh");
  setStatus("Starting Postgres, API, market data, and GUI…");
  await run(BASH, [start, "--no-open", "--no-update-check"]);
  setStatus("Workstation ready");
}

function createSplash() {
  splash = new BrowserWindow({
    width: 780,
    height: 560,
    minWidth: 560,
    minHeight: 380,
    frame: true,
    resizable: true,
    autoHideMenuBar: true,
    title: "TradeMonke setup",
    backgroundColor: "#0b1218",
    ...(APP_ICON ? {icon: APP_ICON} : {}),
    webPreferences: {preload: path.join(__dirname, "preload.js"), contextIsolation: true},
  });
  splash.loadFile(path.join(__dirname, "splash.html"));
  splash.webContents.on("did-finish-load", () => {
    emitBoot("boot-status", bootStatus);
    for (const entry of bootLog) emitBoot("boot-log", entry);
  });
}

async function openWorkstation() {
  const url = guiUrl();
  const token = readEnvToken();
  appendLog(`OPEN_GUI ${url}`);
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    autoHideMenuBar: true,
    ...(APP_ICON ? {icon: APP_ICON} : {}),
    webPreferences: {contextIsolation: true},
  });
  let injected = false;
  if (token) {
    mainWindow.webContents.on("did-finish-load", async () => {
      if (injected) return;
      injected = true;
      await mainWindow.webContents.executeJavaScript(
        `sessionStorage.setItem("gui-token", ${JSON.stringify(token)}); location.reload();`,
      ).catch(() => {});
    });
  }
  await mainWindow.loadURL(url);
  if (splash && !splash.isDestroyed()) splash.close();
}

ipcMain.handle("boot-status", () => bootStatus);
ipcMain.handle("boot-log", () => bootLog.slice(-500));

app.whenReady().then(async () => {
  appendLog(`SESSION_START ROOT=${ROOT} PACKAGE_ROOT=${PACKAGE_ROOT}`);
  createSplash();
  setStatus("Preparing TradeMonke…", "running");
  try {
    if (process.env.TRADEMONKE_SKIP_BOOT !== "1") {
      await maybeBootstrap();
      await maybeUpdate();
      await bootStack();
    }
    setStatus("Opening research workstation…", "done");
    await openWorkstation();
    appendLog("SESSION_READY");
  } catch (error) {
    setStatus("Setup failed — see verbose output and error report", "fail");
    appendBootLog(String(error && (error.stack || error.message || error)), "stderr");
    const reportPath = writeErrorReport("TradeMonke failed to start", error);
    appendBootLog(`Full report: ${reportPath}`, "meta");
    dialog.showErrorBox(
      "TradeMonke failed to start",
      `${String(error.message || error)}\n\nFull report saved to:\n${reportPath}\n\nAlso:\n${path.join(logDir(), "latest-error.log")}`,
    );
    app.quit();
  }
});

app.on("window-all-closed", () => {
  if (stopOnQuit) {
    const stop = scriptPath("trademonke-stop.sh");
    spawn(BASH, [stop], {
      cwd: workingCwd(),
      env: childEnv(),
      detached: true,
      stdio: "ignore",
    }).unref();
  }
  appendLog("SESSION_END");
  app.quit();
});
