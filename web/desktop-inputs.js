const original = {
  apk: { size: 263571029, hash: "9ded0797ee607b6892b531ba3a02f4c4510774f5fe098ccada78ccff881c9209" },
  master: { size: 7801104, hash: "60555788242de9a0580b0d86f6d109d67bd9cabd16d7bcda9b9a99745f270778" }
};

async function verify(file, expected, label) {
  if (!(file instanceof Blob) || file.size !== expected.size) throw new Error("Choose the original Global " + label + ".");
  const bytes = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  const hash = Array.from(new Uint8Array(bytes), (value) => value.toString(16).padStart(2, "0")).join("");
  if (hash !== expected.hash) throw new Error("The " + label + " differs from the expected Global release.");
}

export async function verifyDesktopInputs(game, master) {
  await verify(master, original.master, "master data");
  await verify(game, original.apk, "3.7.1 ARM64 APK");
}
