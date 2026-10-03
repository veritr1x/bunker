// Page logic: collect the files, run the build in a worker, offer the result.
const $ = (id) => document.getElementById(id);
const worker = new Worker("worker.js");
let url = null;

const platform = () => document.querySelector("input[name=platform]:checked").value;

function update() {
  const ios = platform() === "ios";
  $("game-help").textContent = ios ? "Your decrypted 3.7.1 game IPA." : "The original 3.7.1 ARM64 game APK.";
  $("game").accept = ios ? ".ipa" : ".apk";
  $("build").disabled = !($("game").files[0] && $("master").files[0]);
}

function log(line) {
  const box = $("log");
  box.textContent += line + "\n";
  box.scrollTop = box.scrollHeight;
}

document.querySelectorAll("input[name=platform]").forEach((r) => r.addEventListener("change", update));
$("game").addEventListener("change", update);
$("master").addEventListener("change", update);

$("build").addEventListener("click", () => {
  const game = $("game").files[0], master = $("master").files[0];
  const expected = platform() === "ios" ? ".ipa" : ".apk";
  if (!game.name.toLowerCase().endsWith(expected)) { log(`Choose the game ${expected} file.`); return; }
  if (game.name === master.name) { log("Choose two different files."); return; }
  $("build").disabled = true;
  $("result").style.display = "none";
  $("log").textContent = "";
  if (url) URL.revokeObjectURL(url);
  worker.postMessage({ platform: platform(), game, master });
});

worker.onmessage = ({ data }) => {
  if (data.type === "log") log(data.value);
  if (data.type === "error") { log("Build failed: " + data.value); $("build").disabled = false; }
  if (data.type === "done") {
    const { name, bytes } = data.value;
    url = URL.createObjectURL(new Blob([bytes], { type: "application/octet-stream" }));
    $("download").href = url;
    $("download").download = name;
    $("download").textContent = `Download ${name} (${Math.round(bytes.length / 1048576)} MB)`;
    $("sign-android").hidden = name.endsWith(".ipa");
    $("sign-ios").hidden = !name.endsWith(".ipa");
    $("result").style.display = "block";
    $("build").disabled = false;
    log("Done.");
  }
};

update();
