# egoforce 素材与复现记录

正文：[文章源文件](../src/content/blog/3d-perception-and-project-aria/egoforce.md)。核查日期：2026-09-29。

共 23 图：论文原图 19，自制图 4。按正文顺序编号自制图，原图保留作者图号。

## 固定论文与原图清单

以下页码按 PDF 文件从 1 开始；裁切框在 `sources.json`，为页宽/页高归一化坐标。提图前先核对 SHA-256；不以网页后续更新的同名文件静默替换。

### EgoForce: Forearm-Guided Camera-Space 3D Hand Pose from a Monocular Egocentric Camera

- 来源：[固定论文](https://arxiv.org/pdf/2605.12498v1)
- 本地复现文件名：`egoforce.pdf`
- SHA-256：`ac4929bb472a28be0ce4d444f9028a1d6e65f89918961b064668878eac759360`

| 图号 | PDF 页 | 放置章节／省略理由 | 内容 |
| --- | --- | --- | --- |
| 1 | 1 | 开篇 | 单目输入恢复相机坐标中的手和前臂，同时适配多种镜头。 |
| 2 | 3 | 手和前臂需要不同空间分辨率 | HALO 分别编码手和前臂，结合 CIT，再由射线求解器恢复整体平移。 |
| 3 | 5 | 多个不同方向，共同确定一个平移 | 射线求解器把二维关节、置信权重与根相对三维结构组合为相机空间位置。 |
| 4 | 6 | 前臂不在画面里时，不能把空白当真实观测 | 按可见手关节比例分组的前臂收益；位置与加速度误差改善并不相同。 |
| 5 | 7 | 相机位置误差与对齐后手形误差不要混淆 | 二维看起来对齐仍可能存在深度误差，侧视图能揭示这种歧义。 |
| 6 | 8 | 前臂不在画面里时，不能把空白当真实观测 | 物体遮挡手时，前臂输入改善手腕朝向和三维手姿。 |
| 7 | 8 | 前臂不在画面里时，不能把空白当真实观测 | 前臂不可见时的条件先验；补全的是合理姿态。 |
| 8 | 9 | 相机位置误差与对齐后手形误差不要混淆 | ARCTIC、H2O、HOT3D 多视角定性对照，灰色为真值。 |
| 9 | 10 | 8. 原图中的跨设备结果，还能说明什么？ | 多个数据集的手网格重投影；投影质量需结合三维指标判断。 |
| 10 | 13 | 8. 原图中的跨设备结果，还能说明什么？ | 不同光学模型下的手和前臂联合重投影。 |
| 11 | 14 | 局部去畸变和最终原生射线要配套 | 原始鱼眼裁块、透视校正与局部去畸变的比较。 |
| 12 | 14 | 局部去畸变和最终原生射线要配套 | 加入裁块内参条件后，空间位置与朝向更符合观测。 |
| 13 | 14 | 远处小手为什么仍可能抖？ | 深度提升、DGP 与 RSS 的比较；重点看侧面深度错位。 |
| 14 | 16 | MANO 管手，FARM 管前臂 | FARM 接到 MANO 腕部的前后对照，并沿肘方向施加小偏移。 |
| 15 | 17 | 裁成一样大，恰好丢掉了重要的相机信息 | CIT 广播到 patch token，通过拼接、MLP 和残差进行融合。 |
| 16 | 20 | 手部稳定性与前臂稳定性并非同时单调改善 | HOT3D 相机坐标轨迹；尤其比较深度轴和起止点。 |
| 17 | 20 | 8. 原图中的跨设备结果，还能说明什么？ | HO3D 与无标定野外视频的定性结果，后者使用估计的内参。 |
| 18 | 21 | 9. 边界：改善尺度歧义，不代表彻底解除歧义 | 标定扰动实验；中等误差下的改善不构成部署时选择内参的依据。 |
| 19 | 22 | 8. 原图中的跨设备结果，还能说明什么？ | 与 UmeTrack 的单视图比较；裁块生成协议必须与指标一起阅读。 |

## 自制图与计算假设

程序精确生成 SVG；没有使用生成式位图，没有虚构模型输出。所有曲线、点阵和轨迹是教学输入或正文公式的计算，不能当论文性能复现。公式统一通过共享 MathJax/STIX2 渲染。

| 正文顺序 | 文件 | 说明 |
| --- | --- | --- |
| 1 | [egoforce-scale.svg](../public/media/egoforce/egoforce-scale.svg) | 人工手骨架的三维截面作精确二倍相似变换：尺寸与深度同时加倍，投影射线保持一致。并非模型预测或真实用户手型。 |
| 2 | [egoforce-crop.svg](../public/media/egoforce/egoforce-crop.svg) | 针孔数值例：原焦距 800、主点 320，裁块起点 100、宽度 400，缩至 224 后焦距为 448、主点为 123.2。图中骨架只是几何示意。 |
| 3 | [egoforce-rays.svg](../public/media/egoforce/egoforce-rays.svg) | 用向量投影精确画出点到无限直线的垂直残差。RSS 同时求解所有关节共享的平移；正向深度不是这个无约束闭式解自动施加的条件。 |
| 4 | [egoforce-conditioning.svg](../public/media/egoforce/egoforce-conditioning.svg) | 二维对称射线的法矩阵，半夹角 30 度时深度特征值为 0.5，5 度时约 0.015。红色等高线按同一误差阈值计算，展示小夹角病态。 |

## 作者代码核查

只做源码阅读；未宣称重跑训练或论文基准。以下提交固定本文所讨论的实现。

- [dfki-av/EgoForce @ 480ffb358516](https://github.com/dfki-av/EgoForce/tree/480ffb358516d0d7f971ec9da99b7bb07635731e)：`core/rss.py`, `models/halo.py`。

核查像素到原生相机射线的转换、投影矩阵与加阻尼线性求解。代码还包含 robust 求解选项，正文闭式推导对应基本加权最小二乘，不宣称复现所有可选配置。


## 复现与验证

依赖 Python 3、NumPy、Pillow、PyMuPDF，及仓库 Node 依赖。PDF 放在仓库外；已发布图不需要原 PDF 即可浏览。

```bash
python3 scripts/aria-series/extract.py /absolute/path/to/papers egoforce
python3 scripts/aria-series/figures.py
node scripts/aria-series/typeset.mjs
python3 scripts/aria-series/assemble.py
npm run build
```

全系列检查结果见 [制作记录](aria-series-production.md)。重新裁图后应重新运行 assemble，同步真实宽高；重新画图后应先运行 typeset，再检查实际栅格渲染和页面。
