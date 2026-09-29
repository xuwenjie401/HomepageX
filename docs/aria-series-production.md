# 3D Perception and Project Aria 制作记录

核查日期：2026-09-29。五篇中文精读沿用现有科研博客的页面、分级目录和 MathJax/STIX2 排版，新增独立专题入口。专栏已通过提交 `3fd1ed0` 推送至 `main`，[GitHub Pages 发布成功](https://github.com/xuwenjie401/HomepageX/actions/runs/36556600820)，并已核对[正式专题页](https://xuwenjie401.github.io/HomepageX/blog/3d-perception-and-project-aria/)的五篇文章链接。

## 内容与图像覆盖

| 文章 | 固定论文版本 | 原图范围 | 原图 | 自制图 | 合计 | 素材记录 |
| --- | --- | --- | ---: | ---: | ---: | --- |
| BoxerNet / Boxer | 2604.05212v1 | Figure 1–10 | 10 | 4 | 14 | [记录](boxernet-assets.md) |
| LAMP | 2605.05390v1 | Figure 1–12 | 12 | 4 | 16 | [记录](lamp-assets.md) |
| HMD² | 2409.13426v2 | Figure 1–9 | 9 | 4 | 13 | [记录](hmd2-assets.md) |
| EgoForce | 2605.12498v1 | Figure 1–19 | 19 | 4 | 23 | [记录](egoforce-assets.md) |
| Photoreal Scene Reconstruction from an Egocentric Device | 2506.04444v1 | Figure 1–10 | 10 | 4 | 14 | [记录](photoreal-egocentric-reconstruction-assets.md) |
| 总计 | | 全部编号原图，无省略 | 60 | 20 | 80 | |

正文按问题、机制、监督、实验与边界组织；原图放在对应论证旁，并保留作者图号。附录的失败样例、消融、时延曲线、尺寸分桶和标定扰动均有解释。自制图覆盖尺度歧义、深度聚合、异方差损失、动态融合失败、世界坐标、射线病态、速度监督、未来帧等待、环境距离编码、条件扩散、窗口回写、裁块内参、点到线求解、滚动快门、曝光积分和行号图变换。

## 固定来源与实现差异

- [sources.json](../scripts/aria-series/sources.json) 保存论文作者、版本、链接、PDF SHA-256、页码、归一化裁切框和图注。
- [code-sources.json](../scripts/aria-series/code-sources.json) 保存四个作者仓库的固定提交、阅读文件和发现的差异。HMD² 按主文与附录解释，核查时项目页没有代码入口。
- Boxer 的论文中位深度与当前稀疏点分支均值、LAMP 的论文 120 帧与发布设置 20 帧、Photoreal 的论文采样描述与代码默认上限分别说明。Boxer 朝向平均明确使用 180 度对称的倍角均值。
- 实验数据摘自固定论文的原表；没有重跑训练或基准。GT 框、额外深度、用户骨长、离线地图、延迟和数据切分等条件在对应正文中说明。

## 复现

需 Python 3、NumPy、Pillow、PyMuPDF；Node 依赖使用仓库的 `npm ci`。字体使用 Noto Sans CJK，数学通过仓库共享渲染器输出自包含的 STIX2 字形路径。

将五份固定 PDF 放在仓库外，并命名为 `boxer.pdf`、`lamp.pdf`、`hmd2.pdf`、`egoforce.pdf`、`photoreal.pdf`：

```bash
python3 scripts/aria-series/extract.py /absolute/path/to/papers
python3 scripts/aria-series/figures.py
node scripts/aria-series/typeset.mjs
python3 scripts/aria-series/assemble.py
npm run check
npm run build
python3 scripts/aria-series/validate.py
npm run preview
```

原图默认渲染倍率 3.3（约 238 DPI）、WebP quality 94。LAMP Figure 11/12 在 PDF 中仅占小图块，按元数据使用倍率 10，以保留图例与坐标刻度。60 张原图加 20 张 SVG 约 10 MB。网页只依赖已生成素材，浏览和构建不需要下载原始 PDF。

自制图的投影、曲线、残差和颜色均由 [figures.py](../scripts/aria-series/figures.py) 确定性计算；概念骨架与曲线是教学输入。比如 Boxer 动态融合示意使用位置 640、710、780 与权重 1、0.5、1.5，融合位置为 721.666…；这组绘图坐标不代表米或真实模型结果。Photoreal 行号图使用系数 0.35 的教学径向映射，不代表 Aria 标定参数。

## 已执行的验证

- `npm run check`：24 个 Astro 文件，0 errors / warnings / hints。
- `npm run build`：专栏首次构建生成 25 个页面；随后删除两篇初始示例文章，构建生成 23 个页面，并确认旧路由与列表链接均移除。同时检查实际文章正文，避免仅凭构建退出码判断成功。
- [validate.py](../scripts/aria-series/validate.py)：80 张图的覆盖、真实尺寸、alt、大图链接；122 个二级／三级标题；330 处数学渲染节点；无重复锚点、无数学错误节点、无悬空本站文章链接。
- 原图逐张联系表检查，并放大裁切边界和密集图。修正了标题、坐标刻度、底部标签和侧视面板截断；图注没有混入相邻正文。
- 20 张自制 SVG 经 Sharp 栅格化目视检查；另用 Chromium 检查所有顶层文本／数学组的边界，均在画布内。
- Chromium 实际浏览器在 1440×1000 与 390×1000 视口逐篇检查；五篇的页面 `scrollWidth` 分别等于 1440 / 390。无图片加载失败，无页面脚本错误。
- 每篇均操作目录跳转；桌面目录保持展开并有当前章节提示，手机初始收起、可展开、跳转后收起。长公式与表格在自身区域横向滚动，页面整体不溢出。
- 博客首页、专题入口和站点首页在两个视口均无横向溢出；专题显示五篇并按指定阅读顺序排列。

临时 PDF、上游代码 checkout、整页图片、浏览器截图与运行缓存均位于仓库外。可复用的源码核查与 LaTeX 字符串经验已归入 [制作与排查指南](research-blog-production.md)。
