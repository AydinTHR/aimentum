/**
 * Renders the app icons from one mark definition so every size stays in sync.
 *
 *   node scripts/generate-icons.mjs
 *
 * The mark is an "A" whose apex doubles as an arrowhead: the product is about
 * momentum toward a goal. It is drawn as three round-capped strokes and
 * rasterized from a signed distance field, which antialiases cleanly at every
 * size and needs no image library.
 */
import { deflateSync } from "node:zlib";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "icons");

const EMERALD = [52, 211, 153]; // emerald-400, the accent used across the UI
const TOP = [24, 24, 27]; // zinc-900
const BOTTOM = [9, 9, 11]; // zinc-950

/** Strokes in unit space, drawn inside a box the caller places and scales. */
const STROKES = [
  { a: [0.5, 0.16], b: [0.16, 0.84], w: 0.15 },
  { a: [0.5, 0.16], b: [0.84, 0.84], w: 0.15 },
  { a: [0.31, 0.62], b: [0.69, 0.62], w: 0.13 },
];

function distanceToSegment(px, py, [ax, ay], [bx, by]) {
  const dx = bx - ax;
  const dy = by - ay;
  const lengthSquared = dx * dx + dy * dy;
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSquared));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

/** Coverage of the mark at a point, 0 to 1, antialiased over one pixel. */
function markCoverage(px, py, scale, offset, aa) {
  const ux = (px - offset) / scale;
  const uy = (py - offset) / scale;
  let coverage = 0;
  for (const stroke of STROKES) {
    const signed = distanceToSegment(ux, uy, stroke.a, stroke.b) - stroke.w / 2;
    const alpha = 1 - smoothstep(-aa / scale, aa / scale, signed);
    coverage = Math.max(coverage, alpha);
  }
  return coverage;
}

function smoothstep(edge0, edge1, x) {
  const t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

/** Coverage of a rounded square filling the canvas, 0 to 1. */
function squircleCoverage(px, py, size, radius, aa) {
  const half = size / 2;
  const dx = Math.abs(px - half) - (half - radius);
  const dy = Math.abs(py - half) - (half - radius);
  const outside = Math.hypot(Math.max(dx, 0), Math.max(dy, 0));
  const signed = outside + Math.min(Math.max(dx, dy), 0) - radius;
  return 1 - smoothstep(-aa, aa, signed);
}

function blend(base, over, alpha) {
  return base + (over - base) * alpha;
}

/**
 * @param {object} options
 * @param {number} options.size          pixel dimensions
 * @param {number} options.cornerRatio   0 for a full-bleed square
 * @param {number} options.markRatio     mark width as a fraction of the canvas
 * @param {boolean} options.transparent  monochrome mark on alpha, for badges
 */
function render({ size, cornerRatio, markRatio, transparent = false }) {
  const pixels = Buffer.alloc(size * size * 4);
  const markScale = size * markRatio;
  const markOffset = (size - markScale) / 2;
  const radius = size * cornerRatio;
  const aa = 0.75;

  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const px = x + 0.5;
      const py = y + 0.5;
      const mark = markCoverage(px, py, markScale, markOffset, aa);
      const index = (y * size + x) * 4;

      if (transparent) {
        pixels[index] = 255;
        pixels[index + 1] = 255;
        pixels[index + 2] = 255;
        pixels[index + 3] = Math.round(mark * 255);
        continue;
      }

      const background = squircleCoverage(px, py, size, radius, aa);
      const shade = py / size;
      const base = [0, 1, 2].map((channel) => blend(TOP[channel], BOTTOM[channel], shade));
      const rgb = [0, 1, 2].map((channel) => blend(base[channel], EMERALD[channel], mark));
      pixels[index] = Math.round(rgb[0]);
      pixels[index + 1] = Math.round(rgb[1]);
      pixels[index + 2] = Math.round(rgb[2]);
      pixels[index + 3] = Math.round(background * 255);
    }
  }
  return pixels;
}

const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

function toPng(pixels, size) {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header[8] = 8; // bit depth
  header[9] = 6; // truecolour with alpha
  // Filter byte 0 (none) in front of every scanline: the shapes are smooth
  // gradients, so a smarter filter would buy very little.
  const raw = Buffer.alloc(size * (size * 4 + 1));
  for (let y = 0; y < size; y += 1) {
    raw[y * (size * 4 + 1)] = 0;
    pixels.copy(raw, y * (size * 4 + 1) + 1, y * size * 4, (y + 1) * size * 4);
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const TARGETS = [
  { file: "icon-192.png", size: 192, cornerRatio: 0.22, markRatio: 0.58 },
  { file: "icon-512.png", size: 512, cornerRatio: 0.22, markRatio: 0.58 },
  // Maskable icons get cropped to a circle on some launchers, so the mark
  // stays well inside the 80% safe zone and the background is full bleed.
  { file: "maskable-512.png", size: 512, cornerRatio: 0, markRatio: 0.44 },
  // iOS applies its own mask and never wants transparency.
  { file: "apple-touch-icon.png", size: 180, cornerRatio: 0, markRatio: 0.56 },
  { file: "badge.png", size: 96, cornerRatio: 0, markRatio: 0.8, transparent: true },
];

mkdirSync(OUT, { recursive: true });
for (const target of TARGETS) {
  writeFileSync(join(OUT, target.file), toPng(render(target), target.size));
  console.log(`wrote ${target.file} (${target.size}x${target.size})`);
}
