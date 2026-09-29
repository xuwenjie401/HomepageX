# lamp 素材与复现记录

正文：[文章源文件](../src/content/blog/3d-perception-and-project-aria/lamp.md)。核查日期：2026-09-29。

共 16 图：论文原图 12，自制图 4。按正文顺序编号自制图，原图保留作者图号。

## 固定论文与原图清单

以下页码按 PDF 文件从 1 开始；裁切框在 `sources.json`，为页宽/页高归一化坐标。提图前先核对 SHA-256；不以网页后续更新的同名文件静默替换。

### LAMP: Localization Aware Multi-camera People Tracking in Metric 3D World

- 来源：[固定论文](https://arxiv.org/pdf/2605.05390v1)
- 本地复现文件名：`lamp.pdf`
- SHA-256：`c6e4d01aee90b081d48fc6636b90662358b0788557d4df4af15a9a54bda5017e`

| 图号 | PDF 页 | 放置章节／省略理由 | 内容 |
| --- | --- | --- | --- |
| 1 | 1 | 开篇 | 相机接力下的长时轨迹与多人的广视场覆盖。 |
| 2 | 3 | 2. LAMP 的整体分工：检测、关联与拟合 | 先检测与关联，再把射线变换到局部世界坐标，最后拟合人体运动。 |
| 3 | 4 | 缺失观测需要显式表达 | 同一人跨四个单色相机被观察，世界射线维持统一的运动表示。 |
| 4 | 5 | 7. 滑动窗口平均：精度、稳定与延迟一起变化 | 重叠窗口对同一时刻给出多个预测；平均能稳定输出，也会引入等待。 |
| 5 | 6 | Nymeria 更接近自然头部运动的挑战 | Nymeria 上的世界坐标顶点误差；深紫较低，黄色较高。 |
| 6 | 6 | 9. 消融和覆盖率：新信息究竟贡献在哪里？ | 一、二、四相机的跟踪覆盖率分布及样例；关注质量向完整覆盖一侧移动。 |
| 7 | 7 | 10. 留下哪些失败，为什么值得保留？ | EMDB 根轨迹误差；滑板序列保留了 LAMP 的不利结果。 |
| 8 | 14 | 9. 消融和覆盖率：新信息究竟贡献在哪里？ | Aria Gen 2 实时多人演示；这里的演示人体模型使用 MHR。 |
| 9 | 15 | Nymeria 更接近自然头部运动的挑战 | Nymeria 补充比较：单目、窗口平均与多视角的差异。 |
| 10 | 15 | EMDB 证明的不是“所有指标都领先” | EMDB 单目零样本结果；图中人体颜色表示世界顶点误差。 |
| 11 | 16 | 7. 滑动窗口平均：精度、稳定与延迟一起变化 | RTX 4090 上随 tracklet 数增长的分模块运行时间。 |
| 12 | 16 | 7. 滑动窗口平均：精度、稳定与延迟一起变化 | 等待帧数、世界关节误差与抖动之间的权衡。 |

## 自制图与计算假设

程序精确生成 SVG；没有使用生成式位图，没有虚构模型输出。所有曲线、点阵和轨迹是教学输入或正文公式的计算，不能当论文性能复现。公式统一通过共享 MathJax/STIX2 渲染。

| 正文顺序 | 文件 | 说明 |
| --- | --- | --- |
| 1 | [lamp-world.svg](../public/media/lamp/lamp-world.svg) | 一维度量示例：观察者前进 0.5 m，静止目标的相机坐标从 2 m 变为 1.5 m，世界坐标保持 2 m。 |
| 2 | [lamp-rays.svg](../public/media/lamp/lamp-rays.svg) | 三种二维截面的教学几何。世界射线仍不能消除小基线深度不确定性，也不能让不同时刻的移动关节自动成为同一点。 |
| 3 | [lamp-loss.svg](../public/media/lamp/lamp-loss.svg) | 教学轨迹只在中间一帧偏移 0.1 m，却改变了两个时间间隔的增量。论文的 velocity loss 比较离散差分，不能直接省略采样间隔后称为 m/s。 |
| 4 | [lamp-latency.svg](../public/media/lamp/lamp-latency.svg) | 以 30 Hz、120 帧窗口示意滑窗平均的未来依赖。图中只画四个稀疏窗口以便阅读；实际窗口步长与实时输出策略另行决定。 |

## 作者代码核查

只做源码阅读；未宣称重跑训练或论文基准。以下提交固定本文所讨论的实现。

- [facebookresearch/LAMP @ db3e4bf99928](https://github.com/facebookresearch/LAMP/tree/db3e4bf9992874a85946b92e9c8933bba396bc44)：`lamp/models/model.py`, `lamp/models/model_utils.py`, `lamp/models/lifter.py`, `lamp/tracking/smoothing.py`, `README.md`。

论文的 120 帧评测设置与当前 LifterSettings 默认 20 帧分开说明；发布模型附带可选地面条件，并将关键点可见性二值化。未重跑论文指标。


## 复现与验证

依赖 Python 3、NumPy、Pillow、PyMuPDF，及仓库 Node 依赖。PDF 放在仓库外；已发布图不需要原 PDF 即可浏览。

```bash
python3 scripts/aria-series/extract.py /absolute/path/to/papers lamp
python3 scripts/aria-series/figures.py
node scripts/aria-series/typeset.mjs
python3 scripts/aria-series/assemble.py
npm run build
```

全系列检查结果见 [制作记录](aria-series-production.md)。重新裁图后应重新运行 assemble，同步真实宽高；重新画图后应先运行 typeset，再检查实际栅格渲染和页面。
