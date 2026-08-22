#!/usr/bin/env node
/**
 * Build script for the room-scan-app static site.
 *
 * There's no bundler and no dependencies: the whole app is a single
 * self-contained index.html (inline CSS + JS, fonts loaded from Google
 * Fonts). "Building" just means copying the static files Vercel should
 * serve into dist/, so `npm run build` always produces a real output
 * directory to point Vercel's "Output Directory" setting at.
 */
const fs = require("fs");
const path = require("path");

const ROOT = __dirname;
const DIST = path.join(ROOT, "dist");

// Files/folders copied as-is into dist/. Add more here if the app grows
// (e.g. a /public folder with icons).
const ASSETS = ["index.html"];

function copyRecursive(src, dest) {
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src)) {
      copyRecursive(path.join(src, entry), path.join(dest, entry));
    }
  } else {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(src, dest);
  }
}

function build() {
  if (fs.existsSync(DIST)) {
    fs.rmSync(DIST, { recursive: true, force: true });
  }
  fs.mkdirSync(DIST, { recursive: true });

  for (const asset of ASSETS) {
    const src = path.join(ROOT, asset);
    if (!fs.existsSync(src)) {
      console.error(`✗ Falta ${asset} — no se puede construir el sitio.`);
      process.exit(1);
    }
    copyRecursive(src, path.join(DIST, asset));
  }

  // Basic sanity check: make sure the copied HTML at least looks complete.
  const html = fs.readFileSync(path.join(DIST, "index.html"), "utf8");
  if (!html.includes("<html") || !html.includes("</html>")) {
    console.error("✗ index.html no parece un documento HTML completo.");
    process.exit(1);
  }

  console.log(`✓ Sitio estático generado en ${path.relative(ROOT, DIST)}/`);
}

function serve() {
  build();
  const http = require("http");
  const server = http.createServer((req, res) => {
    let reqPath = decodeURIComponent(req.url.split("?")[0]);
    if (reqPath === "/") reqPath = "/index.html";
    const filePath = path.join(DIST, reqPath);
    if (!filePath.startsWith(DIST) || !fs.existsSync(filePath)) {
      res.writeHead(404);
      res.end("Not found");
      return;
    }
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    fs.createReadStream(filePath).pipe(res);
  });
  const port = process.env.PORT || 4173;
  server.listen(port, () => {
    console.log(`→ Sirviendo ${DIST} en http://localhost:${port}`);
  });
}

if (process.argv.includes("--serve")) {
  serve();
} else {
  build();
}
