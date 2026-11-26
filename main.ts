// make.fun entry runner.
// Publishes the pre-rendered 25 Nov 2026 poster into the grader's output dir.
// Node 22 standard library only: no network, no image libraries.
import {
  chmodSync,
  closeSync,
  copyFileSync,
  existsSync,
  mkdirSync,
  openSync,
  readSync,
  statSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const poster = resolve(root, "entry.png");
const outDir = resolve(process.env.MAKEFUN_OUTPUT_DIR || "/output");
const target = join(outDir, "entry.png");
const LIMIT = 1024 * 1024;

function die(message) {
  console.error(`[entry] ${message}`);
  process.exit(1);
}

if (!existsSync(poster)) {
  die(`poster not found next to main.ts: ${poster}`);
}

mkdirSync(outDir, { recursive: true });
copyFileSync(poster, target);
chmodSync(target, 0o644);

const size = statSync(target).size;
if (size === 0) die("wrote an empty file");
if (size > LIMIT) die(`output is ${size} bytes, over the 1 MiB gate`);

// The gate detects the format from the first bytes; verify it really is a PNG
// before declaring success, so a corrupted repo file fails loudly here.
const fd = openSync(target, "r");
const signature = Buffer.alloc(8);
readSync(fd, signature, 0, 8, 0);
closeSync(fd);
if (signature.toString("hex") !== "89504e470d0a1a0a") {
  die("output is not a PNG (bad signature)");
}

console.log(`published ${target} (${size} bytes, mode 0644)`);
