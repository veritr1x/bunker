import { verifyDesktopInputs } from "./desktop-inputs.js";
const log = (value) => self.postMessage({ type: "log", value });

self.onmessage = async ({ data }) => {
  try {
    log("Checking the original Global game and master data…");
    await verifyDesktopInputs(data.game, data.master);
    const { compileWindows } = await import("./windows/compiler.mjs");
    const blob = await compileWindows({ apk: data.game, master: data.master, log, preparedRuntime: data.windowsRuntime });
    if (!(blob instanceof Blob) || blob.size < 512) throw new Error("The compiler returned an incomplete Windows executable.");
    const header = new DataView(await blob.slice(0, 64).arrayBuffer());
    const position = header.getUint32(60, true);
    if (header.getUint16(0, true) !== 0x5a4d || position > blob.size - 26) throw new Error("Missing Windows executable header.");
    const pe = new DataView(await blob.slice(position, position + 26).arrayBuffer());
    if (pe.getUint32(0, true) !== 0x4550 || pe.getUint16(4, true) !== 0x8664 || pe.getUint16(24, true) !== 0x20b) {
      throw new Error("The compiler did not produce a Windows x64 executable.");
    }
    self.postMessage({ type: "done", value: { name: "Nier Reincarnation.exe", blob } });
  } catch (error) {
    self.postMessage({ type: "error", value: error.message || String(error) });
  }
};
