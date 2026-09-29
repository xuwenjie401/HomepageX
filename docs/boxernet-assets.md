# boxernet 素材与复现记录

正文：[文章源文件](../src/content/blog/3d-perception-and-project-aria/boxernet.md)。核查日期：2026-09-29。

共 14 图：论文原图 10，自制图 4。按正文顺序编号自制图，原图保留作者图号。

## 固定论文与原图清单

以下页码按 PDF 文件从 1 开始；裁切框在 `sources.json`，为页宽/页高归一化坐标。提图前先核对 SHA-256；不以网页后续更新的同名文件静默替换。

### Boxer: Robust Lifting of Open-World 2D Bounding Boxes to 3D

- 来源：[固定论文](https://arxiv.org/pdf/2604.05212v1)
- 本地复现文件名：`boxer.pdf`
- SHA-256：`59b3469283815e2acad644241bb61e4e49638d88679c1eef0f78805554c91168`

| 图号 | PDF 页 | 放置章节／省略理由 | 内容 |
| --- | --- | --- | --- |
| 1 | 1 | 开篇 | 静态场景中小物体与长尾类别的三维框。看不同视角是否落在同一个实体上。 |
| 2 | 5 | 2. 先分清 Boxer 与 BoxerNet 的输入输出 | Boxer 完整系统：二维检测、单帧提升、跨视角融合分别承担不同职责。 |
| 3 | 7 | 二维框是 query，整幅图像是上下文 | BoxerNet：图像、射线与可选深度按 patch 编码，二维框作为独立查询。 |
| 4 | 12 | mAP 在这里不考类别名是否正确 | 逐帧三维 IoU 的定性比较；黄色表示与真值重叠更好，须同时区分二维框来源。 |
| 5 | 13 | 朝向不能直接做普通平均 | 把逐帧框叠到统一世界坐标中；更集中的伪热图表示跨帧估计更一致。 |
| 6 | 17 | 不确定性调节的是这一个样本的几何误差 | CA-1M、IoU 0.25 下的 PR 曲线：二维与三维置信度平均改善排序。 |
| 7 | 18 | 检测框很紧，投影框很松，训练会错位 | 四类增强：光度、相机、深度点与二维框；最后一行比较投影框和 SAM 收紧框。 |
| 8 | 21 | 8. 补充实验：伪标注的价值与比较的边界 | ScanNet 的既有闭集标注与 Boxer 开放集伪标注；覆盖变多不等于新增人工真值。 |
| 9 | 22 | 8. 补充实验：伪标注的价值与比较的边界 | SAM3 与 SAM3D 的 ADT 样例；同时观察二维投影与三维、俯视视角。 |
| 10 | 23 | 哪个改动最重要？消融要保留原表基线 | 按物体体积分桶的 PR 曲线；小物体解释了较大部分性能差距。 |

## 自制图与计算假设

程序精确生成 SVG；没有使用生成式位图，没有虚构模型输出。所有曲线、点阵和轨迹是教学输入或正文公式的计算，不能当论文性能复现。公式统一通过共享 MathJax/STIX2 渲染。

| 正文顺序 | 文件 | 说明 |
| --- | --- | --- |
| 1 | [boxer-depth.svg](../public/media/boxernet/boxer-depth.svg) | 按相似三角形绘制的尺度歧义。物体尺寸与深度同时加倍，图像高度不变；这是教学几何，不是检测输出。 |
| 2 | [boxer-patches.svg](../public/media/boxernet/boxer-patches.svg) | 四个有效像素深度的普通中位数为 2.05 m，均值为 3.50 m。论文描述中位数，所核查公开代码的稀疏点分支实际取均值；此图比较两种聚合的行为。 |
| 3 | [boxer-loss.svg](../public/media/boxernet/boxer-loss.svg) | 直接计算 D=4 时的损失曲线。最优 log-variance 为 log 4≈1.386；蓝线为加权几何误差，灰线为不确定性惩罚，红线为总和。 |
| 4 | [boxer-fusion.svg](../public/media/boxernet/boxer-fusion.svg) | 俯视教学示意。左侧同一静态物体可融合，右侧红框是不同时间观测的置信加权结果，不对应这三个观测时刻中的任何一个；采样位置和权重保存在脚本中。 |

## 作者代码核查

只做源码阅读；未宣称重跑训练或论文基准。以下提交固定本文所讨论的实现。

- [facebookresearch/boxer @ 1f86542dc342](https://github.com/facebookresearch/boxer/tree/1f86542dc342a4b1d474c87c97c5d1d6566d9148)：`boxernet/boxernet.py`, `utils/fuse_3d_boxes.py`。

论文描述 patch 中位深度，所核查稀疏点路径实际计算有效像素均值；源码中存在未被该路径调用的 masked_median。倍角 yaw 平均与宽深交换按执行代码核对。主文与附录的参数量出现 25M 与 71M 两种表述，正文未选取其中一个作为确定值。


## 复现与验证

依赖 Python 3、NumPy、Pillow、PyMuPDF，及仓库 Node 依赖。PDF 放在仓库外；已发布图不需要原 PDF 即可浏览。

```bash
python3 scripts/aria-series/extract.py /absolute/path/to/papers boxer
python3 scripts/aria-series/figures.py
node scripts/aria-series/typeset.mjs
python3 scripts/aria-series/assemble.py
npm run build
```

全系列检查结果见 [制作记录](aria-series-production.md)。重新裁图后应重新运行 assemble，同步真实宽高；重新画图后应先运行 typeset，再检查实际栅格渲染和页面。
