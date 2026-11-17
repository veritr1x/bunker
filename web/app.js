// Page logic: collect the files, run the build in a worker, offer the result.
const $ = (id) => document.getElementById(id);
const worker = new Worker("worker.js");
let url = null;
let building = false;  // One build at a time, however fast the button is pressed.

// The Bunker version this site builds (version.json, written by build_site.py).
fetch("version.json").then((r) => r.ok ? r.json() : null).then((v) => {
  if (v && v.version) $("bunker-version").textContent = "BUILDS BUNKER " + v.version;
}).catch(() => {});

const platform = () => document.querySelector("input[name=platform]:checked").value;

function update() {
  const ios = platform() === "ios";
  $("game-help").textContent = ios ? "Your decrypted 3.7.1 game IPA." : "Original 3.7.1 ARM64 APK: Global (English/Korean) or Japanese (experimental).";
  $("game").accept = ios ? ".ipa" : ".apk";
  $("master-help").innerHTML = ios ? "The original master data, <code>20240404193219.bin.e</code>."
    : "The original master data: <code>20240404193219.bin.e</code> for the Global APK, <code>20240405123139.bin.e</code> for the Japanese APK.";
  const identity = checkIdentity();
  $("build").disabled = !($("game").files[0] && $("master").files[0]) || !identity.ok;
  for (const id of ["game", "master"]) {
    const file = $(id).files[0], chip = $(id + "-name");
    chip.textContent = file ? `${file.name} · ${Math.max(1, Math.round(file.size / 1048576))} MB` : "NOT CHOSEN";
    chip.classList.toggle("ok", !!file);
  }
}

// A second copy's App ID and Name (app_identity.js; the build checks the same rules again).
function checkIdentity() {
  const ios = platform() === "ios";
  $("app-id-hint").textContent = ios ? "iOS: letters, digits and -, in parts separated by dots."
    : "Android: letters, digits and _, in parts separated by dots, each starting with a letter.";
  const result = checkAppIdentity(platform(), $("app-id").value, $("app-name").value, Number($("port-offset").value || 0));
  for (const [field, id] of [["appId", "app-id"], ["appName", "app-name"], ["portOffset", "port-offset"]]) {
    const message = result.errors[field] || result.warnings[field] || "";
    const box = $(id + "-error");  // Rewritten only when it changes: screen readers announce each change.
    if (box.textContent !== message) box.textContent = message;
    box.classList.toggle("warning", !result.errors[field] && !!message);
    $(id).setAttribute("aria-invalid", result.errors[field] ? "true" : "false");
  }
  return { ok: Object.keys(result.errors).length === 0, appId: result.appId, appName: result.appName };
}

function log(line) {
  const box = $("log");
  box.textContent += line + "\n";
  box.scrollTop = box.scrollHeight;
}

document.querySelectorAll("input[name=platform]").forEach((r) => r.addEventListener("change", update));
$("game").addEventListener("change", update);
$("master").addEventListener("change", update);
for (const id of ["app-id", "app-name", "port-offset"]) $(id).addEventListener("input", update);

$("build").addEventListener("click", () => {
  if (building) return;
  const game = $("game").files[0], master = $("master").files[0];
  if (!game || !master) { log("Choose the game file and the master data first."); return; }
  const expected = platform() === "ios" ? ".ipa" : ".apk";
  if (!game.name.toLowerCase().endsWith(expected)) { log(`Choose the game ${expected} file.`); return; }
  if (game.name === master.name) { log("Choose two different files."); return; }
  const portOffset = Number($("port-offset").value || 0);
  if (!Number.isInteger(portOffset) || portOffset < 0 || portOffset > 57455) { log("The port offset must be a whole number from 0 to 57455."); return; }
  const identity = checkIdentity();
  if (!identity.ok) { log("Correct the second-copy settings first."); return; }
  building = true;
  $("build").disabled = true;
  $("result").style.display = "none";
  $("log").textContent = "";
  if (url) URL.revokeObjectURL(url);
  worker.postMessage({ platform: platform(), game, master, portOffset, appId: identity.appId, appName: identity.appName });
});

worker.onmessage = ({ data }) => {
  if (data.type === "log") log(data.value);
  if (data.type === "error") { log("Build failed: " + data.value); building = false; $("build").disabled = false; }
  if (data.type === "done") {
    const { name, blob } = data.value;
    url = URL.createObjectURL(blob);
    $("download").href = url;
    $("download").download = name;
    $("download").textContent = `Download ${name} (${Math.round(blob.size / 1048576)} MB)`;
    $("sign-android").hidden = name.endsWith(".ipa");
    $("play-windows").hidden = name.endsWith(".ipa");
    $("sign-ios").hidden = !name.endsWith(".ipa");
    $("result").style.display = "block";
    building = false;
    $("build").disabled = false;
    log("Done.");
  }
};

update();
