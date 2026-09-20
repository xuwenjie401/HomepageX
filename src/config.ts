export const site = {
  title: 'HomepageX',
  name: 'Xuwenjie',
  description: '记录思考、分享探索，也收藏日常的小小发现。',
  github: 'https://github.com/xuwenjie401',
};

// Centralize the project prefix so links also work on GitHub project Pages.
export const withBase = (path = '') =>
  `${import.meta.env.BASE_URL.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;

