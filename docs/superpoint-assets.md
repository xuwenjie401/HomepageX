# SuperPoint 文章素材与复现

文章：`src/content/blog/superpoint.md`。页面共 30 张图：原论文 Figure 1–15，加上 15 张自制解释图。原始论文 PDF、临时渲染和检查截图留在仓库外。

## 原论文图

来源：[SuperPoint，arXiv:1712.07629v4](https://arxiv.org/pdf/1712.07629v4)，2018-04-19 版本，获取于 2026-09-26。原图属于相应权利人，不适用仓库代码的 MIT 许可。正文只保留图号、解读与出处链接。

| Figure | PDF 页码 | 内容 |
| --- | --- | --- |
| 1 | 1 | 特征与对应关系 |
| 2 | 2 | 三阶段训练 |
| 3 | 3 | 双分支网络 |
| 4 | 4 | 合成预训练 |
| 5 | 5 | Homographic Adaptation |
| 6 | 5 | 单应采样组成 |
| 7 | 6 | 迭代适应 |
| 8 | 8 | HPatches 匹配与失败例 |
| 9 | 11 | Synthetic Shapes 类别 |
| 10 | 11 | 分类别精度与定位误差 |
| 11 | 11 | 噪声强度 |
| 12 | 11 | 噪声类型 |
| 13 | 12 | 附加 blob-center 监督与感受野 |
| 14 | 12 | 聚合次数与尺度消融 |
| 15 | 13 | 附录匹配实例 |

裁剪矩形保存在 `scripts/extract-superpoint-figures.py`；使用系统 Poppler 260 DPI 渲染、Pillow WebP quality=95 编码。不改变原始数据或图形结构。重生成：

```bash
python3 scripts/extract-superpoint-figures.py /absolute/path/to/paper.pdf
```

正文表格来自该版本 Table 3、4；噪声、感受野、消融的解读以相应原图和附录为准。

## 自制图

全部文件位于 `public/media/superpoint/`。SVG 提供 title/desc，正文有中文 alt、真实尺寸与原尺寸链接。

| 生成脚本 | 输出 |
| --- | --- |
| `scripts/draw-superpoint.py` | learning-path、align-before-average、cell-decoder |
| `scripts/draw-superpoint-scientific.py` | patch-localization、inference-pipeline |
| `scripts/draw-superpoint-limitations.py` | limitation-parallax、ambiguity、context、detector、subpixel |
| `scripts/draw-superpoint-math.py` | homography-photo、loss-overview、loss-detector、loss-correspondence、loss-hinge |

前三个脚本只需 Python 标准库；第四个需要 Pillow、numpy。数学字形统一使用 MathJax 4 的 STIX2（Times 风格），与文章同一个 `scripts/lib/math.mjs` 渲染器，构建时输出 SVG 路径。不需要浏览器安装 Times New Roman。

```bash
python3 scripts/draw-superpoint.py
python3 scripts/draw-superpoint-scientific.py
python3 scripts/draw-superpoint-limitations.py
python3 scripts/draw-superpoint-math.py
node scripts/typeset-figure-math.mjs
npm run check
npm run build
```

绘图后必须运行最后的数学排版命令；该命令只转换尚未排版的 `$…$` 标签，可重复运行。改动公式或字形时从 Python 脚本开始重生成，不能只改输出 SVG。

### 示意图的数值与含义

- patch-localization：定性的平坦、单向和双向误差形状，不是 SuperPoint 热力图或真实 SSD 测量。
- inference-pipeline：B 图按已知单应变换生成，正确连线由该变换决定，错误连线手动构造。
- parallax：墙面移动 −24、前景移动 −65 像素，按背景对齐后残差 41 像素。
- ambiguity、context、detector：解释重复纹理、上下文和候选缺失；不是 R2D2、SuperGlue、LoFTR 的真实输出或完整架构。
- subpixel：人工位置 (2.35, 2.20)、整数位置 (2, 2)，以及人工高斯响应，说明双峰平均可能落在低谷。
- loss-detector：目标概率从 0.10 到 0.80，负自然对数为 2.303 和 0.223。
- loss-correspondence：投影源点为 (4,0)、(16,16)，目标中心为 (0,0)、(8,0)、(16,16)，阈值为 8，矩阵两行分别是 [1,1,0]、[0,0,1]。
- loss-hinge：精确绘制 max(0,1−a)、max(0,a−0.2)，正项暂不乘 250；相似度 0.7 时函数值 0.3、0.5。

### 写实场景与精确单应变换

`homography-source.webp` 是生成的写实桌面源素材，960×720。生成工具为内置 ImageGen，源文件为 `/home/wjxu22/.codex/generated_images/01a0ddc0-74f7-7b43-8c9b-63e95944abd5/exec-41e8bebb-dde8-4da2-a488-1e1b075bdbfb.png`。仓库内保留优化后的源素材即可复现后续全部结果，无需重新调用生成工具。

`draw-superpoint-math.py` 将它缩放至 640×480，添加固定网格，使用 Pillow 的逆向透视采样。五个矩阵及四个彩点保存在 `homography-matrices.json`。透视矩阵为 `[[1,.12,20],[.04,1,-10],[.0006,-.00025,1]]`。有效区域以白色源图使用相同矩阵生成；所有面板的画布一致。照片内的像素纹理是生成素材，矩阵、坐标和变换结果是确定计算。

生成源图使用的完整提示词：

> Use case: photorealistic-natural. Asset type: source photograph for a scientific tutorial demonstrating exact homography warps; only generate one original photograph, no diagrams or panels. A sharp natural photograph looking almost straight down at a realistic pale oak desk, with a closed dark blue hardcover notebook slightly left of center, a single cream square sheet of graph paper with a fine grey square grid slightly right of center, a yellow wooden pencil diagonally near the bottom, a small dark ceramic coffee cup near upper right. Plenty of wood grain and crisp recognizable object corners, natural daylight from the left, soft short shadows, deep focus across the scene, realistic material textures. Landscape 4:3 composition with all objects comfortably inside the image and some margin. No labels, no readable text, no branding, no watermarks, no arrows, no borders. This will be the same fixed pixel image subjected to mathematically exact affine and projective transforms later, so prioritize natural sharp edges, visible parallel lines on the notebook and grid paper, and consistent photographic perspective.

通用叙事、公式、配图与目录要求见 [论文详解技术博客原则](research-blog-style.md)；本次制作中的工程经验见 [制作与排查指南](research-blog-production.md)。
