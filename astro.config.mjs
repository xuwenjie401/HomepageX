import { defineConfig } from 'astro/config';
import { unified } from '@astrojs/markdown-remark';
import remarkMath from 'remark-math';
import remarkPaperMath from './scripts/lib/math.mjs';

export default defineConfig({
  site: 'https://xuwenjie401.github.io',
  base: '/HomepageX',
  trailingSlash: 'always',
  output: 'static',
  redirects: {
    '/blog/superpoint/': '/HomepageX/blog/sparse-feature-and-visual-recognition/superpoint/',
  },
  markdown: { processor: unified({ remarkPlugins: [remarkMath, remarkPaperMath] }) },
});
