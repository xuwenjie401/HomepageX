---
title: "LAMP 精读：先消除自己的运动，再在三维世界中看懂别人"
description: "从世界坐标射线和 Plücker 表示，到多相机接力、合成人体监督和时序拟合，解释 LAMP 为什么能定位人，也为什么不能把平滑当成零延迟。"
date: 2026-09-29
tags: [论文精读, 3D Perception, Project Aria, LAMP, 人体运动]
draft: false
---

你戴着眼镜走进厨房，朋友正从桌边走向门口。你转头时，朋友会在图像里快速横移；你走近时，他会在图像里变大；他经过视场边缘时，又可能从前方相机消失、出现在侧面相机中。

一个只在视频里追像素的人体模型，面对的其实是两套运动混合后的结果：**你的相机在动，他的身体也在动。** LAMP 的转折点是：既然现代头戴设备已经提供了相机定位，就先把二维观测变成统一世界中的射线，再让网络学习人怎么运动。

本文讲解 Nan Yang 等的 *LAMP: Localization Aware Multi-camera People Tracking in Metric 3D World*，CVPR 2026，固定使用 [arXiv v1 与附录](https://arxiv.org/abs/2605.05390v1)。这里的 LAMP 不是同名的语言辅助姿态估计或机器人操作方法。本文属于 [3D Perception and Project Aria 专栏](/HomepageX/blog/3d-perception-and-project-aria/)。

## 训练资源、卡时与数据量

| 项目 | 论文可确认的内容 |
| --- | --- |
| 训练数据 | Nymeria 提供同步 Aria 观测、定位与 Xsens/SMPL 动作；训练还用真值三维关节投影到虚拟相机生成 Gen 2 配置样本。论文正文没有汇总最终帧数或小时数。 |
| 训练配置 | 三个 Transformer 编解码块、内部维度 512、四秒窗口；30 Hz 时每个窗口为 120 帧。噪声投影、缺失观测和干净片段混合属于数据构造成本。 |
| 硬件与卡时 | 训练 200 个 epoch，使用 4 个节点的 NVIDIA H100，约 19 小时；论文没有给出每节点 GPU 数，不能把它换算成精确 GPU-hours。RTX 4090 上约 12.5 Hz 是十个 tracklet 的完整推理链路，不是训练卡时。 |

<!-- aria-figure: lamp-1 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-1.webp" width="1649" height="589" alt="LAMP 原论文 Figure 1：相机接力下的长时轨迹与多人的广视场覆盖。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 1 · 相机接力下的长时轨迹与多人的广视场覆盖。 <a href="https://arxiv.org/pdf/2605.05390v1#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 1 的左侧强调同一人的长期空间轨迹，右侧强调多人的视场覆盖。要理解这些效果，首先得区分“骨架看起来像人”和“这个人被放到了世界中的正确位置”。

## 1. 第一层困难：图像运动并不是人体运动

### 同一个静止的人，也能在图像里跑得很快

用 $T_{w\leftarrow c}(t)=(R(t),\mathbf o(t))$ 表示相机到世界的变换。世界中关节位置为 $\mathbf X_w(t)$，其相机坐标是

$$
\mathbf X_c(t)=R(t)^\mathsf T\bigl(\mathbf X_w(t)-\mathbf o(t)\bigr).
$$

即使关节完全不动，只要 $R$ 或 $\mathbf o$ 变化，$\mathbf X_c$ 就会变化。先在相机系拟合一个“平滑的人”，最后再转换到世界，可能已经让网络把观察者的摇头误当作目标的摇晃。

举个只含平移的例子：人的世界横坐标始终为 $2$ 米，相机从 $0$ 米移动到 $0.5$ 米。人在相机中的横坐标从 $2$ 米变成 $1.5$ 米；把已知相机位置加回来，两帧都是 $2$ 米。LAMP 把这个已知变化提前消掉，让网络集中处理真实人体的变化。

<!-- aria-figure: lamp-world -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-world.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-world.svg" width="1100" height="500" alt="自制图 1：一维度量示例：观察者前进 0.5 m，静止目标的相机坐标从 2 m 变为 1.5 m，世界坐标保持 2 m。" loading="lazy" /></a>
  <figcaption>自制图 1 · 一维度量示例：观察者前进 0.5 m，静止目标的相机坐标从 2 m 变为 1.5 m，世界坐标保持 2 m。</figcaption>
</figure>
<!-- /aria-figure -->

### 但“提到世界里”还不是三维点

二维关节只提供方向。反投影得到单位向量 $\mathbf d_c$ 后，世界射线为

$$
\mathbf r_w(\lambda)=\mathbf o_w+\lambda\mathbf d_w,\qquad
\mathbf d_w=R_{w\leftarrow c}\mathbf d_c,\qquad \lambda>0.
$$

这里方向向量只乘旋转，**不能加平移**；相机中心则必须做完整刚体变换。射线上哪个深度才是手腕，需要其他视角、时间上下文和人体先验来决定。所谓 early lifting，是提前提升成有位姿的射线，不是提前获得三维真值。

## 2. LAMP 的整体分工：检测、关联与拟合

<!-- aria-figure: lamp-2 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-2.webp" width="1653" height="364" alt="LAMP 原论文 Figure 2：先检测与关联，再把射线变换到局部世界坐标，最后拟合人体运动。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 2 · 先检测与关联，再把射线变换到局部世界坐标，最后拟合人体运动。 <a href="https://arxiv.org/pdf/2605.05390v1#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

全系统先在每张图上检测人和二维关键点，再按身份把跨相机、跨时间观测组成 tracklet；LAMP-Net 针对每个人的射线序列输出人体运动。论文采用 SMPL 参数表示：关节姿态 $\boldsymbol\theta$、体型 $\boldsymbol\beta$、根旋转 $R$、根平移 $\boldsymbol\tau$。

若 $f_{\rm SMPL}$ 返回局部关节与网格顶点，则世界中的输出为

$$
(\mathcal J^t,\mathcal V^t)
=R^t f_{\rm SMPL}(\boldsymbol\theta^t,\boldsymbol\beta^t)+\boldsymbol\tau^t.
$$

体型控制身体比例，姿态控制各关节相对旋转，根旋转与平移决定整个人在房间里的位置。相同局部姿态配上错误根平移，仍可能让一个站得很自然的人穿过桌子。

### 身份关联没有因为用了 Transformer 就消失

系统将已有世界三维 tracklet 投影到当前相机，预测它应当出现的图像区域，再与当前二维框计算匹配代价，用 Hungarian 匹配进行分配。未匹配的检测会创建新 tracklet；长时间不可见的 tracklet 会被停用。

这里使用已知相机位姿，已经补偿了佩戴者转头造成的图像位移。但如果上游把两个人的身份交换，后续“同一个人的时序射线”就被污染。LAMP 的论文重点是世界坐标运动估计，不是完整解决离场后重识别。

## 3. 世界射线如何成为网络输入？

### 局部世界坐标让数值稳定，仍保留度量关系

整个楼层的世界坐标可能很大，而且录制起点任意。LAMP 为每个时间窗口定义一个重力对齐的局部参考系 $L$，锚定窗口起始相机，再计算

$$
T_{L\leftarrow c_k}(t)=T_{L\leftarrow w}T_{w\leftarrow c_k}(t).
$$

这只改变坐标表达，不抹掉相机之间的基线、相机移动距离或人体真实尺度。窗口内所有相机和关节都必须采用同一参考系，不能逐帧各自清零后把目标位移也一起消掉。网络输出最后再变回原世界系。

### 为什么一条射线使用六个数？

论文将射线编码为 6 维 Plücker 表示，并附带二维关节置信度。用常见约定写成

$$
\boldsymbol\ell=(\mathbf d,\mathbf m),\qquad
\mathbf m=\mathbf o\times\mathbf d,\qquad
\|\mathbf d\|_2=1,\quad \mathbf d^\mathsf T\mathbf m=0.
$$

$\mathbf d$ 表示方向，$\mathbf m$ 表示这条直线相对坐标原点的位置。它不是六个独立自由度，也没有编码深度答案。沿同一条线将起点改成 $\mathbf o+a\mathbf d$，叉积仍相同，因为 $\mathbf d\times\mathbf d=0$。

例如 $\mathbf o=(1,0,0)$ 米、$\mathbf d=(0,0,1)$，得到 $\mathbf m=(0,-1,0)$ 米。另一台位于 $(0,0,0)$ 的相机即使看到相同方向，也有不同的 moment。若只保留方向，就会丢掉多相机基线信息。

<!-- aria-figure: lamp-rays -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-rays.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-rays.svg" width="1100" height="500" alt="自制图 2：三种二维截面的教学几何。世界射线仍不能消除小基线深度不确定性，也不能让不同时刻的移动关节自动成为同一点。" loading="lazy" /></a>
  <figcaption>自制图 2 · 三种二维截面的教学几何。世界射线仍不能消除小基线深度不确定性，也不能让不同时刻的移动关节自动成为同一点。</figcaption>
</figure>
<!-- /aria-figure -->

图中两条射线共同限制一个点的位置。但当射线近乎平行时，它们在深度上的交会非常不稳定；当观测来自不同时刻时，它们还可能指向**已移动的不同位置**。LAMP 因而没有把整段时序射线当成静态三角化问题，而是学习一个随时间变化、符合人体结构的解。

### 缺失观测需要显式表达

每个窗口的输入张量为

$$
\Phi\in\mathbb R^{T\times K\times J\times7},\qquad J=17.
$$

$T$ 是帧数、$K$ 是相机数、$J$ 是 MSCOCO 关节数，最后七维为六维射线加检测置信度。缺失二维关键点对应的输入置零。这个零向量是缺失编码，不是一条“正好指向零方向”的合法单位射线。

<!-- aria-figure: lamp-3 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-3.webp" width="798" height="482" alt="LAMP 原论文 Figure 3：同一人跨四个单色相机被观察，世界射线维持统一的运动表示。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 3 · 同一人跨四个单色相机被观察，世界射线维持统一的运动表示。 <a href="https://arxiv.org/pdf/2605.05390v1#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 3 最值得观察的是相机之间的接力：不要求每台相机一直看见整个人。只要身份和标定关系保持一致，网络可以利用同一窗口里不同视角看见的不同关节。

## 4. LAMP-Net：从射线云拟合一个连续的人

### 空间注意力补骨架，时间注意力补缺失

编码器沿关节和时间两个维度推理。单帧被桌面遮住的脚，可以从前后步态获得限制；某相机看不见的胳膊，可能由另一个视角补充。解码器用带时间编码的可学习 readout query 读取运动，且在各编码块进行交叉注意力，而不是只读取最后一层。

论文配置为三个 Transformer 编解码块、内部维度 512、四秒窗口；30 Hz 时是 120 帧。训练中旋转用连续的 6D 表示，最后转换为合法旋转。这个 6D 是旋转矩阵的参数化，与前面的六维 Plücker 射线含义不同。

网络输入没有原图纹理。因此它能避开许多外观域差异，也丢掉了衣服轮廓、肌肉和细致姿态证据。**把图像压成关键点是一种信息取舍**，不是任何任务都能无损使用的技巧。

### 异步多视角为什么还能有用？

如果左相机在 $t$ 时刻看到手腕，右相机在 $t+\Delta t$ 才看到它，两条射线通常不交于同一点。人体运动先验提供两时刻位置之间的联系，网络联合解释它们，而不是假装曝光完全同步。

这要求每个观测使用对应时间的相机位姿，并保持时间顺序。未知的大时间偏移和错误位姿仍会破坏射线一致性；“支持异步”不能被理解为“不需要正确时间戳”。

## 5. 训练标签：没有新设备的视频，怎么训练新相机布局？

Nymeria 提供同步的 Aria 观测、设备定位和 Xsens 人体动作，后者转换为 SMPL。训练时把真值三维关节投到虚拟相机，生成二维关键点，再按同样流程变成射线输入。网络学习的是“这组有噪射线如何对应这个人体动作”。

这个表示让训练不必依赖照片级合成图：只需有人体运动及相机布局，就能模拟新设备观察到的射线。作者用 Gen 1 的人体运动模拟 Gen 2 配置，再在真实 Gen 2 上展示效果。这里存在针对目标配置的数据模拟与训练，不能笼统写成任何新相机都无需适配。

### 训练不能只喂干净的投影点

真实关键点误差会在时间上连续，不是每帧独立地随机跳。附录因此加入时间相关高斯抖动、小幅逐帧噪声、相机视角丢失，以及持续 10–20 帧的关节遮挡；腕和踝等末端关节更容易被扰动，脚更容易被遮住。

训练也混入干净片段，避免只学习“处处都不可信”。这些操作把理想投影变成更接近实际检测的输入，监督人体运动不随输入噪声一起改变。

公开实现还在继续变化：本文所核查的[提交 `db3e4bf99928`](https://github.com/facebookresearch/LAMP/tree/db3e4bf9992874a85946b92e9c8933bba396bc44)中，`LifterSettings` 默认片段长度是 20，并将关键点分数按 0.5 阈值转成二值可见性；模型还可接收地面条件。下文的 120 帧、延迟与基准表格均按固定论文版本讲解，不能把它们不加区分地当作当前 demo 的默认配置。

## 6. 四项损失分别约束什么？

论文使用

$$
\mathcal L=\mathcal L_{\rm SMPL}+5\mathcal L_{\rm 3D}
+\mathcal L_{\rm V}+20\mathcal L_{\rm vel}.
$$

将预测量标为帽号，四项展开为

$$
\begin{aligned}
\mathcal L_{\rm SMPL}&=\frac1T\sum_t\|\hat H^t-H^t\|_2^2,\\
\mathcal L_{\rm 3D}&=\frac1T\sum_t\|\hat{\mathcal J}^t-\mathcal J^t\|_F^2,\\
\mathcal L_{\rm V}&=\frac1T\sum_t\|\hat{\mathcal V}^t-\mathcal V^t\|_F^2,\\
\mathcal L_{\rm vel}&=\frac1{T-1}\sum_{t=2}^T\|\hat{\mathcal D}^t-\mathcal D^t\|_F^2.
\end{aligned}
$$

$H$ 是编码后的人体参数，$\mathcal J$ 是关节、$\mathcal V$ 是顶点、$\mathcal D$ 是关节时间变化。参数损失帮助恢复姿态和体型，关节损失把它们落实到空间位置，网格损失补充整个人体的几何约束，速度损失约束动作随时间如何变化。

原式对时间平均，关节和顶点通过 Frobenius 范数求和；若自己实现改成每顶点平均，网格项相对强度就变了，不能机械照抄权重。参数、位置与时间差分的单位也不同，权重不是可直接比较的“重要性百分比”。

### 速度监督不是“越不动越好”

用一维关节举例，真值连续三帧为 $0,0.1,0.2$ 米，预测为 $0,0.2,0.2$ 米。以每帧差分表示变化时，真值是 $0.1,0.1$，预测是 $0.2,0$；两步都偏差 $0.1$，平均平方误差为 $0.01$。若预测一直不动为 $0,0,0$，速度监督同样会惩罚它，而不会奖励“非常平滑”。

<!-- aria-figure: lamp-loss -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-loss.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-loss.svg" width="1100" height="500" alt="自制图 3：教学轨迹只在中间一帧偏移 0.1 m，却改变了两个时间间隔的增量。论文的 velocity loss 比较离散差分，不能直接省略采样间隔后称为 m/s。" loading="lazy" /></a>
  <figcaption>自制图 3 · 教学轨迹只在中间一帧偏移 0.1 m，却改变了两个时间间隔的增量。论文的 velocity loss 比较离散差分，不能直接省略采样间隔后称为 m/s。</figcaption>
</figure>
<!-- /aria-figure -->

这个算例使用米／帧差分；若转换为米／秒，需要除以帧间隔，平方误差随之缩放。它说明的是速度项比较**预测运动和真实运动**，与只惩罚预测加速度的通用平滑项不同。

所有输出都相同并不能逃过监督：即使静止预测没有抖动，关节、网格与运动项仍会在真实走动片段上产生误差。另一方面，损失没有把“脚绝不穿地”写成严格碰撞约束，因此低抖动也不保证物理接触完全正确。

## 7. 滑动窗口平均：精度、稳定与延迟一起变化

<!-- aria-figure: lamp-4 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-4.webp" width="798" height="479" alt="LAMP 原论文 Figure 4：重叠窗口对同一时刻给出多个预测；平均能稳定输出，也会引入等待。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 4 · 重叠窗口对同一时刻给出多个预测；平均能稳定输出，也会引入等待。 <a href="https://arxiv.org/pdf/2605.05390v1#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

一个 120 帧窗口每次前进一帧，同一个时间点最终可被多个重叠窗口预测。若马上输出当前窗口末帧，是因果运行；若等到未来窗口也看到这个时间点再平均，通常更稳定，但增加延迟。

<!-- aria-figure: lamp-latency -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-latency.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-latency.svg" width="1100" height="500" alt="自制图 4：以 30 Hz、120 帧窗口示意滑窗平均的未来依赖。图中只画四个稀疏窗口以便阅读；实际窗口步长与实时输出策略另行决定。" loading="lazy" /></a>
  <figcaption>自制图 4 · 以 30 Hz、120 帧窗口示意滑窗平均的未来依赖。图中只画四个稀疏窗口以便阅读；实际窗口步长与实时输出策略另行决定。</figcaption>
</figure>
<!-- /aria-figure -->

最大使用全部 $T$ 个窗口时，最早的同刻预测可能要等 $T-1$ 帧。$T=120$、30 Hz 对应 $119/30\approx3.97$ 秒。这不是“单次网络前向要算四秒”，而是为了利用更多未来观测所付出的等待。

<!-- aria-figure: lamp-12 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-12.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-12.webp" width="1232" height="769" alt="LAMP 原论文 Figure 12：等待帧数、世界关节误差与抖动之间的权衡。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 12 · 等待帧数、世界关节误差与抖动之间的权衡。 <a href="https://arxiv.org/pdf/2605.05390v1#page=16" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 12 同时画了关节误差和 jitter 随等待帧数变化，读它时不要只挑最平滑的结果。虚拟角色回放可以接受延迟，实时交互则可能优先选择即时输出。

<!-- aria-figure: lamp-11 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-11.webp" width="1213" height="769" alt="LAMP 原论文 Figure 11：RTX 4090 上随 tracklet 数增长的分模块运行时间。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 11 · RTX 4090 上随 tracklet 数增长的分模块运行时间。 <a href="https://arxiv.org/pdf/2605.05390v1#page=16" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 11 则是运行时间，和刚才的等待延迟是另一回事。论文附录报告 RTX 4090 上十个 tracklet 时完整系统约 12.5 Hz，涉及二维检测、二维关键点与 LAMP-Net 三个部分。这里的“实时”必须连同人数、硬件和前端一起理解。

## 8. 评价前先决定：你是否允许把人重新对齐？

### 四种误差，可能给出相反的排名

- **MPJPE**：对齐根平移后看平均关节位置误差，主要检查局部姿态。
- **PA-MPJPE**：进一步做 Procrustes 对齐，消除整体变换的影响。
- **WA-MPJPE100**：在 100 帧窗口中做 SIM(3) 对齐后评价世界运动，仍可能隐藏全局尺度或位置偏差。
- **W-MPJPE**：不做对齐，直接比较世界关节位置，单位毫米。

如果整个人偏移一米，局部关节姿态完全正确，根对齐后的 MPJPE 可以接近零，W-MPJPE 却仍接近一米。对需要把虚拟人放在真实朋友身上的 AR 应用，这个差别至关重要。

### EMDB 证明的不是“所有指标都领先”

以下为原论文 Table 1，EMDB-2 使用真值相机位姿；LAMP 不在 EMDB 上训练或微调，采用单目输入进行比较。

| 方法 | MPJPE，mm ↓ | PA-MPJPE，mm ↓ | WA-MPJPE100，mm ↓ | W-MPJPE，mm ↓ |
| --- | ---: | ---: | ---: | ---: |
| PromptHMR | 68.1 | 40.1 | 63.9 | 278.1 |
| LAMP-mono | 82.3 | 46.3 | 77.8 | 165.1 |

LAMP 的绝对世界定位更好，但局部对齐后的身体姿态误差更高。这与前面说的表示取舍相呼应：射线方便几何融合，却放弃了一些像素外观线索。不能只引用摘要里的领先表述，删掉这三项不利结果。

<!-- aria-figure: lamp-10 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-10.webp" width="1653" height="910" alt="LAMP 原论文 Figure 10：EMDB 单目零样本结果；图中人体颜色表示世界顶点误差。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 10 · EMDB 单目零样本结果；图中人体颜色表示世界顶点误差。 <a href="https://arxiv.org/pdf/2605.05390v1#page=15" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 10 的颜色是世界顶点误差，支持空间定位的观察；它不能代替局部姿态指标。相似骨架放错空间的位置，在这种着色下会很明显。

### Nymeria 更接近自然头部运动的挑战

| 方法，Nymeria | MPJPE，mm ↓ | W-MPJPE，mm ↓ | Jitter ↓ |
| --- | ---: | ---: | ---: |
| PromptHMR | 109.2 | 246.0 | 114.1 |
| LAMP-mono | 92.3 | 203.4 | 23.8 |
| LAMP-mv | 54.8 | 113.3 | 21.8 |

此表沿用论文 jitter 的 $10\,\mathrm{m/s^3}$ 量纲标注。多视角配置使用 Gen 1 的一台 RGB 与两台 SLAM 相机。结果支持相机定位和多视角对自由头部运动的价值，但不要与 Gen 2 的四相机覆盖实验混成一套输入。

<!-- aria-figure: lamp-5 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-5.webp" width="1653" height="613" alt="LAMP 原论文 Figure 5：Nymeria 上的世界坐标顶点误差；深紫较低，黄色较高。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 5 · Nymeria 上的世界坐标顶点误差；深紫较低，黄色较高。 <a href="https://arxiv.org/pdf/2605.05390v1#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

<!-- aria-figure: lamp-9 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-9.webp" width="1653" height="678" alt="LAMP 原论文 Figure 9：Nymeria 补充比较：单目、窗口平均与多视角的差异。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 9 · Nymeria 补充比较：单目、窗口平均与多视角的差异。 <a href="https://arxiv.org/pdf/2605.05390v1#page=15" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 5 和附录 Figure 9 分别展示主文与更多样例。看世界网格颜色、脚的位置、人体与环境的对应关系，也要记住窗口平均结果使用了额外等待。

## 9. 消融和覆盖率：新信息究竟贡献在哪里？

Nymeria 消融 Table 2 中，只加入已知位姿射线提升，W-MPJPE 从 $296.3$ 降到 $209.6$ mm，而局部 MPJPE 为 $98.5$ 到 $98.3$ mm，几乎不变。这很好地隔离了核心收益：主要修复世界定位，并非凭空改善所有关节弯曲角度。

再加窗口平均，jitter 从 $91.7$ 降到 $23.8$，W-MPJPE 从 $209.6$ 到 $203.4$ mm。进一步引入真实多视角关键点，世界误差降到 $113.3$ mm。原文 Table 2 的多视角勾选与说明存在不一致，本文按第 4.3 节对 var4 的说明解释为真实 Gen 1 三相机观测，避免把它写成模拟真值关键点成绩。

<!-- aria-figure: lamp-6 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-6.webp" width="1653" height="257" alt="LAMP 原论文 Figure 6：一、二、四相机的跟踪覆盖率分布及样例；关注质量向完整覆盖一侧移动。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 6 · 一、二、四相机的跟踪覆盖率分布及样例；关注质量向完整覆盖一侧移动。 <a href="https://arxiv.org/pdf/2605.05390v1#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 6 在 Gen 2 多人场景中报告一、二、四相机平均覆盖约为 47%、65%、81%。多相机不只给同一点更多约束，也让更多人进入视场。**更高覆盖率不是被跟踪者的每个关节都更准**，两者需要不同指标。

<!-- aria-figure: lamp-8 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-8.webp" width="1653" height="356" alt="LAMP 原论文 Figure 8：Aria Gen 2 实时多人演示；这里的演示人体模型使用 MHR。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 8 · Aria Gen 2 实时多人演示；这里的演示人体模型使用 MHR。 <a href="https://arxiv.org/pdf/2605.05390v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 8 是在真实 Gen 2 场景中的定性演示。附录明确实时 demo 使用较轻量的 MHR 人体模型，而论文主要定量评测用 SMPL；这不改变射线思路，但复现系统时需要分清模型输出格式。

## 10. 留下哪些失败，为什么值得保留？

<!-- aria-figure: lamp-7 -->
<figure>
  <a href="/HomepageX/media/lamp/lamp-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/lamp/lamp-7.webp" width="798" height="409" alt="LAMP 原论文 Figure 7：EMDB 根轨迹误差；滑板序列保留了 LAMP 的不利结果。" loading="lazy" /></a>
  <figcaption>LAMP 原论文 Figure 7 · EMDB 根轨迹误差；滑板序列保留了 LAMP 的不利结果。 <a href="https://arxiv.org/pdf/2605.05390v1#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 7 的滑板片段中，LAMP 比 PromptHMR 更差。作者推测训练集缺少这种动作，人体先验可能把不常见运动拉向更常见的模式。这提醒我们：几何约束并没有取代数据分布，关键点稀疏时模型依然依赖学到的动作规律。

相机定位误差也不会被“世界坐标”这个名称自动消除。附录在 EMDB 对相机轨迹加入时间相关扰动，LAMP 的 W-MPJPE 从真值位姿下 $165.1$ mm，增至 $8$ cm／$0.2^\circ$ 扰动下的 $212.3$ mm；使用 DROID 位姿时为 $273.9$ mm。真实外部定位的质量仍是系统上限的一部分。

再有三条边界需要与结果一起记住：单目近乎平行射线的深度弱约束、严重遮挡下无法恢复细节、跨人关联错误带来的轨迹污染。附录的 90.3% 三维跟踪召回采用骨盆距离 $0.25$ 米阈值并忽略 ID，因此不能把它当成长期身份保持率。

LAMP 的关键洞见是：把已经知道的观察者运动提前用掉，网络才更容易学目标自身的运动。下一篇 [HMD²](/HomepageX/blog/3d-perception-and-project-aria/hmd2/)把视角转回来——如果目标就是佩戴者自己，而且身体根本不在画面里，方法必须明确面对“一个观测对应多个合理动作”。

## 参考资料

- [LAMP，arXiv v1 与附录](https://arxiv.org/abs/2605.05390v1)
- [官方项目与视频](https://facebookresearch.github.io/LAMP/)
- [Nymeria 数据集论文](https://arxiv.org/abs/2406.09905)
