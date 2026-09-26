import { defineConfig } from 'astro/config';
import { unified } from '@astrojs/markdown-remark';
import remarkMath from 'remark-math';
import remarkPaperMath from './scripts/lib/math.mjs';

export default defineConfig({
  site: 'https://xuwenjie401.github.io',
  base: '/HomepageX',
  trailingSlash: 'always',
  output: 'static',
  markdown: { processor: unified({ remarkPlugins: [remarkMath, remarkPaperMath] }) },
});
