import fs from 'fs';
import path from 'path';

const root = process.cwd();
const out = path.join(root, 'www');
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(out, { recursive: true });

const filesToCopy = [
  'index.html', 'manifest.json', 'sw.js', 'opening.mp4',
  'icon-192.png', 'icon-512.png', 'og-preview.jpg',
  'privacy.html', 'delete-account.html'
];
for (const f of filesToCopy) {
  const src = path.join(root, f);
  if (fs.existsSync(src)) fs.copyFileSync(src, path.join(out, f));
}

// Copy studio voices & spouse portraits cleanly into www/src/assets/
for (const sub of ['src/assets/voices', 'src/assets/spouses', 'src/assets/models', 'src/assets/cutouts']) {
  const srcDir = path.join(root, sub);
  if (fs.existsSync(srcDir)) {
    const dstDir = path.join(out, sub);
    fs.mkdirSync(dstDir, { recursive: true });
    for (const fn of fs.readdirSync(srcDir)) {
      fs.copyFileSync(path.join(srcDir, fn), path.join(dstDir, fn));
    }
  }
}
console.log('[prepare:web] Built clean Android web bundle in ./www');
