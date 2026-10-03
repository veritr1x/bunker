// Runs the build in a background thread so the page stays responsive.
importScripts("https://cdn.jsdelivr.net/pyodide/v0.28.3/full/pyodide.js");

let ready = null;
const post = (type, value) => self.postMessage({ type, value });

async function fetchBytes(url, label) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Cannot download ${label} (${response.status})`);
  const total = Number(response.headers.get("Content-Length")) || 0;
  const reader = response.body.getReader();
  const parts = [];
  let received = 0, shown = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    parts.push(value);
    received += value.length;
    if (total && received - shown > total / 20) {
      shown = received;
      post("log", `Downloading ${label}… ${Math.round((received / total) * 100)}%`);
    }
  }
  const bytes = new Uint8Array(received);
  let offset = 0;
  for (const part of parts) { bytes.set(part, offset); offset += part.length; }
  return bytes;
}

function writeFile(pyodide, path, bytes) {
  pyodide.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
  pyodide.FS.writeFile(path, bytes);
}

async function setup() {
  post("log", "Loading Python…");
  const pyodide = await loadPyodide();
  await pyodide.loadPackage(["pycryptodome", "msgpack", "lz4"]);
  pyodide.setStdout({ batched: (line) => post("log", line) });
  pyodide.setStderr({ batched: (line) => post("log", line) });
  const manifest = await (await fetch("py/manifest.json")).json();
  for (const file of manifest) {
    writeFile(pyodide, "/repo/" + file, new Uint8Array(await (await fetch("py/" + file)).arrayBuffer()));
  }
  pyodide.runPython("import sys; sys.path.insert(0, '/repo/web'); import webbuild");
  return pyodide;
}

self.onmessage = async ({ data }) => {
  const { platform, game, master } = data;
  try {
    ready = ready || setup();
    const pyodide = await ready;
    const FS = pyodide.FS;
    // Your files are read where they are, without copying them into memory.
    try { FS.unmount("/input"); } catch (_) {}
    FS.mkdirTree("/input");
    FS.mount(FS.filesystems.WORKERFS, { files: [game, master] }, "/input");
    const gamePath = "/input/" + game.name, masterPath = "/input/" + master.name;
    const log = (line) => post("log", line);
    const builder = pyodide.globals.get("webbuild");
    let output;
    if (platform === "android") {
      writeFile(pyodide, "/bundles/android.zip", await fetchBytes("bundles/android.zip", "the launcher"));
      output = "/output/game-Offline.apk";
      FS.mkdirTree("/output");
      builder.build_android(gamePath, masterPath, "/bundles/android.zip", output, log);
    } else {
      writeFile(pyodide, "/bundles/ios-framework.zip", await fetchBytes("bundles/ios-framework.zip", "the launcher"));
      writeFile(pyodide, "/bundles/ios-python.zip", await fetchBytes("bundles/ios-python.zip", "Tools"));
      output = "/output/game-Offline.ipa";
      FS.mkdirTree("/output");
      builder.build_ios(gamePath, masterPath, "/bundles/ios-framework.zip", "/bundles/ios-python.zip", output, log);
    }
    const bytes = FS.readFile(output);
    FS.unlink(output);
    for (const name of FS.readdir("/bundles")) if (name !== "." && name !== "..") FS.unlink("/bundles/" + name);
    self.postMessage({ type: "done", value: { name: output.split("/").pop(), bytes } }, [bytes.buffer]);
  } catch (error) {
    post("error", String(error.message || error).split("\n").filter(Boolean).slice(-3).join("\n"));
  }
};
