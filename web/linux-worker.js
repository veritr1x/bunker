import { verifyDesktopInputs } from "./desktop-inputs.js";
import { openApk, patchedMember } from "./windows/apk.mjs";
import { patchMaster } from "./windows/compiler.mjs";

async function get(name) {
  const response = await fetch(new URL(name, import.meta.url));
  if (!response.ok) throw new Error("Could not load " + name);
  return response;
}

// POSIX tar preserves the executable bit when a Linux archive manager extracts Play.sh.
function header(name, size, mode) {
  const bytes = new Uint8Array(512);
  const put = (offset, value) => bytes.set(new TextEncoder().encode(value), offset);
  const octal = (offset, width, value) => put(offset, value.toString(8).padStart(width - 1, "0") + "\0");
  put(0, "NieR Reincarnation/" + name);
  octal(100, 8, mode); octal(108, 8, 0); octal(116, 8, 0);
  octal(124, 12, size); octal(136, 12, 0);
  put(148, "        "); put(156, "0"); put(257, "ustar\0"); put(263, "00");
  const checksum = bytes.reduce((sum, n) => sum + n, 0);
  put(148, checksum.toString(8).padStart(6, "0") + "\0 ");
  return bytes;
}

self.onmessage = async ({ data }) => {
  const log = value => self.postMessage({type: "log", value});
  try {
    log("Checking the Global APK and master data…");
    await verifyDesktopInputs(data.game, data.master);
    const pin = data.linuxRelease;
    if (!pin || !/^\d+\.\d+\.\d+$/.test(pin.reincompVersion) || !/^[a-f0-9]{64}$/.test(pin.sha256) ||
        pin.asset !== `reincomp-linux-x86_64-${pin.reincompVersion}.tar.gz`) throw new Error("Invalid Linux release");
    const plan = await (await get("windows/game-plan.json")).json();
    const metadata = await patchedMember(await openApk(data.game), plan.metadata);
    log("Applying Bunker’s master data patch…");
    const master = await patchMaster(data.master);
    const template = (await (await get("linux-play.sh")).text()).replace(/\r\n/g, "\n");
    const script = template.replace("@ASSET@", pin.asset).replace("@VERSION@", pin.reincompVersion).replace("@SHA256@", pin.sha256);
    const notices = await (await get("bundles/notices.json")).json();
    const parts = [];
    for (const name of notices.parts) {
      if (!/^notices\.zip(?:\.\d+)?$/.test(name)) throw new Error("Invalid Bunker notice package");
      parts.push(await (await get("bundles/" + name)).blob());
    }
    const noticePack = new Blob(parts);
    if (!noticePack.size || noticePack.size !== notices.size) throw new Error("Incomplete Bunker notices");
    log("Packaging the native Linux download…");
    const tar = [];
    for (const [name, file, mode] of [
      ["Play.sh", new Blob([script]), 0o755], ["game.apk", data.game, 0o644],
      ["global-metadata.dat", metadata, 0o644], ["20240404193219.bin.e", master, 0o644],
      ["notices.zip", noticePack, 0o644]
    ]) {
      tar.push(header(name, file.size, mode), file, new Uint8Array((512 - file.size % 512) % 512));
    }
    tar.push(new Uint8Array(1024));
    const blob = new Blob(tar, {type: "application/x-tar"});
    self.postMessage({type: "done", value: {name: "NieR-Reincarnation-Linux-x86_64.tar", blob}});
  } catch (error) {
    self.postMessage({type: "error", value: error.message || String(error)});
  }
};
