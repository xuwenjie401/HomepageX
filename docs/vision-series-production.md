# 从局部特征到回环优化：九篇文章制作记录

九篇正文、配图、素材记录和复现脚本已完成，已做本地构建及浏览器检查。制作与核查日期：2026-09-26 至 2026-09-27。

2026-09-27 按用户要求归入 **Sparse Feature and Visual Recognition** 专题。源码目录为 `src/content/blog/sparse-feature-and-visual-recognition/`，公开入口为 [专题目录](https://xuwenjie401.github.io/HomepageX/blog/sparse-feature-and-visual-recognition/)。博客首页显示专题入口，专题内按九篇阅读顺序排列；正文交叉引用和返回导航均使用新路径。发布通过仓库既有 GitHub Pages 工作流执行。

读者入口见 [九篇阅读导航](vision-series-reading-guide.md)。写作依据为 [论文详解原则](research-blog-style.md)、[制作指南](research-blog-production.md) 与 [SuperPoint 范文](../src/content/blog/superpoint.md)。

## 交付范围

| 文章 | 图片数 | 素材与来源记录 |
| --- | ---: | --- |
| [GFTT、KLT 与 SIFT](../src/content/blog/sparse-feature-and-visual-recognition/gftt-klt-sift.md) | 42 | [清单](gftt-klt-sift-assets.md) |
| [SuperGlue 与 LightGlue](../src/content/blog/sparse-feature-and-visual-recognition/superglue-lightglue.md) | 24 | [清单](superglue-lightglue-assets.md) |
| [NetVLAD 与 HF-Net](../src/content/blog/sparse-feature-and-visual-recognition/netvlad-hfnet.md) | 29 | [清单](netvlad-hfnet-assets.md) |
| [DINOv2 / DINOv3 的训练](../src/content/blog/sparse-feature-and-visual-recognition/dinov2-dinov3.md) | 37 | [清单](dinov2-dinov3-assets.md) |
| [基础模型怎样改变 VPR 与局部对应](../src/content/blog/sparse-feature-and-visual-recognition/foundation-model-vpr-features.md) | 41 | [清单](foundation-model-vpr-features-assets.md) |
| [TartanAir 与学习型里程计](../src/content/blog/sparse-feature-and-visual-recognition/tartanair.md) | 24 | [清单](tartanair-assets.md) |
| [LET-NET 与 LET-NET2](../src/content/blog/sparse-feature-and-visual-recognition/letnet.md) | 11 | [清单](letnet-assets.md) |
| [ALIKED](../src/content/blog/sparse-feature-and-visual-recognition/aliked.md) | 12 | [清单](aliked-assets.md) |
| [从回环检测到图优化与 BA](../src/content/blog/sparse-feature-and-visual-recognition/loop-closure.md) | 78 | [清单](loop-closure-assets.md) |

共 298 幅图，其中 244 幅论文原图、54 幅程序生成示意图。盘点 24 份固定论文的 254 幅编号图；省略的 10 幅是 VINS-Mono 的控制／移动端应用图与 OKVIS2-X 的部分深度、网格、GNSS 和标定扩展图，逐项理由在对应素材清单中。原图保留作者图号，自制图按各篇阅读顺序编号。

第 5 篇以 AnyLoc、SALAD、SelaVPR、DeDoDe、RoMa 展开，分别解释聚合、适配、稀疏点与稠密匹配的不同变化。第 9 篇共 64 个二至三级标题，覆盖回环前的图维护、视觉／惯性因子、消元与边缘化、几何验证、误差传播、地图融合及异步提交，并对照 ORB-SLAM2/3、VINS-Fusion、OKVIS/2/2-X。

LET-NET2 使用用户指定的 [作者仓库](https://github.com/linyicheng1/LET-NET2/tree/4713802d256ecf3bb463837e80b9d3d0ccba5a1a)。其分析固定于提交 `4713802d256ecf3bb463837e80b9d3d0ccba5a1a`，单独说明真值附近初始化、三通道输出、仅启用光流损失等实现事实。

## 来源与复现

- [sources.json](../scripts/vision-series/sources.json)：论文 URL、SHA-256、全部编号图、PDF 页码、归一化裁切框、中文解读及省略原因。
- [code-sources.json](../scripts/vision-series/code-sources.json)：9 个作者仓库的固定提交与所读文件。
- [extract.py](../scripts/vision-series/extract.py)：验证论文哈希，按清单提取 WebP 原图。
- [figures.py](../scripts/vision-series/figures.py) 与 [typeset.mjs](../scripts/vision-series/typeset.mjs)：生成示意图并通过共享 MathJax/STIX2 排版公式；图中数值、曲线与几何均有明确计算输入。
- [assemble.py](../scripts/vision-series/assemble.py)：生成正文配图块与各篇素材记录，校验原图覆盖，更新真实宽高和自制图编号。
- [verify-examples.py](../scripts/vision-series/verify-examples.py)：核验关键教学计算。
- [validate.py](../scripts/vision-series/validate.py)：检查构建后的页面完整性、媒体与数学节点。

原始 PDF、代码快照、栅格预览、浏览器截图及运行日志均在仓库外的临时制作目录，未加入发布素材。网页浏览只依赖仓库内的压缩图与 SVG。没有运行完整网络训练或重现论文基准，正文中的论文成绩、代码事实和教学例子分别标明。

## 实际验证结果

### 内容与媒体

- 原图逐组查看裁切预览，自制图经栅格化检查全部 54 幅；修正过双栏面板、横轴、扫描图号、数学标签和几何示意。
- 298 幅图均有可解码文件、准确尺寸、alt、图注和原尺寸链接；图号覆盖与素材清单一致。
- 九篇构建产物均有完整正文，共 250 个二至三级标题、563 个数学节点，未发现重复 ID、失效的站内文章链接、失效目录锚点或数学错误节点。
- 教学数值检查通过：LK 正规方程、SuperGlue／SALAD 边缘质量、交叉熵、稀疏 NRE、亚像素加权坐标、Gram 正交不变性、Schur 消元、投影 Jacobian 有限差分、Sim(3) 投影等价以及回环误差按方差分配。

### 构建与阅读

- 初次正文验收时 `npm run build` 通过，18 个静态页面生成完整；构建日志无内容加载和 TeX 错误。归入专题后新增 1 个目录页。
- 初次正文验收时 `npm run check`：19 个文件，0 errors、0 warnings、0 hints；归入专题后检查 22 个文件，同样无错误、警告与提示。
- 桌面实际视口宽 1691px、手机实际视口宽 390px，逐篇检查九个页面：无整页横向溢出，目录条目数与标题数一致，已加载图片无损坏。
- 实际查看 Schur 消元、IMU 预积分与 Gram anchoring 等密集公式段落；桌面目录高亮正确，手机目录跳转后收起。实际点击 Gram 插图，在新标签页打开完整 SVG。检查结束已恢复桌面视口。
- 专题改动另外在 1280px 桌面与 390px 手机视口检查：首页默认显示 1 个专题和 3 篇独立文章，跨目录搜索可找到新文章；无匹配提示及清空恢复正常。专题页包含按指定顺序排列的 9 篇文章，搜索限于专题；文章面包屑与底部链接均返回专题，页面无横向溢出。迁移后九篇媒体、数学和站内链接的产物检查全部通过。

此次修复了共享数学渲染器缺少 `boldsymbol` 扩展的问题。首次构建虽退出成功，但内容加载器留下空正文；注册扩展并强制同步内容后，重新构建、检查全部九篇产物，才计为通过。经验已写入 [制作指南](research-blog-production.md)。

## 后续修改时的检查入口

```bash
python3 scripts/vision-series/verify-examples.py
npm run build
python3 scripts/vision-series/validate.py
```

修改数学渲染器、Astro 模板或 TypeScript 时另外运行 `npm run check`。改变原图裁切或自制图后按各篇素材记录重新生成，并补做受影响图与网页段落的目视检查。
