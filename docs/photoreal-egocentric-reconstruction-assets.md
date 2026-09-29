# photoreal-egocentric-reconstruction 素材与复现记录

正文：[文章源文件](../src/content/blog/3d-perception-and-project-aria/photoreal-egocentric-reconstruction.md)。核查日期：2026-09-29。

共 14 图：论文原图 10，自制图 4。按正文顺序编号自制图，原图保留作者图号。

## 固定论文与原图清单

以下页码按 PDF 文件从 1 开始；裁切框在 `sources.json`，为页宽/页高归一化坐标。提图前先核对 SHA-256；不以网页后续更新的同名文件静默替换。

### Photoreal Scene Reconstruction from an Egocentric Device

- 来源：[固定论文](https://arxiv.org/pdf/2506.04444v1)
- 本地复现文件名：`photoreal.pdf`
- SHA-256：`a759fa539037863c37f0a25f14bf96af30736bc47a437c4c1ef52e3e1b0c3132`

| 图号 | PDF 页 | 放置章节／省略理由 | 内容 |
| --- | --- | --- | --- |
| 1 | 1 | 开篇 | 暗且含噪的留出图像、普通重建、本文重建及提高渲染增益后的对照。 |
| 2 | 3 | 设备定位精度与像素对齐精度不是一回事 | Aria 传感器布局；RGB、SLAM 相机和 IMU 的角色不同。 |
| 3 | 4 | 从 VIO、闭环 SLAM 到联合调整 | VIO、闭环 SLAM 与 VIBA；逐行曝光要求高频轨迹与准确时间标定。 |
| 4 | 5 | 一个小角度，在高分辨率图像里就是许多像素 | 读出期间的重投影运动及其时间分布，说明一帧一个位姿可能差很多像素。 |
| 5 | 8 | 换到 Quest 3，是有依据的迁移，但样本仍有限 | Quest 3 场景中使用与不使用 VIBA 的细节差异。 |
| 6 | 9 | 9. 消融：标定、运动采样、颜色表示各有证据 | 与 Splatfacto、3DGS-on-move 的跨场景视觉比较。 |
| 7 | 10 | 9. 消融：标定、运动采样、颜色表示各有证据 | VIBA、运动采样和场景 gamma 的定性消融；关注文字、细杆与暗部。 |
| 8 | 13 | 8. 实验协议：哪些视角没有参加训练？ | 多种室内外场景的半稠密点云与 RGB 视角。 |
| 9 | 13 | 一条输出行可能来自多条原始传感器行 | 校正后的源行号图；相同输出行不再对应相同的曝光时刻。 |
| 10 | 14 | 10. 看起来像照片，几何是否也变好了？ | DTC 上 3D-GS 与 2D-GS 的颜色、深度和法线重建。 |

## 自制图与计算假设

程序精确生成 SVG；没有使用生成式位图，没有虚构模型输出。所有曲线、点阵和轨迹是教学输入或正文公式的计算，不能当论文性能复现。公式统一通过共享 MathJax/STIX2 渲染。

| 正文顺序 | 文件 | 说明 |
| --- | --- | --- |
| 1 | [photoreal-timing.svg](../public/media/photoreal-egocentric-reconstruction/photoreal-timing.svg) | 以 16 ms 读出、100°/s 转动和 1200 px 焦距计算跨行位移约 33.5 px。示意图夸大斜率便于阅读；实际位移随场景点位置与相机模型变化。 |
| 2 | [photoreal-exposure.svg](../public/media/photoreal-egocentric-reconstruction/photoreal-exposure.svg) | 采用指数为 1/2.2 的教学 gamma 响应，积分后编码为约 0.743，先编码再平均为约 0.616。色块按计算值绘制。 |
| 3 | [photoreal-rowmap.svg](../public/media/photoreal-egocentric-reconstruction/photoreal-rowmap.svg) | 以确定的教学径向映射逐格计算原始行号；白色等时线由数值求根得到。映射系数 0.35 保存在脚本中，不代表 Aria 标定。 |
| 4 | [photoreal-sampling.svg](../public/media/photoreal-egocentric-reconstruction/photoreal-sampling.svg) | 匀速教学例，用不同数量的曝光时刻采样表达快慢运动的区别；图中的 2 与 9 是示意采样数，不是论文每帧固定配置。 |

## 作者代码核查

只做源码阅读；未宣称重跑训练或论文基准。以下提交固定本文所讨论的实现。

- [facebookresearch/egocentric_splats @ 516dfe23d1c7](https://github.com/facebookresearch/egocentric_splats/tree/516dfe23d1c7dec54cea1696ff840f3790cfb95b)：`scene/cameras.py`, `model/vanilla_gsplat.py`。

论文的时间采样描述与当前代码默认上限不同：滚动快门上限 8，曝光内上限 1。正文区分物理积分模型、可用分支与默认配置；未将注释中的 16 当作执行值。


## 复现与验证

依赖 Python 3、NumPy、Pillow、PyMuPDF，及仓库 Node 依赖。PDF 放在仓库外；已发布图不需要原 PDF 即可浏览。

```bash
python3 scripts/aria-series/extract.py /absolute/path/to/papers photoreal
python3 scripts/aria-series/figures.py
node scripts/aria-series/typeset.mjs
python3 scripts/aria-series/assemble.py
npm run build
```

全系列检查结果见 [制作记录](aria-series-production.md)。重新裁图后应重新运行 assemble，同步真实宽高；重新画图后应先运行 typeset，再检查实际栅格渲染和页面。
