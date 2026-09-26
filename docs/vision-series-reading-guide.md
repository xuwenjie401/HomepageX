# 从局部特征到视觉回环：十篇阅读导航

网页入口：[Sparse Feature and Visual Recognition](https://xuwenjie401.github.io/HomepageX/blog/sparse-feature-and-visual-recognition/)。博客首页通过同名专题进入，各篇使用该目录下的独立地址。

这组文章延续 [SuperPoint 详解](../src/content/blog/sparse-feature-and-visual-recognition/superpoint.md) 的写法：从问题出发，用可计算的例子解释机制，再读论文实验与失败情况。每篇均有分级目录、可放大的原图和自制图，以及紧邻公式的符号解释。

| 篇目 | 从哪个问题读起 | 重点 |
| --- | --- | --- |
| 1. [GFTT + KLT + SIFT](../src/content/blog/sparse-feature-and-visual-recognition/gftt-klt-sift.md) | 什么点值得跟踪？为什么有些方向根本估不准？ | 结构张量、孔径问题、LK 更新、金字塔、尺度空间、方向直方图、匹配筛选 |
| 2. [SuperPoint](../src/content/blog/sparse-feature-and-visual-recognition/superpoint.md) | 真实图像没有角点标签，检测与描述怎样联合学习？ | MagicPoint、Homographic Adaptation、检测头、描述监督、训练与推理 |
| 3. [SuperGlue + LightGlue](../src/content/blog/sparse-feature-and-visual-recognition/superglue-lightglue.md) | 描述子很像，为什么还会匹配错？ | 集合上下文、注意力、dustbin 与部分分配、几何监督、自适应深度与点剪枝 |
| 4. [NetVLAD + HF-Net](../src/content/blog/sparse-feature-and-visual-recognition/netvlad-hfnet.md) | 如何先找到地方，再求出精确相机位姿？ | 残差聚合、弱监督、教师蒸馏、共视聚类、2D–3D 对应与 PnP |
| 5. [DINOv2 / DINOv3 的训练](../src/content/blog/sparse-feature-and-visual-recognition/dinov2-dinov3.md) | 没有人工类别标签，局部结构如何学出来？ | 自蒸馏、iBOT、抗坍塌、数据策划、长训练的局部退化、Gram anchoring |
| 6. [基础模型怎样改变 VPR 与局部对应](../src/content/blog/sparse-feature-and-visual-recognition/foundation-model-vpr-features.md) | 有了通用特征，下游还需要学什么？ | AnyLoc、SALAD、SelaVPR、DeDoDe、RoMa 的关键想法、适用条件与取舍 |
| 7. [TartanAir](../src/content/blog/sparse-feature-and-visual-recognition/tartanair.md) | 怎样有控制地生成困难运动和精确监督？ | 仿真采集、相机与深度约定、遮挡、轨迹设计、TartanVO、合成 IMU、域差异 |
| 8. [LET-NET && LET-NET2](../src/content/blog/sparse-feature-and-visual-recognition/letnet.md) | 亮度一致性失效以后，能否学出适合 LK 的表示？ | 三通道特征、角点与可靠性监督、可微求解器、初始化吸引域、作者训练代码 |
| 9. [ALIKED](../src/content/blog/sparse-feature-and-visual-recognition/aliked.md) | 如何把亚像素位置与描述子支持区域一起学好？ | DKD、稀疏可变形采样、SDDH、训练损失、旋转尺度与成本边界 |
| 10. [检测到回环以后](../src/content/blog/sparse-feature-and-visual-recognition/loop-closure.md) | 一次地点重访究竟如何改动历史轨迹和地图？ | 图维护、视觉惯性因子、Schur 与边缘化、Sim(3)/4DoF、ORB-SLAM2/3、VINS-Fusion、OKVIS 系列 |

如果主要关心定位系统，可按 **1 → 2 → 3 → 4 → 10** 阅读。关心基础模型与学习型特征，可按 **5 → 6 → 9 → 3** 阅读。关心学习型里程计和跟踪，可按 **1 → 7 → 8 → 10** 阅读。

第 10 篇篇幅最长。第一次读建议先过第 1–6 节，统一图结构、坐标、优化和几何约束，再分别进入 ORB-SLAM、VINS 或 OKVIS。第 12 节提供系统对照，第 14 节把一次闭环按状态变量走完整，适合回顾。

全专题共 328 幅图（含 SuperPoint 的 30 幅）。原图沿用论文 Figure 编号，自制图按每篇正文顺序编号；教学例子与论文实测分开说明。固定论文版本、作者代码提交、素材再生成方法和实际检查结果见 [制作记录](vision-series-production.md)。
