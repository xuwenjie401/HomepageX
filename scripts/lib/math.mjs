import { mathjax } from '@mathjax/src/js/mathjax.js';
import { TeX } from '@mathjax/src/js/input/tex.js';
import { SVG } from '@mathjax/src/js/output/svg.js';
import { liteAdaptor } from '@mathjax/src/js/adaptors/liteAdaptor.js';
import { RegisterHTMLHandler } from '@mathjax/src/js/handlers/html.js';
import { MathJaxStix2Font } from '@mathjax/mathjax-stix2-font/js/svg.js';
import '@mathjax/src/js/util/asyncLoad/esm.js';
import '@mathjax/src/js/input/tex/ams/AmsConfiguration.js';
import '@mathjax/src/js/input/tex/newcommand/NewcommandConfiguration.js';

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
const document = mathjax.document('', {
  InputJax: new TeX({ packages: ['base', 'ams', 'newcommand'], formatError: (_jax, error) => { throw error; } }),
  OutputJax: new SVG({ fontData: MathJaxStix2Font, fontCache: 'none', linebreaks: { inline: false } }),
});
export const escapeHTML = value => value.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
export async function renderMath(tex, display = false) {
  const node = await document.convertPromise(tex, { display, em: 16, ex: 8, containerWidth: 740 });
  return adaptor.outerHTML(node);
}
export default function remarkPaperMath() {
  return async tree => {
    async function walk(node) {
      if (node.type === 'math' || node.type === 'inlineMath') {
        const display = node.type === 'math';
        const source = node.value;
        const html = await renderMath(source, display);
        node.type = 'html';
        node.value = `<${display ? 'div' : 'span'} class="${display ? 'math-display' : 'math-inline'}" role="math" aria-label="${escapeHTML(source)}">${html}</${display ? 'div' : 'span'}>`;
        delete node.data;
      } else if (node.children) {
        for (const child of node.children) await walk(child);
      }
    }
    await walk(tree);
  };
}
