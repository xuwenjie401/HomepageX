export const sparseFeatureSeries = {
  slug: 'sparse-feature-and-visual-recognition',
  title: 'Sparse Feature and Visual Recognition',
  description: '从局部特征、学习型匹配与视觉识别，到里程计和回环优化。沿着十篇图文详解，连接前端表示与后端几何。',
  order: [
    'gftt-klt-sift',
    'superpoint',
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

export const ariaPerceptionSeries = {
  slug: '3d-perception-and-project-aria',
  title: '3D Perception and Project Aria',
  description: '从第一人称观测走向三维世界：物体框、他人运动、自身动作、手部几何与照片级场景。沿着五篇论文，理解定位、射线、学习先验与物理成像如何互相补足。',
  order: ['boxernet', 'lamp', 'hmd2', 'egoforce', 'photoreal-egocentric-reconstruction'],
};

export const blogSeries = [sparseFeatureSeries, ariaPerceptionSeries];

export const getPostSeries = (id: string) =>
  blogSeries.find(series => id.startsWith(`${series.slug}/`));
