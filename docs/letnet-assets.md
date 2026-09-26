# letnet 素材与复现记录

正文：[文章源文件](../src/content/blog/sparse-feature-and-visual-recognition/letnet.md)。核查日期：2026-09-27。

共 11 图：论文原图 7，自制图 4。按正文顺序编号自制图，原图保留作者图号。

## 固定论文与原图清单

以下页码按 PDF 文件从 1 开始；裁切框在 `sources.json`，为页宽/页高归一化坐标。提图前先核对 SHA-256；不以网页后续更新的同名文件静默替换。

### LET-NET

- 来源：[固定论文](https://arxiv.org/pdf/2310.15655v1)
- 本地复现文件名：`letnet.pdf`
- SHA-256：`04f22b0d3d899f5572a929f15b6ad2542bc8f70217d952406a64f4148cdc76c1`

| 图号 | PDF 页 | 放置章节／省略理由 | 内容 |
| --- | --- | --- | --- |
| 1 | 1 | 1.1 正确位置也可能有很大的灰度误差 | 亮度变化下灰度 LK 与学习特征跟踪的对比。关注光照变化处的跟踪失效，而不只是角点数量。 |
| 2 | 2 | 2.1 网络究竟输出什么 | 浅网络分别产生跟踪特征和角点分数；金字塔 LK 与前后向检查在网络输出后执行。 |
| 3 | 4 | 2.2 为什么训练时需要额外的深网络 | 训练时的深描述分支提供可靠性监督，推理移除；它与浅三通道跟踪特征的职责不同。 |
| 4 | 4 | 3.2 Line peaky loss：别让角点长成一条亮线 | 直线形高响应与峰状响应的区别。line peaky 约束针对沿边缘延伸的分数脊，而不是任意提高分数。 |
| 5 | 5 | 5.2 光照变化、运动模糊与系统收益 | 室内、室外、主动光源和散射模糊的测试图像。饱和造成的信息丢失仍不能靠不变性恢复。 |
| 6 | 6 | 5.2 光照变化、运动模糊与系统收益 | 跟踪存活比例随序列推进变化，并附帧示例。长期保留的点还应通过几何检查，存活比例不是单独的正确率。 |
| 7 | 6 | 5.2 光照变化、运动模糊与系统收益 | 在 VINS-Mono 中更换前端后的 HDR 轨迹。系统结果同时受跟踪、外点和后端影响，不等于单个损失的因果消融。 |

## 自制图与计算假设

程序精确生成 SVG；没有使用生成式位图，没有虚构模型输出。所有曲线、点阵和轨迹是教学输入或正文公式的计算，不能当论文性能复现。公式统一通过共享 MathJax/STIX2 渲染。

| 正文顺序 | 文件 | 说明 |
| --- | --- | --- |
| 1 | [let-illumination.svg](../public/media/letnet/let-illumination.svg) | 同一条边在增益和偏置变化后的强度曲线，说明光度误差并不只由运动造成。 |
| 2 | [let-landscape.svg](../public/media/letnet/let-landscape.svg) | 二次代价与常量特征的教学对比：让所有对应相似并不足够，还要防止失去定位梯度。 |
| 3 | [let-unroll.svg](../public/media/letnet/let-unroll.svg) | 有限步优化的教学展开：红点逐步接近局部极小值，外层监督最终坐标；图不声称每次真实 LM 都采用该步长。 |
| 4 | [let-basin.svg](../public/media/letnet/let-basin.svg) | 示意多极小值目标与局部初始化范围。LET-NET2 固定训练代码使用真值加标准差 2 像素的噪声，不能据此证明任意大运动可收敛。 |

## 作者代码核查

只做源码阅读；未宣称重跑训练或论文基准。以下提交固定本文所讨论的实现。

- [linyicheng1/LET-NET @ 64dfae986d45](https://github.com/linyicheng1/LET-NET/tree/64dfae986d45a59e63ec58a83e96f7c79dbbeb41)：`README.md`, `tracking.cpp`。
- [linyicheng1/LET-NET-Train @ 72fd0106c909](https://github.com/linyicheng1/LET-NET-Train/tree/72fd0106c909b1ff042b1a84ea75baadd8689be8)：`README.md`, `main.py`。
- [linyicheng1/LET-NET2 @ 4713802d256e](https://github.com/linyicheng1/LET-NET2/tree/4713802d256ecf3bb463837e80b9d3d0ccba5a1a)：`README.md`, `lk.py`, `model.py`, `tartanair.py`, `train.py`。

## 复现与验证

依赖 Python 3、NumPy、Pillow、PyMuPDF，及仓库 Node 依赖。PDF 放在仓库外；已发布图不需要原 PDF 即可浏览。

```bash
python3 scripts/vision-series/extract.py /absolute/path/to/papers letnet
python3 scripts/vision-series/figures.py
node scripts/vision-series/typeset.mjs
python3 scripts/vision-series/assemble.py
npm run build
```

全系列检查结果见 [制作记录](vision-series-production.md)。重新裁图后应重新运行 assemble，同步真实宽高；重新画图后应先运行 typeset，再检查实际栅格渲染和页面。
