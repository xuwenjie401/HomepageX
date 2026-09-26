# superglue-lightglue 素材与复现记录

正文：[文章源文件](../src/content/blog/sparse-feature-and-visual-recognition/superglue-lightglue.md)。核查日期：2026-09-27。

共 24 图：论文原图 20，自制图 4。按正文顺序编号自制图，原图保留作者图号。

## 固定论文与原图清单

以下页码按 PDF 文件从 1 开始；裁切框在 `sources.json`，为页宽/页高归一化坐标。提图前先核对 SHA-256；不以网页后续更新的同名文件静默替换。

### SuperGlue

- 来源：[固定论文](https://openaccess.thecvf.com/content_CVPR_2020/papers/Sarlin_SuperGlue_Learning_Feature_Matching_With_Graph_Neural_Networks_CVPR_2020_paper.pdf)
- 本地复现文件名：`superglue.pdf`
- SHA-256：`79b367ea82e7eb3cdff2ddf4bf153d29acf4da8c4f18f1466ce877adc18bd383`

| 图号 | PDF 页 | 放置章节／省略理由 | 内容 |
| --- | --- | --- | --- |
| 1 | 1 | 1. 先把输出定义正确：有些点就不该有伙伴 | 局部检测器、SuperGlue 与几何后端的接口。SuperGlue 接收已有点和描述子，输出带未匹配判断的对应。 |
| 2 | 2 | 1. 先把输出定义正确：有些点就不该有伙伴 | 困难室内图像对的匹配，连线按对极误差着色。看重复结构与视角变化中的错误连线，不能只比较总匹配数。 |
| 3 | 3 | 2.1 位置不是标签，而是关系推理的输入 | 关键点编码、交替自注意力/交叉注意力和最优传输的完整结构。沿着描述子变化追踪上下文如何进入最终分配。 |
| 4 | 4 | 2.2 Self-attention 看自己这张图，cross-attention 看另一张图 | 自注意力与交叉注意力的权重可视化。自注意力能够连接同图远处的可区分区域，不受局部窗口限制。 |
| 5 | 6 | 4. 监督从哪里来：不是把最近邻当真值 | 室内与室外位姿估计对比。应在相同局部特征与误差阈值下比较，避免把特征更换的收益都归因于匹配器。 |
| 6 | 8 | 4. 监督从哪里来：不是把最近邻当真值 | 与最近邻加外点过滤的定性比较。绿色为正确对应、红色为错误对应，重点看重复纹理与视角变化下的内点覆盖。 |
| 7 | 8 | 2.2 Self-attention 看自己这张图，cross-attention 看另一张图 | 不同层和注意力头关注不同信息。图中同时出现局部、全局、自相似和候选匹配模式，不应给所有头赋予同一种语义。 |

### LightGlue

- 来源：[固定论文](https://arxiv.org/pdf/2306.13643v1)
- 本地复现文件名：`lightglue.pdf`
- SHA-256：`2d77fcdfdc38cc4704bee343092502f819e9c7119ca4fd907ef10f2efa47891f`

| 图号 | PDF 页 | 放置章节／省略理由 | 内容 |
| --- | --- | --- | --- |
| 1 | 1 | 5. LightGlue：容易的图像对为什么也要算到底 | 匹配速度与位姿精度的折中。曲线上的不同点包含提前停止等设置，不能只取最快和最准的两端拼成一个配置。 |
| 2 | 2 | 5. LightGlue：容易的图像对为什么也要算到底 | 容易与困难图像对需要不同深度。上方容易样本较早停止，下方难样本继续聚合上下文。 |
| 3 | 3 | 5. LightGlue：容易的图像对为什么也要算到底 | 每层既更新描述，也估计匹配与判断置信度。停止深度与点剪枝是两个不同的自适应维度。 |
| 4 | 4 | 5.3 三种“分数”不能互换 | 逐层剔除不可匹配点。先排除视野不重叠区域，再逐渐识别不重复的检测点。 |
| 5 | 5 | 6.2 Confidence 的标签来自最终决定的一致性 | 单应预训练的收敛速度比较。这里衡量训练图像对数量与训练目标，不是最终真实场景定位成功率。 |
| 6 | 8 | 7. 读实验：快了多少，要和什么一起看 | 可匹配性对错误对应的过滤。视觉上相似的点也可能没有真实对应，matchability 提供额外拒绝能力。 |
| 7 | 8 | 7. 读实验：快了多少，要和什么一起看 | 运行时间随关键点数变化。自适应深度与宽度共同影响耗时，点数不同不宜直接比较单个毫秒数。 |
| 8 | 9 | 7. 读实验：快了多少，要和什么一起看 | 由易到难的图像对，同时展示剪枝、可匹配性与最终连线。注意困难样本何时仍需后续层。 |
| 9 | 10 | 7. 读实验：快了多少，要和什么一起看 | 同一匹配框架接收 SIFT、SuperPoint、DISK 的结果。输入特征的检测覆盖不同，匹配器无法补回没有检测的点。 |
| 10 | 12 | 7.1 失败图比平均时间更能暴露边界 | InLoc 失败案例：重复物体和强纹理可能胜过真正的几何结构。高置信匹配仍需后端几何验证。 |
| 11 | 13 | 7.2 自适应省掉的是哪些计算 | 不可匹配点随层数逐步被识别。曲线说明剪枝判断是在推理中累积证据，而非一次阈值筛除。 |
| 12 | 14 | 6.2 Confidence 的标签来自最终决定的一致性 | 合成单应预训练样本，包含透视和强光度增强。平面变换监督仍不能覆盖真实三维遮挡的全部变化。 |
| 13 | 15 | 7.2 自适应省掉的是哪些计算 | 固定 1024 点的模块耗时拆分。双向交叉注意力复用与更轻的分配层是速度收益的重要来源。 |

## 自制图与计算假设

程序精确生成 SVG；没有使用生成式位图，没有虚构模型输出。所有曲线、点阵和轨迹是教学输入或正文公式的计算，不能当论文性能复现。公式统一通过共享 MathJax/STIX2 渲染。

| 正文顺序 | 文件 | 说明 |
| --- | --- | --- |
| 1 | [matching-context.svg](../public/media/superglue-lightglue/matching-context.svg) | 重复窗格产生一对多歧义；稳定邻域关系提供附加证据，但没有可区分结构时上下文也会失败。 |
| 2 | [matching-dustbin.svg](../public/media/superglue-lightglue/matching-dustbin.svg) | 一个满足 SuperGlue 扩展边缘约束的硬分配极限：a3 未匹配，空槽之间的质量用于平衡矩阵。 |
| 3 | [matching-supervision.svg](../public/media/superglue-lightglue/matching-supervision.svg) | 教学概率矩阵展示标签与负对数监督；这些示意概率不代表 Sinkhorn 完整扩展矩阵。 |
| 4 | [lightglue-pruning.svg](../public/media/superglue-lightglue/lightglue-pruning.svg) | 点剪枝并非直接删掉低匹配分数点；应结合对最终判断的置信度，防止过早删除尚未消歧的点。 |

## 作者代码核查

只做源码阅读；未宣称重跑训练或论文基准。以下提交固定本文所讨论的实现。

- [cvg/LightGlue @ eb42fee2d714](https://github.com/cvg/LightGlue/tree/eb42fee2d71449efb0aa5c10549752b5d75384d8)：`README.md`, `lightglue/lightglue.py`。

## 复现与验证

依赖 Python 3、NumPy、Pillow、PyMuPDF，及仓库 Node 依赖。PDF 放在仓库外；已发布图不需要原 PDF 即可浏览。

```bash
python3 scripts/vision-series/extract.py /absolute/path/to/papers superglue lightglue
python3 scripts/vision-series/figures.py
node scripts/vision-series/typeset.mjs
python3 scripts/vision-series/assemble.py
npm run build
```

全系列检查结果见 [制作记录](vision-series-production.md)。重新裁图后应重新运行 assemble，同步真实宽高；重新画图后应先运行 typeset，再检查实际栅格渲染和页面。
