# hmd2 素材与复现记录

正文：[文章源文件](../src/content/blog/3d-perception-and-project-aria/hmd2.md)。核查日期：2026-09-29。

共 13 图：论文原图 9，自制图 4。按正文顺序编号自制图，原图保留作者图号。

## 固定论文与原图清单

以下页码按 PDF 文件从 1 开始；裁切框在 `sources.json`，为页宽/页高归一化坐标。提图前先核对 SHA-256；不以网页后续更新的同名文件静默替换。

### HMD²: Environment-aware Motion Generation from Single Egocentric Head-Mounted Device

- 来源：[固定论文](https://arxiv.org/pdf/2409.13426v2)
- 本地复现文件名：`hmd2.pdf`
- SHA-256：`51ba153f4c6f5c1eb733c5fd86cbc94595015940b4aa391bda6434120902a9f5`

| 图号 | PDF 页 | 放置章节／省略理由 | 内容 |
| --- | --- | --- | --- |
| 1 | 1 | 开篇 | 外向相机只看到环境和少量身体，系统生成与头部及场景相容的全身动作。 |
| 2 | 4 | 2. 三种条件，分别补上哪一块信息？ | 头部运动、CLIP 图像特征和局部点云特征共同条件化动作扩散。 |
| 3 | 4 | 一个设备不等于一颗 RGB 传感器 | 连续第一人称图像中，手臂只间歇出现，完整身体并不可见。 |
| 4 | 5 | 独立生成窗口，会在拼接处换一套身体 | 每次反向扩散都用上一窗口覆盖重叠区，保持长序列衔接。 |
| 5 | 6 | 主结果使用完整长序列，单位是厘米 | 跪坐转换和抬手动作的定性比较；观察回归均值、条件缺失与低延迟的影响。 |
| 6 | 7 | 7. 多次生成究竟该在哪些地方不同？ | 相同头部条件下手臂和腿的多种合理解。 |
| 7 | 8 | 6. 点云和 CLIP 并不是两个可随意替换的条件 | 去掉点云或图像条件后，坐姿与手部运动出现不同错误。 |
| 8 | 13 | 7. 多次生成究竟该在哪些地方不同？ | 相同输入的四次采样：可见部分应服从观测，不可见部分保留变化。 |
| 9 | 14 | 8. 平均误差之外：困难动作在哪里？ | 按动作场景排序的关节误差，展示平均值掩盖的困难尾部。 |

## 自制图与计算假设

程序精确生成 SVG；没有使用生成式位图，没有虚构模型输出。所有曲线、点阵和轨迹是教学输入或正文公式的计算，不能当论文性能复现。公式统一通过共享 MathJax/STIX2 渲染。

| 正文顺序 | 文件 | 说明 |
| --- | --- | --- |
| 1 | [hmd2-ambiguity.svg](../public/media/hmd2/hmd2-ambiguity.svg) | 两个人工骨架共享头部位置，分别呈坐姿与蹲姿。环境和语义可减少歧义，但无法证明不可见肢体只有一个真实解。 |
| 2 | [hmd2-voxel.svg](../public/media/hmd2/hmd2-voxel.svg) | 按人工稀疏点计算最近距离并在 0.1 m 截断，颜色只用于展示该数值。左侧为 2 m 立方体的示意投影，右侧为其中一个教学切片。 |
| 3 | [hmd2-diffusion.svg](../public/media/hmd2/hmd2-diffusion.svg) | 使用固定随机种子绘制概念曲线；标量例按正文的前向加噪公式计算。真实模型对整段关节旋转序列生成，训练预测干净动作。 |
| 4 | [hmd2-window.svg](../public/media/hmd2/hmd2-window.svg) | 按真实帧数比例绘制 240 帧窗口。蓝色是重叠历史，金色是新增块；右侧数字是新增块时长，首帧最大前视间隔为 (h−1)/60。 |

HMD² 的核查依据为固定论文主文、附录与项目页；核查时项目页未提供代码入口，未宣称验证其训练实现。


## 复现与验证

依赖 Python 3、NumPy、Pillow、PyMuPDF，及仓库 Node 依赖。PDF 放在仓库外；已发布图不需要原 PDF 即可浏览。

```bash
python3 scripts/aria-series/extract.py /absolute/path/to/papers hmd2
python3 scripts/aria-series/figures.py
node scripts/aria-series/typeset.mjs
python3 scripts/aria-series/assemble.py
npm run build
```

全系列检查结果见 [制作记录](aria-series-production.md)。重新裁图后应重新运行 assemble，同步真实宽高；重新画图后应先运行 typeset，再检查实际栅格渲染和页面。
