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

// The notices are optional: a site built without the notice pack makes builds without Notices.
async function fetchNotices(pyodide) {
  const head = await fetch("bundles/notices.zip", { method: "HEAD" }).catch(() => null);
  if (!head || !head.ok) return null;
  writeFile(pyodide, "/bundles/notices.zip", await fetchBytes("bundles/notices.zip", "the notices"));
  return "/bundles/notices.zip";
}

// The finished file goes to the page as a Blob built from pieces, so it is never
// held whole twice: browsers can keep a large Blob out of the page's memory.
class Pieces {
  constructor() { this.blob = new Blob([]); this.pending = []; this.size = 0; }
  add(bytes) {
    this.pending.push(bytes);
    this.size += bytes.length;
    if (this.pending.length >= 8) this.fold();
  }
  fold() { this.blob = new Blob([this.blob, ...this.pending], { type: "application/octet-stream" }); this.pending = []; }
  done() { this.fold(); return this.blob; }
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
  const { platform, game, master, portOffset = 0 } = data;
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
    // The APK or IPA comes out in pieces as it is written; it is never a file here.
    const pieces = new Pieces();
    const handOver = (piece) => {
      const buffer = piece.getBuffer("u8");
      pieces.add(buffer.data.slice());
      buffer.release();
      piece.destroy();
    };
    let name;
    if (platform === "android") {
      writeFile(pyodide, "/bundles/android.zip", await fetchBytes("bundles/android.zip", "the launcher"));
      const notices = await fetchNotices(pyodide);
      builder.build_android(gamePath, masterPath, "/bundles/android.zip", handOver, log, portOffset, notices);
      name = "bunker.apk";
    } else {
      writeFile(pyodide, "/bundles/ios-framework.zip", await fetchBytes("bundles/ios-framework.zip", "the launcher"));
      writeFile(pyodide, "/bundles/ios-python.zip", await fetchBytes("bundles/ios-python.zip", "Tools"));
      const notices = await fetchNotices(pyodide);
      builder.build_ios(gamePath, masterPath, "/bundles/ios-framework.zip", "/bundles/ios-python.zip", handOver, log, portOffset, notices);
      name = "bunker.ipa";
    }
    const blob = pieces.done();
    for (const file of FS.readdir("/bundles")) if (file !== "." && file !== "..") FS.unlink("/bundles/" + file);
    self.postMessage({ type: "done", value: { name, blob } });
  } catch (error) {
    post("error", String(error.message || error).split("\n").filter(Boolean).slice(-3).join("\n"));
  }
};
