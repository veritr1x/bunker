// The Archive's 3D viewer: one costume as glTF, lit like a studio, turned by touch.
import * as THREE from "three";
import { GLTFLoader } from "/archive-static/vendor/three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "/archive-static/vendor/three/addons/controls/OrbitControls.js";

const stage = document.getElementById("stage");
const status = document.getElementById("stage-status");
const css = getComputedStyle(document.documentElement);
const paper = new THREE.Color(css.getPropertyValue("--bg-cream").trim() || "#d3ceb8");
const ink = new THREE.Color(css.getPropertyValue("--accent").trim() || "#3a372f");

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
stage.prepend(renderer.domElement);

const scene = new THREE.Scene();
scene.background = paper;
scene.add(new THREE.HemisphereLight(0xffffff, 0x8a8470, 2.2));
const key = new THREE.DirectionalLight(0xffffff, 1.6);
key.position.set(1.5, 3, 2.5);
scene.add(key);
const grid = new THREE.GridHelper(4, 16, ink, ink);
grid.material.transparent = true;
grid.material.opacity = 0.25;
scene.add(grid);

const camera = new THREE.PerspectiveCamera(30, 1, 0.05, 50);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.autoRotate = true;
controls.autoRotateSpeed = 1.2;
let home = { position: new THREE.Vector3(0, 1, 4), target: new THREE.Vector3(0, 0.9, 0) };

function resize() {
  const { width, height } = stage.getBoundingClientRect();
  renderer.setSize(width, height, false);
  camera.aspect = width / Math.max(height, 1);
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(stage);

function frameModel(object) {
  const box = new THREE.Box3().setFromObject(object);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  // Fit the whole bounding sphere into the narrower view angle (a phone's width), so the model
  // stays in frame as it turns, with a margin; then allow zooming well in and well out.
  const vertical = THREE.MathUtils.degToRad(camera.fov / 2);
  const horizontal = Math.atan(Math.tan(vertical) * camera.aspect);
  const distance = (size.length() / 2) / Math.sin(Math.min(vertical, horizontal)) * 1.15;
  home = { position: new THREE.Vector3(center.x, center.y, center.z + distance), target: center };
  resetCamera();
  controls.minDistance = distance * 0.1;
  controls.maxDistance = distance * 4;
}

// Weapons are modelled lying along their length; stand anything much longer than it is tall
// upright, then rest it on the grid. Costumes already stand and are left alone.
function standUp(object) {
  const size = new THREE.Box3().setFromObject(object).getSize(new THREE.Vector3());
  if (size.z > size.y * 1.5 && size.z >= size.x) object.rotation.x = -Math.PI / 2;
  else if (size.x > size.y * 1.5) object.rotation.z = Math.PI / 2;
  object.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(object);
  object.position.y -= box.min.y;
  object.position.x -= (box.min.x + box.max.x) / 2;
  object.position.z -= (box.min.z + box.max.z) / 2;
}

// Everything else stands as modelled: rest it on the grid, centred.
function ground(object) {
  object.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(object);
  object.position.y -= box.min.y;
  object.position.x -= (box.min.x + box.max.x) / 2;
  object.position.z -= (box.min.z + box.max.z) / 2;
}

function resetCamera() {
  camera.position.copy(home.position);
  controls.target.copy(home.target);
  controls.update();
}

let current = null, mixer = null, action = null, rest = [];
const clock = new THREE.Clock();
const motionCache = new Map();

let wanted = null; // the latest choice: a slower, earlier fetch must not replace it

async function playMotion(button) {
  wanted = button;
  document.querySelectorAll("[data-motion]").forEach((b) => b.classList.toggle("on", b === button));
  if (!current) return;
  try {
    let clip = null;
    if (button.dataset.motion) {
      clip = motionCache.get(button.dataset.motion);
      if (!clip) {
        status.textContent = "Preparing the motion…"; status.hidden = false;
        const response = await fetch(button.dataset.motion);
        if (!response.ok) throw new Error(await response.text());
        clip = THREE.AnimationClip.parse(await response.json());
        // parse() copies json.uuid, which these clips lack; the mixer keys actions by uuid.
        clip.uuid = THREE.MathUtils.generateUUID();
        motionCache.set(button.dataset.motion, clip);
      }
    }
    if (wanted !== button) return;
    status.hidden = true;
    if (action) { action.fadeOut(0.25); action = null; }
    if (!clip) { mixer.stopAllAction(); restPose(); return; }
    action = mixer.clipAction(clip);
    action.reset().fadeIn(0.25).play();
  } catch (error) {
    if (wanted === button) { status.textContent = "This motion could not be shown."; status.hidden = false; }
  }
}
document.querySelectorAll("[data-motion]").forEach((b) => b.addEventListener("click", () => playMotion(b)));

// The pose the model was saved in. Not skeleton.pose(): the skins share bones, and Unity keeps stale bind
// matrices for bones a mesh does not use, so posing each skin from its own would scatter the others.
function restPose() {
  for (const [bone, position, quaternion, scale] of rest) {
    bone.position.copy(position); bone.quaternion.copy(quaternion); bone.scale.copy(scale);
  }
}
const loader = new GLTFLoader();
function load(url) {
  status.textContent = "Preparing the model…";
  status.hidden = false;
  loader.load(url, (gltf) => {
    if (current) scene.remove(current);
    current = gltf.scene;
    current.traverse((o) => { if (o.isSkinnedMesh) o.frustumCulled = false; });
    rest = [];
    current.traverse((o) => { if (o.isBone) rest.push([o, o.position.clone(), o.quaternion.clone(), o.scale.clone()]); });
    scene.add(current);
    if ((stage.dataset.name || "").startsWith("wp")) standUp(current); else ground(current);
    frameModel(current);
    mixer = new THREE.AnimationMixer(current);
    status.hidden = true;
    // The first field motion; a family with only battle motions starts with its first of those.
    const first = document.querySelector("[data-motion].on") || document.querySelector("[data-motion]:not([data-motion=''])")
      || document.querySelector("[data-motion]");
    if (first) playMotion(first);
  }, undefined, () => { status.textContent = "This model could not be shown."; });
}

document.getElementById("reset").addEventListener("click", resetCamera);
const spin = document.getElementById("spin");
spin.addEventListener("click", () => {
  controls.autoRotate = !controls.autoRotate;
  spin.textContent = controls.autoRotate ? "Turning" : "Still";
  spin.classList.toggle("on", controls.autoRotate);
  spin.setAttribute("aria-pressed", controls.autoRotate);
});
document.getElementById("snapshot").addEventListener("click", () => {
  const picture = renderer.domElement.toDataURL("image/png");
  const name = (stage.dataset.name || "costume") + ".png";
  // In the app, WebView ignores download links; the Bunker saves the picture where the user picks.
  if (window.bunkerFiles) { window.bunkerFiles.savePng(name, picture); return; }
  const link = document.createElement("a");
  link.href = picture;
  link.download = name;
  link.click();
});

// For checking the viewer from a debugger: the model, its mixer and the playing action.
window.archiveViewer = { get model() { return current; }, get mixer() { return mixer; }, get action() { return action; } };

renderer.setAnimationLoop(() => {
  if (mixer) mixer.update(clock.getDelta());
  controls.update();
  renderer.render(scene, camera);
});
resize();
load(stage.dataset.model);
