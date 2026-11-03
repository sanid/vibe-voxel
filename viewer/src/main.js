import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { decodeChunk, loadChunkRecords, loadIndex } from './chunks.js';
import { BERLIN, berlinOffsetHours, parseDay, sunAt } from './sun.js';

const TILE = '392_5820';
const BASE = `/chunks/${TILE}`;
// World origin: the tile centre, so the scene sits near 0 (positions are relative to it).
const CENTRE = new THREE.Vector3(500, 0, -500);
const ALEX = new THREE.Vector3(300, 40, 100); // Alexanderplatz, local (800, 400)

const canvas = document.getElementById('scene');
const statusEl = document.getElementById('status');
const hourEl = document.getElementById('hour');
const dateEl = document.getElementById('date');
const sunEl = document.getElementById('sun');
const resetBtn = document.getElementById('reset');

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight, false);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
const SKY_DAY = new THREE.Color('#bcd3e6');
scene.background = SKY_DAY.clone();

const camera = new THREE.PerspectiveCamera(40, window.innerWidth / window.innerHeight, 1, 6000);
const resetView = () => {
  camera.position.copy(ALEX).add(new THREE.Vector3(-160, 130, 260));
  controls.target.copy(ALEX);
  controls.update();
};
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.maxPolarAngle = Math.PI * 0.49;
controls.minDistance = 10;
controls.maxDistance = 2500;
resetView();
resetBtn.addEventListener('click', resetView);

const hemi = new THREE.HemisphereLight(0xdfeaff, 0x6b6253, 0.6);
scene.add(hemi);

const sun = new THREE.DirectionalLight(0xfff1dc, 2.4);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
const sc = sun.shadow.camera;
sc.left = -620; sc.right = 620; sc.top = 620; sc.bottom = -620; sc.near = 1; sc.far = 3000;
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 0.6;
sun.target.position.set(0, 0, 0);
scene.add(sun, sun.target);


function updateSun() {
  const day = parseDay(dateEl.value);
  const hour = Number(hourEl.value);
  const offset = berlinOffsetHours(new Date(day.getTime() + hour * 3600000));
  const s = sunAt(day, hour, offset);
  const up = Math.max(0, s.up);
  const dir = new THREE.Vector3(s.east, s.up, -s.north).normalize();
  sun.position.copy(dir.clone().multiplyScalar(1400));
  sun.intensity = s.up > 0 ? 0.2 + 2.6 * Math.sqrt(up) : 0;
  hemi.intensity = 0.25 + 0.5 * Math.sqrt(up);
  const dayFactor = Math.min(1, Math.max(0, (s.elevation + 0.05) / 0.2));
  scene.background.copy(new THREE.Color('#0d1424').lerp(SKY_DAY, dayFactor));

  const hh = String(Math.floor(hour)).padStart(2, '0');
  const mm = String(Math.round((hour % 1) * 60)).padStart(2, '0');
  const elDeg = (s.elevation * 180) / Math.PI;
  const azFromNorth = ((Math.atan2(s.east, s.north) * 180) / Math.PI + 360) % 360;
  sunEl.textContent = `${hh}:${mm} CEST · sun ${elDeg.toFixed(0)}° high, ${azFromNorth.toFixed(0)}° from north` +
    (s.up <= 0 ? ' (below horizon)' : '');
}

hourEl.addEventListener('input', updateSun);
dateEl.addEventListener('input', updateSun);

async function load() {
  const index = await loadIndex(BASE);
  const entries = index.chunks.filter((c) => c.quads > 0);
  let done = 0;
  let quads = 0;
  for (const entry of entries) {
    const view = await loadChunkRecords(BASE, entry);
    const g = decodeChunk(view, [CENTRE.x, CENTRE.y, CENTRE.z]);
    const geom = new THREE.BufferGeometry();
    geom.setAttribute('position', new THREE.BufferAttribute(g.positions, 3));
    geom.setAttribute('normal', new THREE.BufferAttribute(g.normals, 3));
    geom.setAttribute('color', new THREE.BufferAttribute(g.colors, 3));
    geom.setIndex(new THREE.BufferAttribute(g.indices, 1));
    geom.computeBoundingSphere();
    const mesh = new THREE.Mesh(geom, new THREE.MeshLambertMaterial({ vertexColors: true }));
    mesh.position.copy(CENTRE);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);
    quads += g.quads;
    done += 1;
    statusEl.textContent = `loading ${done}/${entries.length} chunks`;
  }
  statusEl.textContent = `${entries.length} chunks · ${quads.toLocaleString('en')} quads`;
  window.__loaded = { chunks: entries.length, quads };
}

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight, false);
});

updateSun();
load().catch((err) => {
  statusEl.textContent = `failed: ${err.message}`;
  console.error(err);
});

renderer.setAnimationLoop(() => {
  controls.update();
  renderer.render(scene, camera);
});

// Berlin constant, exported for the status line and for tests.
window.__berlin = BERLIN;
