export const sparseFeatureSeries = {
  slug: 'sparse-feature-and-visual-recognition',
  title: 'Sparse Feature and Visual Recognition',
  description: '从局部特征、学习型匹配与视觉识别，到里程计和回环优化。沿着九篇图文详解，连接前端表示与后端几何。',
  order: [
    'gftt-klt-sift',
    'superglue-lightglue',
    'netvlad-hfnet',
    'dinov2-dinov3',
    'foundation-model-vpr-features',
    'tartanair',
    'letnet',
    'aliked',
    'loop-closure',
  ],
};

export const blogSeries = [sparseFeatureSeries];

export const getPostSeries = (id: string) =>
  blogSeries.find(series => id.startsWith(`${series.slug}/`));
