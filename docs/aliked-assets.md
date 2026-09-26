# aliked 素材与复现记录

正文：[文章源文件](../src/content/blog/sparse-feature-and-visual-recognition/aliked.md)。核查日期：2026-09-27。

共 12 图：论文原图 8，自制图 4。按正文顺序编号自制图，原图保留作者图号。

## 固定论文与原图清单

以下页码按 PDF 文件从 1 开始；裁切框在 `sources.json`，为页宽/页高归一化坐标。提图前先核对 SHA-256；不以网页后续更新的同名文件静默替换。

### ALIKED

- 来源：[固定论文](https://arxiv.org/pdf/2304.03608v2)
- 本地复现文件名：`aliked.pdf`
- SHA-256：`8ade7c4cc5752254a1da1dc3db4fc18fc42e037b646b995a742021b1d36ed8cd`

| 图号 | PDF 页 | 放置章节／省略理由 | 内容 |
| --- | --- | --- | --- |
| 1 | 3 | 2.1 多尺度特征如何同时保留位置和语义 | 多尺度编码、聚合、可微检测和稀疏描述头。共享特征是密集的，最终描述子只在关键点上构造。 |
| 2 | 5 | 3.1 从固定卷积到可学习的支持位置 | SDDH 先预测支持位置，再双线性采样、编码并融合。预测位置数 M 与初始小块边长 K 分别控制不同成本。 |
| 3 | 5 | 1.1 一次图像前向里，哪些计算真的被用到了 | 作为对照的密集描述头 DMH：先在全图做卷积，再读取关键点。它突出 SDDH 避免的冗余计算。 |
| 4 | 9 | 5.1 先分清特征匹配与重建指标 | IMW 验证集的双视匹配与多视重建。正确匹配按误差由绿到黄，错误为红；重建覆盖与匹配精度应分开看。 |
| 5 | 10 | 5.1 先分清特征匹配与重建指标 | 纹理分布不均的失败例。即使局部匹配较多，点集中在有限区域也会损害对极几何估计。 |
| 6 | 11 | 5.2 单独改变旋转和尺度，观察鲁棒性边界 | 旋转角度与尺度差异增加时的匹配精度。可变形支持区域提升部分鲁棒性，但曲线仍会下降。 |
| 7 | 12 | 5.3 消融与支持区域可视化，要分别读 | 旋转、尺度、单应与透视变换下的采样位置和有效关注区域。蓝色为关键点、红色为支持位置、绿色为影响区域。 |
| 8 | 14 | 5.4 最应该保留的一张失败图 | 尺度和视角同时剧变的困难样例。可变形描述子仍有限，增加匹配器或多尺度策略属于额外能力。 |

## 自制图与计算假设

程序精确生成 SVG；没有使用生成式位图，没有虚构模型输出。所有曲线、点阵和轨迹是教学输入或正文公式的计算，不能当论文性能复现。公式统一通过共享 MathJax/STIX2 渲染。

| 正文顺序 | 文件 | 说明 |
| --- | --- | --- |
| 1 | [aliked-sparse-cost.svg](../public/media/aliked/aliked-sparse-cost.svg) | 点标记表示最终描述子需要被计算的位置；ALIKED 仍然需要密集共享特征与分数图。 |
| 2 | [aliked-subpixel.svg](../public/media/aliked/aliked-subpixel.svg) | 按三个归一化权重计算得到 0.5 像素的连续位置；局部细化不等于 NMS 索引本身可微。 |
| 3 | [aliked-sampling.svg](../public/media/aliked/aliked-sampling.svg) | 教学示意中两幅图共享局部结构但发生剪切，支持采样位置跟随结构；真实偏移由描述损失间接学习。 |
| 4 | [aliked-supervision.svg](../public/media/aliked/aliked-supervision.svg) | 由三个相似度直接计算的 softmax 与负对数，展示温度以及困难负样本对稀疏描述训练的影响。 |

## 作者代码核查

只做源码阅读；未宣称重跑训练或论文基准。以下提交固定本文所讨论的实现。

- [Shiaoming/ALIKED @ 683d7c651973](https://github.com/Shiaoming/ALIKED/tree/683d7c65197395c0b3f01ebe76e1084a27e73a65)：`README.md`, `nets/aliked.py`, `nets/blocks.py`。

## 复现与验证

依赖 Python 3、NumPy、Pillow、PyMuPDF，及仓库 Node 依赖。PDF 放在仓库外；已发布图不需要原 PDF 即可浏览。

```bash
python3 scripts/vision-series/extract.py /absolute/path/to/papers aliked
python3 scripts/vision-series/figures.py
node scripts/vision-series/typeset.mjs
python3 scripts/vision-series/assemble.py
npm run build
```

全系列检查结果见 [制作记录](vision-series-production.md)。重新裁图后应重新运行 assemble，同步真实宽高；重新画图后应先运行 typeset，再检查实际栅格渲染和页面。
