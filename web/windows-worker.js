const original = {
  apk: { size: 263571029, hash: "9ded0797ee607b6892b531ba3a02f4c4510774f5fe098ccada78ccff881c9209" },
  master: { size: 7801104, hash: "60555788242de9a0580b0d86f6d109d67bd9cabd16d7bcda9b9a99745f270778" }
};
const log = (value) => self.postMessage({ type: "log", value });

async function verify(file, expected, label) {
  if (!(file instanceof Blob) || file.size !== expected.size) throw new Error("Choose the original Global " + label + ".");
  const bytes = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  const hash = Array.from(new Uint8Array(bytes), (value) => value.toString(16).padStart(2, "0")).join("");
  if (hash !== expected.hash) throw new Error("The " + label + " differs from the expected Global release.");
}

self.onmessage = async ({ data }) => {
  try {
    log("Checking the original Global game and master data…");
    await verify(data.master, original.master, "master data");
    await verify(data.game, original.apk, "3.7.1 ARM64 APK");
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
