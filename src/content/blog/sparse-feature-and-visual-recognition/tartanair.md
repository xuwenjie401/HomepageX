---
title: "读懂 TartanAir：怎样造一个能教会视觉里程计、又能暴露 SLAM 弱点的世界"
description: "从 Unreal/AirSim 场景、轨迹采样和数据验证，推导深度到光流、特征监督和 IMU 信号，再看 TartanVO 的跨相机泛化与仿真边界。"
date: 2026-09-26
tags: [论文精读, 仿真, 数据集, 视觉里程计]
---

机器人能在熟悉道路上跑通，不代表它能在急转弯、昏暗房间、树叶晃动和突然曝光变化时稳定定位。真实采集最困难的往往恰好是这些情况：容易撞、难重复、标注不准，还很难同时取得逐像素深度、光流和精确相机位姿。

TartanAir 的关键价值，是把“从哪里取得训练信号”变成可控的工程系统。严格地说，**TartanAir 是仿真生成的数据集及配套采集、处理工具体系；底层渲染与传感器接口依托 Unreal Engine 和 AirSim**。它不是一个只负责把机器人动力学向前积分的单一模拟器。

> 主线采用 [TartanAir，IROS 2020，arXiv:2003.14338v2](https://arxiv.org/abs/2003.14338v2)；应用例子采用 [TartanVO，arXiv:2011.00359v1](https://arxiv.org/abs/2011.00359v1)。V2 的新增传感器和格式按 [官方文档](https://tartanair.org/)说明，与 2020 年论文的 V1 区分。

## 1. 先决定需要什么困难，再设计世界

### 1.1 视觉多样性之外，还需要运动多样性

一辆车多数时候向前，转动主要是 yaw。网络可能不必充分理解几何，只要记住“地面通常以这种速度流过”就能得到较低训练误差。换成手持相机横移、无人机滚转或倒退，捷径就失效。

V1 论文设置 30 个环境、1037 条长序列和超过 100 万帧，包含结构化城市、室内及自然环境。这里的规模属于该论文版本，不能与 V2 的环境数、相机数相加后当成同一个数据集统计。

<!-- vision-figure: tartanair-1 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanair-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanair-1.webp" width="1697" height="1779" alt="TartanAir 原论文 Figure 1：多环境、季节、材质和照明示例。环境多样性与轨迹运动多样性是两个独立设计维度。" loading="lazy" /></a>
  <figcaption>TartanAir 原论文 Figure 1 · 多环境、季节、材质和照明示例。环境多样性与轨迹运动多样性是两个独立设计维度。 <a href="https://arxiv.org/pdf/2003.14338v2#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: tartanair-3 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanair-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanair-3.webp" width="842" height="782" alt="TartanAir 原论文 Figure 3：KITTI 与 TartanAir 的平移、旋转分布。运动方向过于单一时，网络可能依靠数据偏置而非通用几何。" loading="lazy" /></a>
  <figcaption>TartanAir 原论文 Figure 3 · KITTI 与 TartanAir 的平移、旋转分布。运动方向过于单一时，网络可能依靠数据偏置而非通用几何。 <a href="https://arxiv.org/pdf/2003.14338v2#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 3 把相邻帧平移和旋转投到主方向上。作者用奇异值 $t_1\ge t_2\ge t_3$、$r_1\ge r_2\ge r_3$ 定义运动多样性指标：

$$
\sigma_{motion}=\frac12\left(\frac{\sqrt{t_2t_3}}{t_1}+\frac{\sqrt{r_2r_3}}{r_1}\right).
$$

单一主轴支配时较小，三轴接近时趋近 1；零运动时需单独处理分母。这是方向覆盖的统计，不是“物理真实性”分数，也不能判断加速度是否符合某种车辆或人体动力学。

### 1.2 困难要可以分解和重复

<!-- vision-figure: tartanair-4 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanair-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanair-4.webp" width="437" height="663" alt="TartanAir 原论文 Figure 4：低照明、弱纹理、动态物体与恶劣天气等困难场景。它们应成为测试条件，而非仅作为渲染展示。" loading="lazy" /></a>
  <figcaption>TartanAir 原论文 Figure 4 · 低照明、弱纹理、动态物体与恶劣天气等困难场景。它们应成为测试条件，而非仅作为渲染展示。 <a href="https://arxiv.org/pdf/2003.14338v2#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

动态光照、雨雾、曝光、反射和运动物体对应不同失效源。若一次同时改变全部因素，即使误差变大也很难解释原因。仿真的优势是能够固定轨迹和几何，仅改变某个因素，以检查前端特征、跟踪还是后端假设先失效。

但“可以控制”不等于原数据已经穷尽了所有独立消融。实验设计仍需明确所用场景、轨迹、渲染设置和随机种子。

## 2. 大规模采集不靠人手开相机游览

### 2.1 先建自由空间，再采样路径

<!-- vision-figure: tartanair-5 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanair-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanair-5.webp" width="1742" height="315" alt="TartanAir 原论文 Figure 5：环境探索、路径采样、数据采集与验证的生成流程。可重复控制条件让失败原因更容易被隔离。" loading="lazy" /></a>
  <figcaption>TartanAir 原论文 Figure 5 · 环境探索、路径采样、数据采集与验证的生成流程。可重复控制条件让失败原因更容易被隔离。 <a href="https://arxiv.org/pdf/2003.14338v2#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: tartan-paths -->
<figure>
  <a href="/HomepageX/media/tartanair/tartan-paths.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartan-paths.svg" width="1100" height="470" alt="自制图 1：二维教学地图展示路径与朝向是两类设计变量；避障路径本身不保证真实机器人能够满足动力学约束。" loading="lazy" /></a>
  <figcaption>自制图 1 · 二维教学地图展示路径与朝向是两类设计变量；避障路径本身不保证真实机器人能够满足动力学约束。</figcaption>
</figure>
<!-- /vision-figure -->

原管线先用深度和已知位姿建立占据栅格，通过 frontier 探索逐渐覆盖场景，再用 RRT* 在自由空间中规划无碰撞路径。随机采样节点及连接形成轨迹图，从中取路径并用样条平滑，最后随机化沿轨迹的增量位移与观察角度。

这里有两个不同层次：路径控制相机去哪些位置，朝向采样控制相机看到什么。只随机位置而总朝前看，仍然保留强视角偏好；只随机朝向却反复站在原地，又缺少平移视差。

论文采集的是按位置序列驱动虚拟相机获得的数据。路径平滑有助于连续性，但不能直接推断它满足任意真实飞行器的推力、角速度和加速度限制。做 learning-based IO/VIO 时，这个差别尤其重要。

### 2.2 原始通道与派生标签分开保存

<!-- vision-figure: tartanair-2 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanair-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanair-2.webp" width="841" height="883" alt="TartanAir 原论文 Figure 2：RGB、深度、分割、光流及其他标注来自同一仿真状态。多模态监督的价值在于几何与时间对应一致。" loading="lazy" /></a>
  <figcaption>TartanAir 原论文 Figure 2 · RGB、深度、分割、光流及其他标注来自同一仿真状态。多模态监督的价值在于几何与时间对应一致。 <a href="https://arxiv.org/pdf/2003.14338v2#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

渲染器和接口提供 RGB、深度、分割、相机位姿。基于这些几何量，再生成光流、视差、点云等。派生标签不是独立测量，它们共享源数据；如果某个坐标变换写反，会让多个标签一起错。

可复查的样本至少应关联：图像 ID、内参、坐标系定义、位姿、时间或采样顺序、深度约定、有效掩码。只保存一张漂亮的流颜色图，既不能训练，也不能验证对应是否准确。

## 3. 从深度和位姿推导光流：标签为什么能准确

### 3.1 必须先说明“深度”是哪种距离

采用针孔相机和相机坐标 $Z$ 深度 $z$，像素齐次坐标 $\widetilde{\mathbf u}=(u,v,1)^\top$ 对应

$$
\mathbf X_A=z_A(\mathbf u)K_A^{-1}\widetilde{\mathbf u}.
$$

如果文件保存的是到光心的射线距离 $r$，则应改成

$$
\mathbf X_A=r_A(\mathbf u)\frac{K_A^{-1}\widetilde{\mathbf u}}{\|K_A^{-1}\widetilde{\mathbf u}\|}.
$$

离主点越远，两种定义差异越大。因此下面的推导使用 $Z$ 深度假设，具体解码与 ray/planar 转换应服从所用 TartanAir 版本和相机模型，不能看见一个名为 depth 的数组就直接套公式。

### 3.2 一个三维点从 A 走到 B

令 $T_{WA},T_{WB}$ 把相机坐标变到世界系，则

$$
T_{BA}=T_{WB}^{-1}T_{WA},\quad
\mathbf X_B=R_{BA}\mathbf X_A+\mathbf t_{BA},\quad
\mathbf u'_B=\pi(K_B\mathbf X_B),\quad
\mathbf f_{A\to B}(\mathbf u)=\mathbf u'_B-\mathbf u.
$$

这里流向是 A 像素到 B 像素，生成 B 图时做的逆向采样又是另一件事。坐标符号混淆会导致看似平滑却反向的光流。

<!-- vision-figure: tartan-reprojection -->
<figure>
  <a href="/HomepageX/media/tartanair/tartan-reprojection.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartan-reprojection.svg" width="1100" height="470" alt="自制图 2：教学几何示意：相机 A 的像素沿射线恢复三维点，通过相对位姿投到 B；真实代码必须统一坐标和深度定义。" loading="lazy" /></a>
  <figcaption>自制图 2 · 教学几何示意：相机 A 的像素沿射线恢复三维点，通过相对位姿投到 B；真实代码必须统一坐标和深度定义。</figcaption>
</figure>
<!-- /vision-figure -->

数值例子：焦距 $f=320$ 像素，点位于相机前方 4 米，相机向右平移 0.1 米且不旋转，点在新相机系的横坐标减少 0.1 米，因此像素向左移动 $320\times0.1/4=8$ 像素。2 米处点移动 16 像素，8 米处点移动 4 像素。不同深度产生不同流，这正是单张全局单应不能模拟一般三维平移的原因。

<!-- vision-figure: tartanair-6 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanair-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanair-6.webp" width="841" height="200" alt="TartanAir 原论文 Figure 6：由深度和位姿产生的光流示例。有效光流需排除视野外和不可见区域，动态物体还需要其自身运动信息。" loading="lazy" /></a>
  <figcaption>TartanAir 原论文 Figure 6 · 由深度和位姿产生的光流示例。有效光流需排除视野外和不可见区域，动态物体还需要其自身运动信息。 <a href="https://arxiv.org/pdf/2003.14338v2#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

### 3.3 有投影，不代表在第二帧可见

若 $Z_B\le0$，点在相机后方；若投影越界，它离开视野；若预测深度大于目标图该像素处的可见表面深度，它可能被遮挡。对可见性可作近似检查：

$$
M(\mathbf u)=\mathbf1[Z_B>0]\mathbf1[\mathbf u'_B\in\Omega_B]
\mathbf1[|z_B(\mathbf u'_B)-Z_B|<\tau_z].
$$

实际阈值应考虑距离、插值和边缘。遮挡边界上把前景、背景深度双线性混合，会产生不存在的中间表面，不能当成精确几何真值。

<!-- vision-figure: tartanair-7 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanair-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanair-7.webp" width="842" height="237" alt="TartanAir 原论文 Figure 7：遮挡在光流真值中对应无效区域。它与几何投影超出图像边界是不同原因。" loading="lazy" /></a>
  <figcaption>TartanAir 原论文 Figure 7 · 遮挡在光流真值中对应无效区域。它与几何投影超出图像边界是不同原因。 <a href="https://arxiv.org/pdf/2003.14338v2#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: tartan-occlusion -->
<figure>
  <a href="/HomepageX/media/tartanair/tartan-occlusion.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartan-occlusion.svg" width="1100" height="470" alt="自制图 3：第二帧的射线上先遇到遮挡物；用深度一致性检查可见性，不能只检查投影是否越界。" loading="lazy" /></a>
  <figcaption>自制图 3 · 第二帧的射线上先遇到遮挡物；用深度一致性检查可见性，不能只检查投影是否越界。</figcaption>
</figure>
<!-- /vision-figure -->

原论文光流推导明确针对静态场景。移动汽车除了相机运动，还有物体自身的变换；只使用相机位姿和一张深度不能恢复它的真实光流。数据包含动态物体，不意味着相机运动生成的全部流标签在动态区域同样有效。

### 3.4 视差与模拟 LiDAR 也来自同一份几何

校正后的平行双目满足 $d=f_xb/Z$，其中 $b$ 为米制基线、$d$ 为像素视差。以 $f_x=320,b=0.25,Z=4$ 得到 20 像素。不同内参、未校正双目不能直接套这个一维关系。

<!-- vision-figure: tartanair-8 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanair-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanair-8.webp" width="842" height="247" alt="TartanAir 原论文 Figure 8：相同视差在同时屏蔽遮挡与视野外、仅屏蔽视野外、不屏蔽时的差别。颜色解释和无效区域必须一起保留。" loading="lazy" /></a>
  <figcaption>TartanAir 原论文 Figure 8 · 相同视差在同时屏蔽遮挡与视野外、仅屏蔽视野外、不屏蔽时的差别。颜色解释和无效区域必须一起保留。 <a href="https://arxiv.org/pdf/2003.14338v2#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: tartanair-9 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanair-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanair-9.webp" width="842" height="258" alt="TartanAir 原论文 Figure 9：模拟 LiDAR 的示例，原文将其作为额外模态。不同传感器采样规律不能仅靠重命名深度图代替。" loading="lazy" /></a>
  <figcaption>TartanAir 原论文 Figure 9 · 模拟 LiDAR 的示例，原文将其作为额外模态。不同传感器采样规律不能仅靠重命名深度图代替。 <a href="https://arxiv.org/pdf/2003.14338v2#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

模拟 LiDAR 可以沿扫描方向从深度中采样。视觉渲染深度与碰撞模型射线有不同细节，叶片等对象可能只有可见网格而没有完整碰撞体。无论采用哪种方案，理想同步点云都还缺少真实扫描中的运动畸变、反射强度、漏测和多径等因素。

## 4. 数据验证：为什么真值也需要检查

可用已知流把两帧的可见区域对齐，再检查图像和深度是否一致；也可检查连续位姿、深度分布和异常帧。光度验证不能盲目要求全部像素相同，因为渲染曝光、阴影或动态物体本来就会改变颜色。

对于自己的训练管线，最有效的最小验证是：取十个实际三维点，手算投影；画 A→B 与 B→A；叠加 mask；查看深度边缘、图像四角和极端旋转。点云看起来像房间，并不能排除坐标轴符号或四元数顺序错误。

## 5. 有了这些标签，哪些学习任务真正受益

### 5.1 稀疏特征：用几何判断重复性和正确对应

把 A 的检测点投到 B，检查 B 是否在容差内也检测到点，就能监督重复性；用可见性筛选，再以正负对应训练描述子。这里不需要人工给“兴趣点”命名，但仍需要选择哪些点值得学，以及如何处理未检测到的可见位置。

### 5.2 光流：直接监督输出位移，也可监督优化后的结果

常见 endpoint error 为

$$
\mathcal L_{flow}=\frac1{\sum_iM_i}\sum_iM_i\|\widehat{\mathbf f}_i-\mathbf f_i^*\|_2.
$$

对于 LET-NET2，位移不是由 CNN 一次直接回归，而是从学习特征上运行可微 LK 得到。几何真值惩罚最终跟踪误差，梯度再传回特征。这使模型能学习“什么表示便于优化器跟对”。[下一篇 LET-NET / LET-NET2](/HomepageX/blog/sparse-feature-and-visual-recognition/letnet/)将细拆这条梯度路径。

### 5.3 VO：监督位姿不能绕过单目尺度问题

相邻帧姿态可直接作为训练目标，但纯单目几何只恢复平移方向与相对尺度。网络在固定相机高度的驾驶数据中预测米制平移，有可能依赖场景尺寸先验；换相机和场景后这个先验就变了。

## 6. TartanVO：仿真规模如何变成跨相机泛化

### 6.1 显式提供内参，不让网络猜镜头

<!-- vision-figure: tartanvo-1 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanvo-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanvo-1.webp" width="1340" height="307" alt="TartanVO 原论文 Figure 1：匹配网络、位姿网络和相机内参输入的分工。运动估计需要知道同样像素位移对应何种射线变化。" loading="lazy" /></a>
  <figcaption>TartanVO 原论文 Figure 1 · 匹配网络、位姿网络和相机内参输入的分工。运动估计需要知道同样像素位移对应何种射线变化。 <a href="https://arxiv.org/pdf/2011.00359v1#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: tartanvo-2 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanvo-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanvo-2.webp" width="1340" height="363" alt="TartanVO 原论文 Figure 2：不同相机视野与内参层的解释。固定训练相机的像素统计不应被误当成通用几何。" loading="lazy" /></a>
  <figcaption>TartanVO 原论文 Figure 2 · 不同相机视野与内参层的解释。固定训练相机的像素统计不应被误当成通用几何。 <a href="https://arxiv.org/pdf/2011.00359v1#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

TartanVO 先用匹配/光流网络产生运动线索，再把光流与内参图一起送给位姿网络。内参图的两通道为

$$
K_x(u,v)=\frac{u-c_x}{f_x},\qquad K_y(u,v)=\frac{v-c_y}{f_y}.
$$

它们表达像素对应的归一化相机射线坐标。焦距加倍时，相同角度运动产生的像素流变大；没有内参，网络很容易把镜头差异误当成运动差异。

<!-- vision-figure: tartanvo-3 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanvo-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanvo-3.webp" width="1340" height="259" alt="TartanVO 原论文 Figure 3：随机裁剪和缩放形成相机变化增强。内参和光流必须随图像变换同步更新。" loading="lazy" /></a>
  <figcaption>TartanVO 原论文 Figure 3 · 随机裁剪和缩放形成相机变化增强。内参和光流必须随图像变换同步更新。 <a href="https://arxiv.org/pdf/2011.00359v1#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: tartan-intrinsics -->
<figure>
  <a href="/HomepageX/media/tartanair/tartan-intrinsics.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartan-intrinsics.svg" width="1100" height="470" alt="自制图 4：归一化射线把像素运动与相机内参联系起来；示例使用 100 和 200 像素焦距。" loading="lazy" /></a>
  <figcaption>自制图 4 · 归一化射线把像素运动与相机内参联系起来；示例使用 100 和 200 像素焦距。</figcaption>
</figure>
<!-- /vision-figure -->

裁剪左上偏移 $(a,b)$、再缩放 $(s_x,s_y)$ 后，$f'_x=s_xf_x$、$c'_x=s_x(c_x-a)$，纵向同理。光流的两个分量也分别乘 $s_x,s_y$。仅改变 RGB 尺寸、不改标签与内参，会把数据增强变成错误监督。

### 6.2 Up-to-scale 损失明确承认不可观测量

归一化平移目标可写为

$$
\mathcal L_t=\left\|\frac{\widehat{\mathbf t}}{\max(\|\widehat{\mathbf t}\|,\epsilon)}-
\frac{\mathbf t^*}{\max(\|\mathbf t^*\|,\epsilon)}\right\|,
\qquad\mathcal L_{pose}=\mathcal L_t+\mathcal L_R.
$$

它不惩罚沿正确方向的幅值差，降低模型记住某个训练集绝对尺度的诱因。零平移或极小基线下，方向本身也不稳定，需要特殊处理。旋转的监督表示与权重要按作者配方核对，不能把旋转向量欧氏差当成任意大角度下完全等价的 SO(3) 测地距离。

<!-- vision-figure: tartanvo-4 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanvo-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanvo-4.webp" width="1340" height="381" alt="TartanVO 原论文 Figure 4：不同训练数据量与组合的收敛。训练损失下降不等同于跨域误差必然下降。" loading="lazy" /></a>
  <figcaption>TartanVO 原论文 Figure 4 · 不同训练数据量与组合的收敛。训练损失下降不等同于跨域误差必然下降。 <a href="https://arxiv.org/pdf/2011.00359v1#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: tartanvo-5 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanvo-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanvo-5.webp" width="1340" height="385" alt="TartanVO 原论文 Figure 5：不同损失及其超参数对训练/泛化的影响。尺度处理改变平移目标的含义，不能与米制误差混写。" loading="lazy" /></a>
  <figcaption>TartanVO 原论文 Figure 5 · 不同损失及其超参数对训练/泛化的影响。尺度处理改变平移目标的含义，不能与米制误差混写。 <a href="https://arxiv.org/pdf/2011.00359v1#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: tartanvo-6 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanvo-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanvo-6.webp" width="1340" height="253" alt="TartanVO 原论文 Figure 6：EuRoC 轨迹可视化。对照黑色真值检查转弯和闭合段，定量判断还需查看论文的对齐与尺度协议。" loading="lazy" /></a>
  <figcaption>TartanVO 原论文 Figure 6 · EuRoC 轨迹可视化。对照黑色真值检查转弯和闭合段，定量判断还需查看论文的对齐与尺度协议。 <a href="https://arxiv.org/pdf/2011.00359v1#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: tartanvo-7 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanvo-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanvo-7.webp" width="1340" height="280" alt="TartanVO 原论文 Figure 7：作者系统与商品跟踪设备的定性对照。相机、输入模态和失效处理不同，不能作为纯算法等条件排名。" loading="lazy" /></a>
  <figcaption>TartanVO 原论文 Figure 7 · 作者系统与商品跟踪设备的定性对照。相机、输入模态和失效处理不同，不能作为纯算法等条件排名。 <a href="https://arxiv.org/pdf/2011.00359v1#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: tartanvo-8 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanvo-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanvo-8.webp" width="1340" height="1423" alt="TartanVO 原论文 Figure 8：更多 TartanAir 测试轨迹，包含不同环境中的偏差。保留这些结果有助于观察泛化收益与残余失败。" loading="lazy" /></a>
  <figcaption>TartanVO 原论文 Figure 8 · 更多 TartanAir 测试轨迹，包含不同环境中的偏差。保留这些结果有助于观察泛化收益与残余失败。 <a href="https://arxiv.org/pdf/2011.00359v1#page=12" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

实验用消融区分内参输入、训练增强和 up-to-scale 目标的作用，并展示仿真训练到真实数据的迁移。单目轨迹评估允许何种尺度对齐，要与误差一起报告；经过真值尺度对齐的 ATE 不能证明在线系统已经观测到米制尺度。

## 7. IO / VIO：额外的数据通道还需要额外的物理假设

### 7.1 V1 与 V2 的范围不同

2020 年论文重点是视觉及从深度派生的几何标签。当前 V2 文档另提供 IMU、鱼眼/全景等工具，并解释 IMU 由位姿插值与微分产生。不能把 V2 的 IMU 能力倒写成原始 TartanVO 的传感器输入。[官方模态说明](https://tartanair.org/modalities.html)

### 7.2 从轨迹生成 IMU，应该生成比力而不是世界加速度

令 $R_{WB}$ 将机体系向量变到世界系、$\mathbf p_W(t)$ 为传感器位置，理想测量模型是

$$
\widetilde{\boldsymbol\omega}_B=\operatorname{vee}(R_{WB}^\top\dot R_{WB})+\mathbf b_g+\mathbf n_g,
$$

$$
\widetilde{\mathbf a}_B=R_{WB}^\top(\ddot{\mathbf p}_W-\mathbf g_W)+\mathbf b_a+\mathbf n_a.
$$

静止放在桌上的加速度计也会输出与重力相反的比力。把世界加速度直接当作加速度计读数，会让静止模型都错。若 IMU 与相机存在杆臂，还需考虑旋转引入的切向与向心加速度。

<!-- vision-figure: tartan-imu -->
<figure>
  <a href="/HomepageX/media/tartanair/tartan-imu.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartan-imu.svg" width="1100" height="470" alt="自制图 5：同一正弦轨迹的位置（米）、速度（米每秒）和加速度（米每二次方秒），保留正负号和共同时间轴；轨迹光滑不等于满足执行器限制。" loading="lazy" /></a>
  <figcaption>自制图 5 · 同一正弦轨迹的位置（米）、速度（米每秒）和加速度（米每二次方秒），保留正负号和共同时间轴；轨迹光滑不等于满足执行器限制。</figcaption>
</figure>
<!-- /vision-figure -->

这里是标准理想传感器模型的教学推导；具体噪声强度、bias 随机游走、时间同步和外参按实际生成配置设置。低频离散相机位姿经过样条再二阶微分，得到的高频信号会受样条平滑与采样影响；它不是现场真实 IMU 的独立测量。

### 7.3 Learning-based IO 最容易学到错误的运动先验

只用 IMU 的里程计模型可能借助人体步态、车载运动或设备佩戴方式约束速度漂移。任意六自由度虚拟相机轨迹并不自动符合这些运动规律。TartanAir 可用于传感器融合接口、可控扰动和部分表征训练，但训练目标域 IO 时仍需匹配动力学和噪声，并用真实 IMU 数据验证。

## 8. 仿真最大的价值，是把错误变得可定位

<!-- vision-figure: tartanair-10 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanair-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanair-10.webp" width="841" height="420" alt="TartanAir 原论文 Figure 10：SLAM 基线实验选择的六个环境，分别强调雨与光晕、闪烁光、低照明、落叶、弱纹理和动态物体。" loading="lazy" /></a>
  <figcaption>TartanAir 原论文 Figure 10 · SLAM 基线实验选择的六个环境，分别强调雨与光晕、闪烁光、低照明、落叶、弱纹理和动态物体。 <a href="https://arxiv.org/pdf/2003.14338v2#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 10 选择六类有代表性的环境，并在 easy/medium/hard 三种运动条件下比较。easy 固定 pitch/roll，较难设置加入六自由度运动并增加相邻帧位移和转角，因此难度变化同时涉及运动先验与收敛范围。

<!-- vision-figure: tartanair-11 -->
<figure>
  <a href="/HomepageX/media/tartanair/tartanair-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/tartanair/tartanair-11.webp" width="841" height="286" alt="TartanAir 原论文 Figure 11：同一路径开启／关闭困难因素的对照：落叶、运动机械、雨、风暴与昼夜变化。用控制变量检查它们对跟踪成功率和误差的影响。" loading="lazy" /></a>
  <figcaption>TartanAir 原论文 Figure 11 · 同一路径开启／关闭困难因素的对照：落叶、运动机械、雨、风暴与昼夜变化。用控制变量检查它们对跟踪成功率和误差的影响。 <a href="https://arxiv.org/pdf/2003.14338v2#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 11 则固定路径，只切换落叶、运动机械、雨、风暴或昼夜条件。原文在五个环境中各取 3–5 条轨迹、每条运行多次，以检查这些困难因素的影响。这比仅比较两个不同场景更能支持“哪个因素导致退化”的解释。

原论文的 SLAM 实验显示困难运动和成像条件会显著影响系统。基准里成功完成的轨迹与失败退出的轨迹要一起统计，只对成功片段计算平均 ATE 会掩盖鲁棒性问题。

训练划分也应按场景或环境资产考虑。把同一路径相邻帧随机分到训练和测试，甚至把同一个建筑资产的不同光照当成独立未知场景，都会高估泛化。最有说服力的组合是：控制变量仿真解释机制，未见环境检查泛化，真实传感器数据检验域差异。

TartanAir 让精确几何、困难条件与大量数据能够同时获得。它的贡献不在于证明仿真等同现实，而在于给我们一套可重复的问题：模型到底缺什么监督，失败来自哪里，新增机制是否真的解决了那个原因。
