# 开发与维护说明

## 本地开发

需要 Node.js 22.12+（建议使用最新 Node.js 22 LTS）和 npm。

```sh
npm ci
npm run dev
```

打开终端输出的地址，并访问 `/HomepageX/`，通常为 `http://localhost:4321/HomepageX/`。

```sh
npm run check   # Astro 与 TypeScript 检查
npm run build   # 生成 dist/ 静态网站
npm run preview # 本地预览构建结果
```

## 修改个人信息

- `src/config.ts`：站点名称、显示姓名、介绍、GitHub 链接。
- `src/pages/index.astro`：首页介绍。
- `src/pages/about.astro`：个人简介。
- `src/styles/global.css`：颜色与排版。

当前姓名根据 GitHub 用户名暂设为 Xuwenjie，简介是通用占位内容。两篇文章均标记为“示例文章”，可以直接删除或替换。

## 写文章

在 `src/content/blog/` 新建 `my-first-post.md`：

```markdown
---
title: "我的第一篇文章"
description: "一句话介绍这篇文章。"
date: 2026-09-20
tags: [学习, 随笔]
draft: false
---

## 今天的发现

从这里开始写正文。
```

文件名对应文章地址 `/HomepageX/blog/my-first-post/`。文章按日期从新到旧排列；设置 `draft: true` 后，文章不会出现在列表中，也不会生成公开页面。注意：公开 Git 仓库内的草稿源文件仍可被别人阅读。

## 图片与小视频

把经过压缩的图片、短视频放在 `public/media/` 下，建议按文章分目录，例如 `public/media/my-first-post/`。原始大图、原始视频在仓库外另行保存。

正文插入图片（请先放入对应真实文件）：

```html
<img src="/HomepageX/media/my-first-post/photo.webp"
     alt="对照片内容的描述" loading="lazy" width="1200" height="800" />
```

正文插入短视频：

```html
<video controls playsinline preload="none"
       aria-label="实验过程短视频">
  <source src="/HomepageX/media/my-first-post/demo.mp4" type="video/mp4" />
  你的浏览器不支持视频播放。
</video>
```

默认不自动播放，`preload="none"` 提示浏览器不要提前下载视频。含对白的视频建议补充字幕 `<track>` 或文字说明。有封面时可加 `poster="/HomepageX/media/my-first-post/poster.webp"`。

长视频发布到 Bilibili，再将平台提供的播放器嵌入代码放入 Markdown，或直接使用视频链接。嵌入时关闭自动播放；普通视频链接兼容性更好。

所有本地媒体链接都要包含项目路径 `/HomepageX/`。更换仓库名或独立域名时，需要同步修改正文中的媒体链接。

## 免费发布到 GitHub Pages

远程仓库：`git@github.com:xuwenjie401/HomepageX.git`。

1. 在 GitHub 仓库的 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
2. 将代码提交并推送到 `main`。`.github/workflows/deploy.yml` 会运行类型检查、构建并发布。
3. 如果已经推送过，启用 Pages 后可在 **Actions → Deploy to GitHub Pages → Run workflow** 手动运行。

预计发布地址：<https://xuwenjie401.github.io/HomepageX/>（需要工作流成功后才会上线）。

GitHub Free 使用公开仓库时支持免费 Pages；不需要购买服务器、对象存储或域名。本项目不会开通任何收费服务。私有仓库能否免费使用 Pages 取决于账户计划。

Pages 已发布网站上限为 1 GB，每月带宽软限制为 100 GB。媒体仍需控制总量，建议每个小视频压缩到几 MB，并为网站其他内容预留空间；这不是无限媒体存储。Git 会保留历史文件，删除旧视频不会自动清理仓库历史。

参考：[Astro 部署说明](https://docs.astro.build/en/guides/deploy/github/) · [GitHub Pages 使用限制](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)

## 目录

```text
.github/workflows/deploy.yml  自动发布流程
public/media/                 本地图片和短视频
src/content/blog/             Markdown 文章
src/components/               文章列表组件
src/layouts/                  共用页面布局
src/pages/                    首页、博客、关于、404
src/styles/global.css         全站样式
src/content.config.ts         文章字段校验
src/config.ts                 个人信息与链接配置
astro.config.mjs              GitHub Pages 域名与项目路径
```
