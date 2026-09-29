---
title: "EgoForce 精读：用前臂和射线，把手放回相机前三维空间"
description: "从单目深度尺度歧义、FARM 与裁块内参，到点到射线闭式求解；逐项追踪手臂监督、标定误差和跨镜头实验。"
date: 2026-09-29
tags: [论文精读, 3D Perception, Project Aria, EgoForce, 手部重建]
draft: false
---

戴着眼镜伸手拿杯子，一个手部模型可能把每根手指弯得都很像，投回图像也几乎重合，却把手放在相机前一米，而真实手腕只离镜头半米。用它驱动屏幕里的手势动画似乎够用，用它抓取真实桌上的杯子就会暴露问题。

**EgoForce 要同时恢复手的内部姿态和它在相机坐标中的位置。** 它增加前臂几何线索，并把不同镜头的像素统一转换成射线，利用二维与三维关节对应求解整个手臂的平移。名字里的 Force 不代表它在估计接触力或肌肉力。

本文精读 Christen Millerdurai 等的 *EgoForce: Forearm-Guided Camera-Space 3D Hand Pose from a Monocular Egocentric Camera*，SIGGRAPH 2026，固定采用 [arXiv v1 的 23 页主文及附录](https://arxiv.org/abs/2605.12498v1)，并参考[官方实现](https://github.com/dfki-av/EgoForce)。它是 [3D Perception and Project Aria 专栏](/HomepageX/blog/3d-perception-and-project-aria/)的第四篇。

<!-- aria-figure: egoforce-1 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-1.webp" width="1702" height="727" alt="EgoForce 原论文 Figure 1：单目输入恢复相机坐标中的手和前臂，同时适配多种镜头。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 1 · 单目输入恢复相机坐标中的手和前臂，同时适配多种镜头。 <a href="https://arxiv.org/pdf/2605.12498v1#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

## 1. “手重建对了”至少有三种含义

### 局部手势、整体朝向、绝对位置分别看

把第 $i$ 个关节写成

$$
\mathbf P_i=\mathbf t+\mathbf J_i.
$$

$\mathbf J_i$ 是已经包含整体朝向和尺度、但以手腕等根节点为原点的三维关节；$\mathbf t$ 是整只手在相机坐标中的平移。手指弯曲正确，并不意味着 $\mathbf t$ 正确；甚至去掉整体旋转和尺度后形状很像，也不意味着手掌真正朝向杯柄。

针孔投影中，$\pi(s\mathbf P)=\pi(\mathbf P)$。一只两倍大的手放在两倍远的位置，可以产生相同二维关节。因此仅最小化二维重投影，无法从几何上确定未知手尺寸和深度。

<!-- aria-figure: egoforce-scale -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-scale.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-scale.svg" width="1100" height="500" alt="自制图 1：人工手骨架的三维截面作精确二倍相似变换：尺寸与深度同时加倍，投影射线保持一致。并非模型预测或真实用户手型。" loading="lazy" /></a>
  <figcaption>自制图 1 · 人工手骨架的三维截面作精确二倍相似变换：尺寸与深度同时加倍，投影射线保持一致。并非模型预测或真实用户手型。</figcaption>
</figure>
<!-- /aria-figure -->

前臂带来更长的可见结构和人体尺寸先验，有助于减少歧义，但不能凭单目图像严格证明某个用户的手有多大。论文附录也明确：精确度量尺度在缺少用户尺寸线索时仍然欠约束。

### 相机坐标不是世界坐标

EgoForce 的输出随相机移动而改变，它无需 SLAM 就能逐帧估计相机前方的手。若要把手与 [Boxer 的静态物体地图](/HomepageX/blog/3d-perception-and-project-aria/boxernet/)放到一个房间坐标系，还需要外部 $T_{w\leftarrow c}$：

$$
\mathbf P_w=R_{w\leftarrow c}\mathbf P_c+\mathbf t_{w\leftarrow c}.
$$

这一步不是 EgoForce 自己解决的世界定位，跨系统时间同步、标定与尺度一致性也需要另行检查。

## 2. 为什么不把裁块放大一点，顺便把前臂也拍进去？

### 手和前臂需要不同空间分辨率

把整个前臂连手缩进一个固定小裁块，会牺牲手指细节。HALO 因而单独读取手部 $224\times224$ 裁块和前臂 $112\times112$ 裁块，再让 token 交互。它为每只手分别运行，最后预测 21 个手关节和 3 个前臂关节、置信度以及参数化三维结构。

<!-- aria-figure: egoforce-2 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-2.webp" width="1702" height="696" alt="EgoForce 原论文 Figure 2：HALO 分别编码手和前臂，结合 CIT，再由射线求解器恢复整体平移。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 2 · HALO 分别编码手和前臂，结合 CIT，再由射线求解器恢复整体平移。 <a href="https://arxiv.org/pdf/2605.12498v1#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 2 的分工可从两条路径读：二维分支产生热图和像素位置；参数分支产生根相对三维形状；RSS 再用两者恢复绝对平移。不要把三维参数分支看成已经完成了全部相机空间定位。

### 裁成一样大，恰好丢掉了重要的相机信息

两只手裁块都被缩放成 224 像素后，原图中的大小、位于中心还是边缘、对应哪种镜头，可能不再可见。CIT（Crop Intrinsics Token）把裁块位置和视场信息补回来。

用针孔示例，原相机 $f_x=800$，裁块从 $x_0=100$ 开始、宽度 $s_x=400$，缩放到 $W=224$。新焦距和主点为

$$
f'_x=f_xW/s_x=448,\qquad
c'_x=(c_x-x_0)W/s_x.
$$

若 $c_x=320$，则 $c'_x=123.2$。把裁块机械视为主点始终在 112 的相机，就会改变射线方向。附录的 CIT 进一步编码局部观察方向、归一化主点偏移、裁块比例与半视场角，并结合位置编码，不仅仅是一个焦距数。

<!-- aria-figure: egoforce-crop -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-crop.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-crop.svg" width="1100" height="500" alt="自制图 2：针孔数值例：原焦距 800、主点 320，裁块起点 100、宽度 400，缩至 224 后焦距为 448、主点为 123.2。图中骨架只是几何示意。" loading="lazy" /></a>
  <figcaption>自制图 2 · 针孔数值例：原焦距 800、主点 320，裁块起点 100、宽度 400，缩至 224 后焦距为 448、主点为 123.2。图中骨架只是几何示意。</figcaption>
</figure>
<!-- /aria-figure -->

<!-- aria-figure: egoforce-15 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-15.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-15.webp" width="821" height="419" alt="EgoForce 原论文 Figure 15：CIT 广播到 patch token，通过拼接、MLP 和残差进行融合。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 15 · CIT 广播到 patch token，通过拼接、MLP 和残差进行融合。 <a href="https://arxiv.org/pdf/2605.12498v1#page=17" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 15 显示 CIT 被广播到每个对应裁块的 patch，经拼接、MLP 降维，再残差加回。这将“这张小图在原相机中来自哪里”传给视觉特征。手与前臂分别使用自己的裁块条件。

## 3. 鱼眼相机的难题：边缘像素不是普通针孔像素

### 局部去畸变和最终原生射线要配套

鱼眼画面中，手靠近边缘时会产生明显形变。EgoForce 在裁块编码前去除镜头特有的非线性畸变，再配合 CIT 做几何条件化。预测二维关节后，必须跟踪裁剪、缩放和去畸变之间的坐标关系，把关键点映射到正确的相机模型再反投影。

<!-- aria-figure: egoforce-11 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-11.webp" width="823" height="374" alt="EgoForce 原论文 Figure 11：原始鱼眼裁块、透视校正与局部去畸变的比较。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 11 · 原始鱼眼裁块、透视校正与局部去畸变的比较。 <a href="https://arxiv.org/pdf/2605.12498v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 11 对照了原始鱼眼裁块、整体透视校正和局部去畸变。把整张广角图强行展开为普通透视图，边缘可能被剧烈拉伸；因此“去畸变”不能简单等于“整幅图随便拉直”。

<!-- aria-figure: egoforce-12 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-12.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-12.webp" width="823" height="523" alt="EgoForce 原论文 Figure 12：加入裁块内参条件后，空间位置与朝向更符合观测。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 12 · 加入裁块内参条件后，空间位置与朝向更符合观测。 <a href="https://arxiv.org/pdf/2605.12498v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 12 则控制 CIT 的有无。局部外观相似不代表观察方向相同，几何条件能减少朝向和相机位置歧义。

原论文 Table 3 的 HOT3D 消融最能量化这个问题：原始设置 CS-MJE 为 $123.4$ mm；只有 CIT 为 $76.6$；只有局部去畸变为 $48.7$；两者结合为 $45.8$。所以总提升不能全归因于“多看了前臂”，正确处理镜头本身贡献很大。

## 4. 手与前臂如何变成可学习的三维结构？

### MANO 管手，FARM 管前臂

手使用 MANO：姿态 $\theta$ 包含 16 个旋转的 6D 参数，形状 $\beta\in\mathbb R^{10}$。前臂使用 FARM，其参数为五维形状 $\gamma$、6D 整体旋转与平移。

FARM 从沿肘到腕方向的圆环构造表面，半径沿长度变化；再用 PCA 将形状压成五维。附录用 AMASS 提取的成人 SMPL 前臂样本建立形状空间，保留约 99% 的形状方差。这个百分比描述所用样本内的 PCA 表达，并不保证覆盖儿童或所有身体差异。

<!-- aria-figure: egoforce-14 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-14.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-14.webp" width="823" height="453" alt="EgoForce 原论文 Figure 14：FARM 接到 MANO 腕部的前后对照，并沿肘方向施加小偏移。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 14 · FARM 接到 MANO 腕部的前后对照，并沿肘方向施加小偏移。 <a href="https://arxiv.org/pdf/2605.12498v1#page=16" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 14 把 FARM 腕端与 MANO 手腕对齐，并沿肘方向加约前臂长度 3% 的小偏移以减少交叠。这里是网格连接策略，不是额外传感器测出的解剖结构。

### 前臂不在画面里时，不能把空白当真实观测

前臂可见时，模型使用前臂视觉 token；不可见时使用 missing-arm token，并从手部特征条件化的变分先验采样前臂表示。简化写为

$$
\mathbf z=\boldsymbol\mu(\mathbf f_H)
+\boldsymbol\sigma(\mathbf f_H)\odot\epsilon,
\quad \epsilon\sim\mathcal N(0,I),
\qquad \mathbf f_A^{\rm prior}=g(\mathbf z).
$$

它补的是与手部相容的合理前臂，并非重新获得被遮挡的观测。原文消融中，前臂不可见时先验改善了前臂误差，而手部误差几乎不变，这与它的职责一致。

<!-- aria-figure: egoforce-7 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-7.webp" width="819" height="667" alt="EgoForce 原论文 Figure 7：前臂不可见时的条件先验；补全的是合理姿态。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 7 · 前臂不可见时的条件先验；补全的是合理姿态。 <a href="https://arxiv.org/pdf/2605.12498v1#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

当手被杯子挡住、前臂仍可见，真实前臂输入则有另一种作用：提供腕部朝向与肢体延伸方向。

<!-- aria-figure: egoforce-6 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-6.webp" width="823" height="1018" alt="EgoForce 原论文 Figure 6：物体遮挡手时，前臂输入改善手腕朝向和三维手姿。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 6 · 物体遮挡手时，前臂输入改善手腕朝向和三维手姿。 <a href="https://arxiv.org/pdf/2605.12498v1#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

<!-- aria-figure: egoforce-4 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-4.webp" width="819" height="542" alt="EgoForce 原论文 Figure 4：按可见手关节比例分组的前臂收益；位置与加速度误差改善并不相同。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 4 · 按可见手关节比例分组的前臂收益；位置与加速度误差改善并不相同。 <a href="https://arxiv.org/pdf/2605.12498v1#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 6 给出具体遮挡样例；Figure 4 按手关节可见比例统计。收益在部分遮挡区域更明显，但不能据此假定完全遮挡下也能恢复真实手指动作。网络依然需要依靠先验补全。

## 5. 核心推导：点到射线为什么能求出三维平移？

### 把不同镜头都变成单位方向

对每个二维关键点，使用已标定相机模型反投影成单位方向 $\mathbf d_i$。理想情况下，根相对关节加整体平移应落在对应射线上：

$$
\mathbf t+\mathbf J_i=\lambda_i\mathbf d_i.
$$

未知量看起来有一个三维平移和每个关节各自的深度 $\lambda_i$。但我们只关心共同平移，可以先消掉深度。

### 用正交投影器去掉沿射线方向

定义

$$
\Pi_i=I-\mathbf d_i\mathbf d_i^\mathsf T.
$$

因为 $\|\mathbf d_i\|=1$，有 $\Pi_i\mathbf d_i=0$。于是

$$
\Pi_i(\mathbf t+\mathbf J_i)=0.
$$

$\Pi_i\mathbf P_i$ 就是点偏离射线所在直线的垂直分量。例如 $\mathbf d=(0,0,1)$ 时，$\Pi=\operatorname{diag}(1,1,0)$：点 $(0.02,-0.01,0.6)$ 米的横向残差是 $(0.02,-0.01,0)$，平方距离为 $0.0005\,\mathrm m^2$。深度 $0.6$ 没有被这一条射线单独约束。

<!-- aria-figure: egoforce-rays -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-rays.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-rays.svg" width="1100" height="500" alt="自制图 3：用向量投影精确画出点到无限直线的垂直残差。RSS 同时求解所有关节共享的平移；正向深度不是这个无约束闭式解自动施加的条件。" loading="lazy" /></a>
  <figcaption>自制图 3 · 用向量投影精确画出点到无限直线的垂直残差。RSS 同时求解所有关节共享的平移；正向深度不是这个无约束闭式解自动施加的条件。</figcaption>
</figure>
<!-- /aria-figure -->

这里的距离严格说是点到射线**所在直线**的距离；式子本身未强制 $\lambda_i>0$。实际有效解还应处于相机可见的一侧。这个细节能帮助理解闭式线性解的范围。

### 多个不同方向，共同确定一个平移

网络预测的置信度 $w_i\in(0,1)$ 调节关节的贡献：

$$
E(\mathbf t)=\sum_iw_i\|\Pi_i(\mathbf t+\mathbf J_i)\|_2^2.
$$

由于 $\Pi_i$ 对称且幂等，对 $\mathbf t$ 求导得到

$$
A\mathbf t=-\mathbf b,\qquad
A=\sum_iw_i\Pi_i,\qquad
\mathbf b=\sum_iw_i\Pi_i\mathbf J_i.
$$

带小阻尼的解为

$$
\hat{\mathbf t}=-(A+\varepsilon I)^{-1}\mathbf b.
$$

实现时应解线性系统，不必显式构造矩阵逆。它是一个 $3\times3$ 问题，因此额外计算小。针孔、鱼眼和畸变广角的差别集中在“像素怎样变成方向”这一步，后面的最小二乘形式相同。

<!-- aria-figure: egoforce-3 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-3.webp" width="823" height="777" alt="EgoForce 原论文 Figure 3：射线求解器把二维关节、置信权重与根相对三维结构组合为相机空间位置。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 3 · 射线求解器把二维关节、置信权重与根相对三维结构组合为相机空间位置。 <a href="https://arxiv.org/pdf/2605.12498v1#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

给一个可复算的三点例子：设根相对关节为 $(0,0,0)$、$(0.1,0,0)$、$(0,0.1,0)$ 米，真实平移为 $(0,0,1)$ 米。将三个平移后坐标分别归一化为射线，所有权重取一，无遮挡无噪声时解出同一个 $(0,0,1)$。但若把所有 $\mathbf J_i$ 和 $\mathbf t$ 同时放大两倍，射线仍然相同。**RSS 恢复深度的前提，是网络已给出可信的相对三维尺度；它没有凭空消灭单目尺度歧义。**

### 远处小手为什么仍可能抖？

当所有射线近乎平行，$A$ 在共同方向上的约束很弱，二维细微抖动会转成大深度变化。增加前臂关节能扩大空间跨度，有助于改善条件，但遮挡或错误前臂也可能引入坏约束。低置信关节会被降权；如果所有权重都变得很小，阻尼将主导求解，同样不是正确答案的保证。

<!-- aria-figure: egoforce-conditioning -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-conditioning.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-conditioning.svg" width="1100" height="500" alt="自制图 4：二维对称射线的法矩阵，半夹角 30 度时深度特征值为 0.5，5 度时约 0.015。红色等高线按同一误差阈值计算，展示小夹角病态。" loading="lazy" /></a>
  <figcaption>自制图 4 · 二维对称射线的法矩阵，半夹角 30 度时深度特征值为 0.5，5 度时约 0.015。红色等高线按同一误差阈值计算，展示小夹角病态。</figcaption>
</figure>
<!-- /aria-figure -->

论文在求解后对相机平移使用常速度 Kalman 滤波，并阻断求解器向根相对三维预测的梯度，以免偶发不稳定解污染形状学习。平滑只抑制时间噪声，不能把始终偏离的手自动校回正确位置。

<!-- aria-figure: egoforce-13 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-13.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-13.webp" width="821" height="503" alt="EgoForce 原论文 Figure 13：深度提升、DGP 与 RSS 的比较；重点看侧面深度错位。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 13 · 深度提升、DGP 与 RSS 的比较；重点看侧面深度错位。 <a href="https://arxiv.org/pdf/2605.12498v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 13 比较不同提升方法，看侧面深度比只看输入视角更有意义。二维重投影相似时，三维放置仍可能完全不同。

## 6. 监督从哪里来，每一项损失负责哪条路径？

### 并非所有数据集都有前臂真值

训练包含 Re:InterHand、HandCO、H2O、ARCTIC、HO3D、HOT3D，共约 367 万 RGB 图像。手部 MANO 标签较丰富，前臂则需另做：ARCTIC 从已有 SMPL-X 转换并拟合 FARM；H2O 利用多视角关键点和轮廓拟合。其余数据的前臂可见性或深度条件不足，不能假装都有同等监督。

未提供 FARM 参数时，论文将相应 FARM 与相对朝向损失关掉；落在图像外的二维关键点也被掩码。**没有标签不等于零姿态标签。** 这是联合训练异构数据时最容易出错的一处。

### 七项损失不是七个同尺度数字

总目标为

$$
\mathcal L=\mathcal L_H+\mathcal L_J+\mathcal L_{\rm MANO}
+\mathcal L_{\rm FARM}+\mathcal L_{\rm rel}
+\mathcal L_{\rm prior}+\mathcal L_{\rm cs}.
$$

| 损失 | 监督对象与来源 | 原文内部权重 |
| --- | --- | --- |
| 热图 | 二维手／前臂关节位置构造的目标热图 | 手 20，前臂 100 |
| 根相对关节 | 去根平移后的三维关节 | 手 1，前臂 5 |
| MANO | 手姿态、手形状参数 | 5、0.01 |
| FARM | 前臂形状与整体旋转 | 0.5、25 |
| 相对朝向 | 同时具备手臂监督的帧 | 0.5 |
| 前臂先验 | 与标准高斯的 KL 散度 | 1 |
| 相机空间关节 | RSS 后的绝对三维关节 | 手与前臂均 0.001 |

表中权重来自原文第 3.4 节，已放在各项内部，不应再把它们当额外总权重重复乘一次。位置、热图值、旋转表示和形状系数的数值尺度不同；重实现若更改坐标单位或求和方式，这组数值不能照搬解释。

### 跟踪一个关节的两条监督路径

二维热图误差促使峰值接近标注像素；根相对三维误差让手掌、指骨和前臂形成正确结构。两者在 RSS 中结合成绝对关节，再由相机空间损失检查是否放到正确深度。

若手指内部形状正确，但整只手偏移 $0.1$ 米，根相对损失可以很小，相机空间项仍会对每个关节产生平移误差。反之，若腕点位置正确、手指弯错，根相对关节和 MANO 项会惩罚这种错误。它们并不是对同一个结果重复打分。

相对朝向项在合法旋转上比较 $R_HR_A^\mathsf T$，采用 SO(3) 测地角度的平方。一个 $10^\circ$ 的相对旋转误差约为 $0.1745$ 弧度，乘权重后的单帧贡献约 $0.5\times0.1745^2=0.0152$；把角度直接按“10”代入会把量纲弄错。

对于一维高斯先验，KL 为

$$
D_{\rm KL}\bigl(\mathcal N(\mu,\sigma^2)\|\mathcal N(0,1)\bigr)
=\tfrac12(\mu^2+\sigma^2-\log\sigma^2-1).
$$

$\mu=0,\sigma=1$ 时为零；$\mu=1,\sigma=1$ 时为 $0.5$。这个项规范潜变量分布，不直接保证某个遮挡前臂就是真实姿态；几何学习与可见数据仍然必不可少。

## 7. 实验：28% 的改善究竟改善了什么？

### 相机位置误差与对齐后手形误差不要混淆

CS-MJE 在相机坐标直接测平均关节欧氏误差；RS-MJE 减去根平移；PS-MJE 经过尺度、旋转和平移对齐。单位均为毫米。加速度误差 CS-ACC／RS-ACC 的单位是 $\mathrm{m/s^2}$，用于检查时序稳定性。

原论文 Table 1 的主要比较如下：

| 数据集 | HandDGP CS-MJE ↓ | EgoForce CS-MJE ↓ | HandDGP PS-MJE ↓ | EgoForce PS-MJE ↓ |
| --- | ---: | ---: | ---: | ---: |
| ARCTIC | 51.7 | 49.5 | 9.9 | 8.0 |
| HOT3D | 61.3 | 43.9 | 8.6 | 6.6 |
| H2O | 29.9 | 25.0 | 6.3 | 5.6 |
| HO3D | 50.3 | 49.5 | 9.3 | 9.0 |

HOT3D 的相对下降为 $(61.3-43.9)/61.3\approx28.4\%$。它是该协议下的**相机空间关节误差**变化，不是每个数据集都下降 28%，也不是手指全部精确到 6.6 mm；后者是去掉整体变换后的 PS-MJE。

HandDGP 的训练代码未公开，作者使用自己的重实现，并在附录与公开权重进行了同预处理比较。HOT3D 使用作者划分的训练／验证帧来计算 CS-MJE；ARCTIC 也以带标签验证集作为相机空间测试代理。复现数字时必须匹配这些划分，不能拿官方隐藏测试集排行替代。

<!-- aria-figure: egoforce-5 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-5.webp" width="823" height="660" alt="EgoForce 原论文 Figure 5：二维看起来对齐仍可能存在深度误差，侧视图能揭示这种歧义。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 5 · 二维看起来对齐仍可能存在深度误差，侧视图能揭示这种歧义。 <a href="https://arxiv.org/pdf/2605.12498v1#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

<!-- aria-figure: egoforce-8 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-8.webp" width="1702" height="1744" alt="EgoForce 原论文 Figure 8：ARCTIC、H2O、HOT3D 多视角定性对照，灰色为真值。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 8 · ARCTIC、H2O、HOT3D 多视角定性对照，灰色为真值。 <a href="https://arxiv.org/pdf/2605.12498v1#page=9" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 5 和 Figure 8 的侧视角揭示前后错位。仅看投影很容易高估结果，灰色真值与彩色预测在另一视角的距离才更接近 CS-MJE 所衡量的问题。

### 手部稳定性与前臂稳定性并非同时单调改善

原文前臂可见消融中，加入前臂图像使手部 CS-ACC 从 $19.3$ 降到 $15.2\,\mathrm{m/s^2}$，但前臂自己的 CS-ACC 从 $20.7$ 升到 $22.7$。更多视觉证据让动作更富变化，也可能使前臂预测更抖。这提醒我们，不要把一个分支的收益自动推广到整个身体。

<!-- aria-figure: egoforce-16 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-16.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-16.webp" width="1702" height="437" alt="EgoForce 原论文 Figure 16：HOT3D 相机坐标轨迹；尤其比较深度轴和起止点。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 16 · HOT3D 相机坐标轨迹；尤其比较深度轴和起止点。 <a href="https://arxiv.org/pdf/2605.12498v1#page=20" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 16 的轨迹比较尤其要看深度方向。但它仍是指定序列的定性证据，系统平均误差与滤波效果应结合表格。RSS 在 HOT3D 上单独使用的 CS-MJE 为 $45.8$ mm，加 Kalman 后为 $43.9$；不要把滤波后的最终成绩全部记到闭式求解器头上。

## 8. 原图中的跨设备结果，还能说明什么？

<!-- aria-figure: egoforce-9 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-9.webp" width="1702" height="1982" alt="EgoForce 原论文 Figure 9：多个数据集的手网格重投影；投影质量需结合三维指标判断。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 9 · 多个数据集的手网格重投影；投影质量需结合三维指标判断。 <a href="https://arxiv.org/pdf/2605.12498v1#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 9 展示手网格重投影，检查手指与物体边缘的关系。它说明多种镜头下视觉对齐的可能性，但遮挡后面仍没有直接观测。

<!-- aria-figure: egoforce-10 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-10.webp" width="1702" height="1516" alt="EgoForce 原论文 Figure 10：不同光学模型下的手和前臂联合重投影。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 10 · 不同光学模型下的手和前臂联合重投影。 <a href="https://arxiv.org/pdf/2605.12498v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 10 把前臂也画出来，可检查腕部连接和延伸方向。论文没有把 FARM 当成精密前臂解剖重建；圆环和刚体近似会丢掉桡骨、尺骨相对运动和轴向扭转。

<!-- aria-figure: egoforce-17 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-17.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-17.webp" width="1702" height="374" alt="EgoForce 原论文 Figure 17：HO3D 与无标定野外视频的定性结果，后者使用估计的内参。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 17 · HO3D 与无标定野外视频的定性结果，后者使用估计的内参。 <a href="https://arxiv.org/pdf/2605.12498v1#page=20" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 17 的野外样例使用估计内参。这些视频没有同等级别三维真值，不能与有标定数据上的误差直接比较。方法对准确的相机几何仍然有依赖。

<!-- aria-figure: egoforce-19 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-19.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-19.webp" width="1702" height="900" alt="EgoForce 原论文 Figure 19：与 UmeTrack 的单视图比较；裁块生成协议必须与指标一起阅读。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 19 · 与 UmeTrack 的单视图比较；裁块生成协议必须与指标一起阅读。 <a href="https://arxiv.org/pdf/2605.12498v1#page=22" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 19 与 UmeTrack 的比较也要读裁块协议。附录区分用真值三维关节生成透视裁块的理想设置，与二维框生成裁块的现实设置。UmeTrack 本身主要面向多视角，单视图对照只能支持这个受限协议里的结论。

## 9. 边界：改善尺度歧义，不代表彻底解除歧义

<!-- aria-figure: egoforce-18 -->
<figure>
  <a href="/HomepageX/media/egoforce/egoforce-18.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/egoforce/egoforce-18.webp" width="825" height="1182" alt="EgoForce 原论文 Figure 18：标定扰动实验；中等误差下的改善不构成部署时选择内参的依据。" loading="lazy" /></a>
  <figcaption>EgoForce 原论文 Figure 18 · 标定扰动实验；中等误差下的改善不构成部署时选择内参的依据。 <a href="https://arxiv.org/pdf/2605.12498v1#page=21" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 18 在标定扰动中发现中等扰动有时反而改善误差。作者解释，这可能涉及数据集内参与软件估计内参之间的偏差。但选择“最优扰动”需要真值三维手位姿，部署时不能据此主动把标定改坏。

模型也依赖有标定的三维训练集，不能直接享用所有无三维标签的网络手图。前臂形状先验主要来自成人身体样本；非常规体型、重遮挡、快速运动和不同成像条件仍可能失败。RSS 在近乎平行射线下不适定，Kalman 滤波也无法恢复长期错误尺度。

论文在 RTX 3090 上报告两手完整链路约 14 FPS，包括手臂检测、HALO 与 RSS；网络前向约 $24.2$ ms、提升约 $3.1$ ms，检测另有约 $40$ ms。这里的神经网络加解析几何，在桌面 GPU 上具备互动可能性，但不是眼镜端原生运行速度。

它最有启发性的部分，是把“视觉先验估计结构”和“标定几何求整体位置”分工清楚。下一篇[照片级第一人称场景重建](/HomepageX/blog/3d-perception-and-project-aria/photoreal-egocentric-reconstruction/)继续追问相机模型：如果连一帧内部每一行的曝光时间都不同，只有一个相机位姿还够不够？

## 参考资料

- [EgoForce，arXiv v1，含 19 幅编号图与附录](https://arxiv.org/abs/2605.12498v1)
- [作者项目](https://dfki-av.github.io/EgoForce/)与[源码](https://github.com/dfki-av/EgoForce)
