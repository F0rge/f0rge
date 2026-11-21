// Writes dist/artifact.html: the HTML fragment published as the claude.ai Artifact.
import { existsSync, writeFileSync } from 'node:fs';

const FONTS =
  'https://fonts.googleapis.com/css2?family=Geist:wght@100..900&family=Instrument+Serif&display=swap';
for (const f of ['dist/assets/app.js', 'dist/assets/app.css', 'dist/arc-front.jpg']) {
  if (!existsSync(f)) throw new Error(`missing ${f}: did vite build run?`);
}
writeFileSync(
  'dist/artifact.html',
  [
    '<title>DasKasas Blocks</title>',
    `<link rel="stylesheet" href="${FONTS}">`,
    '<link rel="stylesheet" href="assets/app.css">',
    '<div id="root"></div>',
    '<script type="module" src="assets/app.js"></script>',
    '',
  ].join('\n'),
);
console.log('wrote dist/artifact.html');
