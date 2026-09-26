/** Replace $TeX$ labels in generated SVGs with the same STIX2 glyphs as the article. */
import { readFile, writeFile, readdir } from 'node:fs/promises';
import { renderMath, escapeHTML } from './lib/math.mjs';
const folder = new URL('../public/media/superpoint/', import.meta.url);
const decode = s => s.replaceAll('&lt;', '<').replaceAll('&gt;', '>').replaceAll('&quot;', '"').replaceAll('&#x27;', "'").replaceAll('&amp;', '&');
for (const name of await readdir(folder)) {
  if (!name.endsWith('.svg')) continue;
  let source = await readFile(new URL(name, folder), 'utf8');
  const labels = [...source.matchAll(/<text\b([^>]*)>([^<]*\$[^<]*)<\/text>/g)];
  for (const [original, attrs, escaped] of labels) {
    const attr = (key, fallback) => attrs.match(new RegExp(`(?:^|\\s)${key}="([^"]*)"`))?.[1] ?? fallback;
    const size = Number(attr('font-size', '22'));
    const x = Number(attr('x', '0')), y = Number(attr('y', '0'));
    const anchor = attr('text-anchor', 'start');
    const chunks = decode(escaped).split(/\$([^$]+)\$/);
    const runs = [];
    for (let i = 0; i < chunks.length; i++) {
      if (!chunks[i]) continue;
      if (i % 2) {
        const svg = (await renderMath(chunks[i])).match(/<svg\b[\s\S]*<\/svg>/)[0];
        const [vx, vy, vw, vh] = svg.match(/viewBox="([^"]+)"/)[1].split(' ').map(Number);
        // MathJax SVG coordinates are 1000 units per em.
        const width = vw / 1000 * size, height = vh / 1000 * size;
        const body = svg.replace(/<svg\b[^>]*>/, '').replace(/<\/svg>$/, '');
        runs.push({ width, draw: offset => `<svg x="${offset}" y="${y + vy / 1000 * size}" width="${width}" height="${height}" viewBox="${vx} ${vy} ${vw} ${vh}">${body}</svg>` });
      } else {
        const text = chunks[i];
        const width = [...text].reduce((n, c) => n + (c.charCodeAt(0) > 255 ? 1 : c === ' ' ? .28 : .55), 0) * size;
        runs.push({ width, draw: offset => `<text ${attrs.replace(/\s(?:x|text-anchor)="[^"]*"/g, '')} x="${offset}" text-anchor="start" xml:space="preserve">${escapeHTML(text)}</text>` });
      }
    }
    const width = runs.reduce((n, r) => n + r.width, 0);
    let cursor = x - (anchor === 'middle' ? width / 2 : anchor === 'end' ? width : 0);
    const rendered = runs.map(run => { const result = run.draw(cursor); cursor += run.width; return result; }).join('');
    source = source.replace(original, `<g color="${attr('fill', '#202a35')}" aria-label="${escaped}">${rendered}</g>`);
  }
  if (labels.length) { await writeFile(new URL(name, folder), source); console.log(`${name}: ${labels.length} math labels`); }
}
