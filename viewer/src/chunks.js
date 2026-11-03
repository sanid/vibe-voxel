// Load raw chunks and turn their 16-byte quads into triangle buffers.
// Record layout: pipeline/greedy_mesher.py (x y z w h normal material flags reserved).

const NORMAL_AXIS = [0, 0, 1, 1, 2, 2];       // xyz axis of each normal id
const NORMAL_SIGN = [1, -1, 1, -1, 1, -1];

// Voxel space (x east, y north, z up) -> three.js world (x east, y up, z south).
const toWorld = (x, y, z) => [x, z, -y];

export async function loadIndex(base) {
  const res = await fetch(`${base}/index.json`);
  if (!res.ok) throw new Error(`index.json: HTTP ${res.status}`);
  return res.json();
}

export async function loadChunkRecords(base, entry) {
  const res = await fetch(`${base}/${entry.file}`);
  if (!res.ok) throw new Error(`${entry.file}: HTTP ${res.status}`);
  return new DataView(await res.arrayBuffer());
}

// Colour per material id (materials.py). Values are sRGB 0..1.
export const PALETTE = {
  1: [0.42, 0.55, 0.33],  // ground: grass and paving, until OSM materials arrive
  2: [0.76, 0.70, 0.62],  // building body
  3: [0.84, 0.78, 0.66],  // wall: sandstone and render
  4: [0.60, 0.30, 0.24],  // roof: terracotta
  5: [0.33, 0.24, 0.18],  // trunk
  6: [0.36, 0.60, 0.29],  // linden
  7: [0.48, 0.56, 0.29],  // plane
  8: [0.23, 0.45, 0.22],  // oak
  9: [0.40, 0.62, 0.34],  // other trees
  10: [1.0, 0.15, 0.10],  // beacon
};

const toLinear = (c) => Math.pow(c, 2.2);

// Decode one chunk into typed arrays for a single BufferGeometry.
// offset: world-space origin subtracted from every vertex (keeps float32 precise).
export function decodeChunk(view, offset) {
  const n = view.byteLength / 16;
  const positions = new Float32Array(n * 12);
  const normals = new Float32Array(n * 12);
  const colors = new Float32Array(n * 12);
  const indices = new Uint32Array(n * 6);
  let v = 0;
  let i = 0;

  for (let q = 0; q < n; q++) {
    const o = q * 16;
    const x = view.getUint16(o, true);
    const y = view.getUint16(o + 2, true);
    const z = view.getUint16(o + 4, true);
    const w = view.getUint16(o + 6, true);
    const h = view.getUint16(o + 8, true);
    const nid = view.getUint8(o + 10);
    const mat = view.getUint8(o + 11);

    const axis = NORMAL_AXIS[nid];
    const sign = NORMAL_SIGN[nid];
    const [t0, t1] = [0, 1, 2].filter((a) => a !== axis);

    const p = [x, y, z];
    const add = (base, axisIdx, amount) => { const r = base.slice(); r[axisIdx] += amount; return r; };
    const c0 = p;
    const c1 = add(p, t0, w);
    const c2 = add(c1, t1, h);
    const c3 = add(p, t1, h);
    const corners = [c0, c1, c2, c3].map((c) => toWorld(c[0], c[1], c[2]));

    // Unit normal in world space (the same linear map applied to a vector).
    const nv = [0, 0, 0];
    nv[axis] = sign;
    const [nx, ny, nz] = toWorld(nv[0], nv[1], nv[2]);

    // Triangle winding must agree with the normal (CCW seen from outside).
    const a = corners[0], b = corners[1], c = corners[2];
    const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2];
    const vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
    const cx = uy * vz - uz * vy, cy = uz * vx - ux * vz, cz = ux * vy - uy * vx;
    const flip = cx * nx + cy * ny + cz * nz < 0;

    // Slight per-quad brightness so large flat areas are not one flat colour.
    const hash = (((x * 73856093) ^ (y * 19349663) ^ (z * 83492791)) >>> 0) % 1000;
    const jitter = 0.94 + 0.12 * (hash / 1000);
    const base = PALETTE[mat] ?? [1, 0, 1];
    const col = base.map((ch) => toLinear(Math.min(1, ch * jitter)));

    const base0 = v / 3;
    for (let k = 0; k < 4; k++) {
      const pw = corners[k];
      positions[v] = pw[0] - offset[0];
      positions[v + 1] = pw[1] - offset[1];
      positions[v + 2] = pw[2] - offset[2];
      normals[v] = nx; normals[v + 1] = ny; normals[v + 2] = nz;
      colors[v] = col[0]; colors[v + 1] = col[1]; colors[v + 2] = col[2];
      v += 3;
    }
    if (flip) {
      indices[i++] = base0; indices[i++] = base0 + 2; indices[i++] = base0 + 1;
      indices[i++] = base0; indices[i++] = base0 + 3; indices[i++] = base0 + 2;
    } else {
      indices[i++] = base0; indices[i++] = base0 + 1; indices[i++] = base0 + 2;
      indices[i++] = base0; indices[i++] = base0 + 2; indices[i++] = base0 + 3;
    }
  }
  return { positions, normals, colors, indices: indices.subarray(0, i), quads: n };
}
