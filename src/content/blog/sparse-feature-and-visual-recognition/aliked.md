---
title: "ALIKED 详解：只在关键点上，学习应该去哪里取描述信息"
description: "从 ALIKE 的亚像素检测到 ALIKED 的稀疏可变形描述头，逐步推导采样、梯度、稀疏 NRE 监督与速度边界。"
date: 2026-09-26
tags: [论文精读, 局部特征, 可变形卷积, 视觉定位]
---

两张照片拍到同一扇窗。第一张正视，第二张斜视：窗的左右边距、玻璃反光和周围墙面的位置都变了。一个固定方形感受野可能在第一张图里主要看到窗框，在第二张图里却混入很多墙面。描述子要相似，首先得让它们收集的证据有可比性。

ALIKED 把这个问题拆成两部分：**检测在哪里落点；描述这个点时，又该到哪些位置读取特征**。它沿用 ALIKE 的可微亚像素检测思路，新增稀疏可变形描述头 SDDH，既让采样位置适应局部形变，又避免在没有关键点的地方完整计算最终描述子。

> 本文采用 [ALIKED: A Lighter Keypoint and Descriptor Extraction Network via Deformable Transformation，arXiv:2304.03608v2](https://arxiv.org/abs/2304.03608v2)，对照[作者实现](https://github.com/Shiaoming/ALIKED/tree/683d7c65197395c0b3f01ebe76e1084a27e73a65)。ALIKED 与 ALIKE 是相关但不同的方法；下面特别区分继承的检测模块和新增的描述模块。

## 训练资源、卡时与数据量

| 项目 | 论文与固定代码版本给出的信息 |
| --- | --- |
| 训练数据 | MegaDepth 135 个场景、每场景约 10k 对的透视图像对（训练时排除 IMW2020 验证/测试场景），加上 Oxford、Paris、Aachen 等数据上的合成单应与风格变化图像对；论文没有把混合后的最终采样总数单独汇总。 |
| 训练配置 | $800\times800$ 输入，batch size 为 2，梯度累积 6 批；每次先取 400 个检测点，再随机取 400 个点并做 NMS。 |
| 硬件与卡时 | v2 论文和固定代码没有披露 GPU 型号、训练墙钟时间或 GPU-hours；这里的 5 像素是对应监督门限，不是训练成本。 |


## 1. 密集特征图，不一定要配密集描述子图

### 1.1 一次图像前向里，哪些计算真的被用到了

设图像大小为 $H\times W$，最终只保留 $N$ 个关键点，每点描述子维度 $D$。常见方案先计算 $H\times W\times D$ 的描述图，再在 $N$ 个坐标上采样。如果 $N\ll HW$，最后一段高维卷积的大部分输出没有被读取。

但不能因此把整个网络都变成只读 $N$ 个原始像素：关键点分数和局部表征仍需要图像上下文。ALIKED 保留共享密集特征 $F$，把较昂贵的**最终描述头**改为按关键点执行。

<!-- vision-figure: aliked-3 -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-3.webp" width="862" height="372" alt="ALIKED 原论文 Figure 3：作为对照的密集描述头 DMH：先在全图做卷积，再读取关键点。它突出 SDDH 避免的冗余计算。" loading="lazy" /></a>
  <figcaption>ALIKED 原论文 Figure 3 · 作为对照的密集描述头 DMH：先在全图做卷积，再读取关键点。它突出 SDDH 避免的冗余计算。 <a href="https://arxiv.org/pdf/2304.03608v2#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 3 是被替换的密集描述头：先在全部位置计算高维向量，再只读取关键点上的少量结果。这个基线帮助我们定位 SDDH 具体省掉了哪部分工作。

<!-- vision-figure: aliked-sparse-cost -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-sparse-cost.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-sparse-cost.svg" width="1100" height="470" alt="自制图 1：点标记表示最终描述子需要被计算的位置；ALIKED 仍然需要密集共享特征与分数图。" loading="lazy" /></a>
  <figcaption>自制图 1 · 点标记表示最终描述子需要被计算的位置；ALIKED 仍然需要密集共享特征与分数图。</figcaption>
</figure>
<!-- /vision-figure -->

例如 $640\times480$ 图像有 307200 个像素，若保留 1000 点，两者相差约 307 倍。这个比值只说明候选输出位置数，绝不是整网能加速 307 倍：骨干、分数头、NMS、采样和内存访问仍要付费。

### 1.2 为什么还需要可变形采样

简单地在每个关键点周围取固定 $K\times K$ patch，已经能减少冗余描述计算，却没有解决斜视下的支持区域变化。SDDH 再往前一步：先看中心附近的小特征块，预测 $M$ 个二维偏移，再去这些位置读取支持特征。

这里 $K$ 决定“用多大范围判断该去哪里取信息”，$M$ 决定“最后取多少个支持位置”。二者不是同一个量，$M$ 不需要等于 $K^2$。

## 2. 先把关键点位置做准：ALIKE 留下的 DKD

### 2.1 多尺度特征如何同时保留位置和语义

网络的四级特征尺度为原图、$1/2$、$1/8$ 和 $1/32$。各层经 $1\times1$ 通道变换与上采样对齐后拼接，形成共享特征 $F$。高分辨率分支保留边缘与精确位置，深分支提供更大的感受野；后两级使用可变形卷积。

<!-- vision-figure: aliked-1 -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-1.webp" width="1729" height="967" alt="ALIKED 原论文 Figure 1：多尺度编码、聚合、可微检测和稀疏描述头。共享特征是密集的，最终描述子只在关键点上构造。" loading="lazy" /></a>
  <figcaption>ALIKED 原论文 Figure 1 · 多尺度编码、聚合、可微检测和稀疏描述头。共享特征是密集的，最终描述子只在关键点上构造。 <a href="https://arxiv.org/pdf/2304.03608v2#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

原论文 Figure 1 需从左到右追踪三个对象：多尺度特征、单通道分数图、稀疏坐标和描述子。不要把中间的密集共享特征图误称为已经算完的密集描述子图。图中的 DKD 属于检测端，SDDH 属于描述端。

### 2.2 为什么 argmax 难训练，局部 softargmax 可以补上梯度

离散最大值的位置会突然从一个像素跳到另一个像素，普通反向传播无法直接对这种索引选择求有用梯度。DKD 先用 NMS 找离散候选，再在候选周围的固定小窗口内，用归一化分数计算连续位置。

窗口坐标为 $\mathbf c_k$，分数为 $s_k$，有

$$
a_k=\frac{\exp(s_k/\tau_{det})}{\sum_l\exp(s_l/\tau_{det})},
\qquad
\widehat{\mathbf p}=\sum_k a_k\mathbf c_k.
$$

一维例子中，坐标 $(-1,0,1)$ 的归一化质量为 $(0.1,0.3,0.6)$，位置就是 $0.5$ 像素，而非被限制在 $0$ 或 $1$。其梯度为

$$
\frac{\partial\widehat{\mathbf p}}{\partial s_k}
=\frac{a_k}{\tau_{det}}(\mathbf c_k-\widehat{\mathbf p}).
$$

因此几何误差可以把分数质量朝正确方向移动。但 NMS 候选集合的生成仍是离散的：DKD 的可微性作用在已选局部窗口内，不表示整套 top-k/NMS 索引选择都被连续化了。

<!-- vision-figure: aliked-subpixel -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-subpixel.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-subpixel.svg" width="1100" height="470" alt="自制图 2：按三个归一化权重计算得到 0.5 像素的连续位置；局部细化不等于 NMS 索引本身可微。" loading="lazy" /></a>
  <figcaption>自制图 2 · 按三个归一化权重计算得到 0.5 像素的连续位置；局部细化不等于 NMS 索引本身可微。</figcaption>
</figure>
<!-- /vision-figure -->

### 2.3 连续位置还需要尖锐而稳定的峰

如果分数在一条边上均匀铺开，softargmax 也会输出一个坐标，但它只是平均位置，不一定是可重检测的角点。峰值损失把归一化质量压向局部中心；双向重投影损失则要求变换后位置一致。

这解释了为什么“亚像素输出”本身不是精确性保证。只有坐标被真实几何监督约束、响应形状又避免退化，亚像素数字才有意义。

## 3. SDDH：描述子应该从哪里读信息

### 3.1 从固定卷积到可学习的支持位置

固定卷积可写为

$$
y(\mathbf p)=\sum_{k\in\mathcal R}W_kF(\mathbf p+\mathbf r_k),
$$

其中 $\mathcal R$ 是固定网格。可变形卷积引入偏移 $\Delta\mathbf r_k$。SDDH 则在每个稀疏关键点 $\mathbf p_i$ 处预测一组支持偏移

$$
\Delta_i=g_\theta(F_{K\times K}(\mathbf p_i))\in\mathbb R^{M\times2}.
$$

论文用一个无 padding 的 $K\times K$ 卷积压缩局部块，经 SELU 和 $1\times1$ 卷积得到 $2M$ 个数。注意这一步输出的是采样位置参数，而不是把原始图像整体做一次透视矫正。

<!-- vision-figure: aliked-2 -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-2.webp" width="1729" height="515" alt="ALIKED 原论文 Figure 2：SDDH 先预测支持位置，再双线性采样、编码并融合。预测位置数 M 与初始小块边长 K 分别控制不同成本。" loading="lazy" /></a>
  <figcaption>ALIKED 原论文 Figure 2 · SDDH 先预测支持位置，再双线性采样、编码并融合。预测位置数 M 与初始小块边长 K 分别控制不同成本。 <a href="https://arxiv.org/pdf/2304.03608v2#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: aliked-sampling -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-sampling.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-sampling.svg" width="1100" height="470" alt="自制图 3：教学示意中两幅图共享局部结构但发生剪切，支持采样位置跟随结构；真实偏移由描述损失间接学习。" loading="lazy" /></a>
  <figcaption>自制图 3 · 教学示意中两幅图共享局部结构但发生剪切，支持采样位置跟随结构；真实偏移由描述损失间接学习。</figcaption>
</figure>
<!-- /vision-figure -->

随后计算

$$
\widetilde{\mathbf d}_i=\sum_{m=1}^{M}
W_m\,\Phi\bigl(F(\mathbf p_i+\Delta_{im})\bigr),
\qquad
\mathbf d_i=\frac{\widetilde{\mathbf d}_i}{\|\widetilde{\mathbf d}_i\|_2}.
$$

$\Phi$ 是共享的通道变换与 SELU，$W_m$ 为融合支持位置的可学习权重。示意图里不同采样点的颜色表示同一输出槽位在两幅图中的角色；训练并没有直接给每个偏移一个人工“窗框左角”的标签。

### 3.2 双线性采样为什么能把梯度传给偏移

若采样位置为 $(x,y)$，落在整数格点 $(i,j)$ 与 $(i+1,j+1)$ 之间，令 $\alpha=x-i$、$\beta=y-j$，则

$$
\begin{aligned}
F(x,y)={}&(1-\alpha)(1-\beta)F_{ij}
+\alpha(1-\beta)F_{i+1,j}\\
&+(1-\alpha)\beta F_{i,j+1}
+\alpha\beta F_{i+1,j+1}.
\end{aligned}
$$

因此

$$
\frac{\partial F(x,y)}{\partial x}
=(1-\beta)(F_{i+1,j}-F_{ij})+
\beta(F_{i+1,j+1}-F_{i,j+1}).
$$

描述损失可以经这个梯度告诉偏移预测器：“往右读到的特征更有利于正确匹配”。在完全平坦区域，差分接近零，偏移的训练信号也会很弱；这是信息限制，而不是多加一层网络就自动消失的问题。

### 3.3 灵活采样不等于严格的几何不变性定理

如果两幅图的局部形变可以被支持位置调整近似吸收，最终描述子更可能保持相似。Figure 7 的支持区域可视化帮助观察网络究竟从何处收集信息。但偏移没有被强制限制成一个统一仿射矩阵或单应矩阵，也没有保证在任意新视角下满足严格等变关系。

它的好处是自由度高、能适应更一般的局部结构；代价是依赖训练分布，难以解释每个采样槽位，并且在严重尺度和视角共同变化时仍可能失败。把“可学习的鲁棒性”写成“解决任意形变”会夸大方法。

## 4. 没有密集描述图，监督怎么写

### 4.1 几何先决定正样本，描述相似度再决定概率

ALIKED 使用已知相机、深度或合成单应变换得到 $w_{AB}$。先将 A 中点投到 B，再寻找距离小于阈值的 B 点作为对应。训练设置使用 5 像素门限；这只是正样本构造规则，不是最终评估准确度的定义。

双向重投影损失为

$$
\mathcal L_{rp}=\operatorname{mean}_{(i,j)\in\mathcal M}
\frac{\|w_{AB}(\mathbf p_i)-\mathbf q_j\|_2+
\|w_{BA}(\mathbf q_j)-\mathbf p_i\|_2}{2}.
$$

没有有效几何对应的点不能被强行配给最近描述子。否则网络会用自身预测创造监督，再自我确认错误。

### 4.2 Sparse NRE：在稀疏候选集合上做分类

对 A 中一个描述子 $\mathbf d_i^A$，与 B 中所有 $N_B$ 个描述子计算点积 $s_{ij}$，再得到

$$
q_{ij}=
\frac{\exp((s_{ij}-1)/\tau_{des})}
{\sum_{k=1}^{N_B}\exp((s_{ik}-1)/\tau_{des})}.
$$

所有 logit 同减 1 不改变 softmax，它只改变数值表达。若几何正样本是 $j^*$，损失为 $-\log q_{ij^*}$；再对两个方向及有效对应取平均。

<!-- vision-figure: aliked-supervision -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-supervision.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-supervision.svg" width="1100" height="470" alt="自制图 4：由三个相似度直接计算的 softmax 与负对数，展示温度以及困难负样本对稀疏描述训练的影响。" loading="lazy" /></a>
  <figcaption>自制图 4 · 由三个相似度直接计算的 softmax 与负对数，展示温度以及困难负样本对稀疏描述训练的影响。</figcaption>
</figure>
<!-- /vision-figure -->

设相似度为 $(0.9,0.7,0.2)$、温度为 $0.1$，第一项正确，则概率约 $(0.880,0.119,0.001)$，负对数约 $0.128$。把第二个重复窗格的相似度从 $0.7$ 提高到 $0.9$，正确概率便降到约 $0.5$，损失升至约 $0.694$。这正是“相似还不够，必须比错误候选更相似”的竞争关系。

稀疏 NRE 与密集 NRE 的区别不仅是节省内存：负样本从全部像素变成已采样点，分母改变，难负样本分布也改变。因此训练点数、随机点比例与 NMS 策略属于目标函数的一部分。

### 4.3 峰值、可靠性和描述子各自管什么

峰值损失对局部 softmax 质量按距输出位置的距离加权，促使响应聚集。可靠性则取正确对应的描述匹配概率 $r_i$，用检测分数 $s_i$ 做归一化加权：

$$
\mathcal L_{re}^A=
\frac{\sum_i(1-r_i)s_i}{\sum_i s_i},
\qquad
\mathcal L_{re}=\frac12(\mathcal L_{re}^A+\mathcal L_{re}^B).
$$

论文式 (12) 的 softmax 本身是一个候选向量；进入标量可靠性权重时，应理解为取正确对应处的分量，不能拿整个向量直接冒充一个角点的置信值。

可靠性让检测器更愿意保留描述子能区分的位置，峰值项让位置尖锐，重投影项让位置正确，描述损失则把正负候选拉开。论文总目标为

$$
\mathcal L=\mathcal L_{rp}+0.5\mathcal L_{pk}
+5\mathcal L_{ds}+\mathcal L_{re}.
$$

这些系数依赖论文的平均方式和采样规则。把 $\mathcal L_{ds}$ 从平均改成对全部匹配求和后，不能原样沿用系数 5。

### 4.4 训练图像与点是如何采样的

作者使用 MegaDepth 的透视图像对，以及 Oxford/Paris/Aachen 等数据上的合成单应与风格变化图像对。训练图像为 $800\times800$，batch size 为 2，累积 6 批梯度；先检测 400 点，再随机采样 400 点并进行 NMS。这让网络有机会学习尚未被高分检测器偏爱的区域，减少“只训练当前已经会检测的点”的闭环。

最终的 ALIKED-T(16)、N(16)、N(32) 中，T/N 表示骨干规模，括号数字是支持采样位置数 $M$，不是描述子维度。选择配置时必须同时看这些因素。

## 5. 实验：把更准、更鲁棒和更快分别验证

### 5.1 先分清特征匹配与重建指标

MMA 衡量保留匹配中有多少落在给定像素误差内；匹配分数还与可匹配关键点数量有关；单应估计准确度经过 RANSAC 等后处理，衡量整对图像几何能否恢复。严格像素门限下的收益更能体现定位精度，宽松门限不充分说明亚像素优势。

原论文主要使用 mutual nearest neighbor 匹配，以观察特征本身的表现。若替换为 LightGlue，得到的是联合系统性能，不能拿来直接归因于 SDDH。

<!-- vision-figure: aliked-4 -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-4.webp" width="1729" height="1432" alt="ALIKED 原论文 Figure 4：IMW 验证集的双视匹配与多视重建。正确匹配按误差由绿到黄，错误为红；重建覆盖与匹配精度应分开看。" loading="lazy" /></a>
  <figcaption>ALIKED 原论文 Figure 4 · IMW 验证集的双视匹配与多视重建。正确匹配按误差由绿到黄，错误为红；重建覆盖与匹配精度应分开看。 <a href="https://arxiv.org/pdf/2304.03608v2#page=9" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 4 的每种方法同时展示 IMW 场景中的立体匹配和多视图重建。先看正确连线是否分布在不同结构，再看重建是否覆盖相应区域。连线更多、注册图像更多和三维误差更低并不等价；重建还受视差、几何验证与相机注册影响。

<!-- vision-figure: aliked-5 -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-5.webp" width="861" height="294" alt="ALIKED 原论文 Figure 5：纹理分布不均的失败例。即使局部匹配较多，点集中在有限区域也会损害对极几何估计。" loading="lazy" /></a>
  <figcaption>ALIKED 原论文 Figure 5 · 纹理分布不均的失败例。即使局部匹配较多，点集中在有限区域也会损害对极几何估计。 <a href="https://arxiv.org/pdf/2304.03608v2#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 5 专门暴露另一种失败：纹理集中在局部，匹配容易沿特定方向分布，估计的极线几何可能不可靠。这说明点检测得准与点分布得好是两项条件。系统中仍有必要限制网格内点数、检查内点覆盖范围，而不是只验收一个内点总数。

### 5.2 单独改变旋转和尺度，观察鲁棒性边界

<!-- vision-figure: aliked-6 -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-6.webp" width="861" height="788" alt="ALIKED 原论文 Figure 6：旋转角度与尺度差异增加时的匹配精度。可变形支持区域提升部分鲁棒性，但曲线仍会下降。" loading="lazy" /></a>
  <figcaption>ALIKED 原论文 Figure 6 · 旋转角度与尺度差异增加时的匹配精度。可变形支持区域提升部分鲁棒性，但曲线仍会下降。 <a href="https://arxiv.org/pdf/2304.03608v2#page=11" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 6 的上图改变平面内旋转角，下图改变尺度差异。可变形描述头对旋转很有帮助，但尺度差继续扩大时，单尺度方法仍明显下降；多尺度 R2D2 是另一条增加计算的参照。不能把“旋转图表现好”扩展成任意透视和尺度变化下都稳定。

这也解释了学习采样的上限：输出偏移来自有限感受野，输入特征中已经丢失的细节无法凭采样重新生成。

### 5.3 消融与支持区域可视化，要分别读

论文的消融表逐步比较普通描述头、稀疏固定采样头和 SDDH，并改变核大小与支持点数。要检查收益究竟来自网络规模、检测质量，还是可变形支持区域本身。

<!-- vision-figure: aliked-7 -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-7.webp" width="1729" height="862" alt="ALIKED 原论文 Figure 7：旋转、尺度、单应与透视变换下的采样位置和有效关注区域。蓝色为关键点、红色为支持位置、绿色为影响区域。" loading="lazy" /></a>
  <figcaption>ALIKED 原论文 Figure 7 · 旋转、尺度、单应与透视变换下的采样位置和有效关注区域。蓝色为关键点、红色为支持位置、绿色为影响区域。 <a href="https://arxiv.org/pdf/2304.03608v2#page=12" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 7 不是消融曲线，而是旋转、缩放、单应和透视变化下的支持区域：绿色区域展示某个描述子读取或影响的局部证据。比较成对区域是否随对象结构改变，有助于理解“采样跟着内容移动”；但它没有证明每个支持点都是真实物理点的精确对应。

论文选择 $K=3,M=16$ 作为一组速度与精度折中，再用 $M=32$ 增强较大模型。增大 $M$ 能收集更多证据，也增加采样和聚合成本。若把 $N$ 从 1000 提高到 8000，SDDH 的成本会随关键点数增长；“只算稀疏点”不代表点数任意增加都免费。

表 III 将密集描述头成本与 $HW$ 联系起来，而稀疏头的采样、偏移和融合与 $NM$ 联系起来。实际延迟还受 grid sampling 的访存、算子支持和硬件影响，FLOPs 低不自动等于手机端更快。

### 5.4 最应该保留的一张失败图

<!-- vision-figure: aliked-8 -->
<figure>
  <a href="/HomepageX/media/aliked/aliked-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/aliked/aliked-8.webp" width="861" height="391" alt="ALIKED 原论文 Figure 8：尺度和视角同时剧变的困难样例。可变形描述子仍有限，增加匹配器或多尺度策略属于额外能力。" loading="lazy" /></a>
  <figcaption>ALIKED 原论文 Figure 8 · 尺度和视角同时剧变的困难样例。可变形描述子仍有限，增加匹配器或多尺度策略属于额外能力。 <a href="https://arxiv.org/pdf/2304.03608v2#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 8 同时存在大尺度和大视角变化。ALIKED 虽能恢复部分对应，仍出现大量困难区域；论文也指出只用一层偏移估计，对复杂变形的表达能力有限。多尺度搜索和学习匹配器可能补救，但它们增加的是额外系统能力，不能说原来的单尺度描述子已经解决了问题。

此外，32 位浮点描述子与 grid sampling 对部分移动设备并不友好。部署前应实测端到端耗时、显存、线程同步和不同点数下的延迟分布，而不只摘取论文中最快的单模块时间。

## 6. ALIKED、SuperPoint 与 LET-NET 应该怎么选

| 需求 | 核心输出与使用方式 | 更应关注的条件 |
| --- | --- | --- |
| 宽基线独立特征匹配 | ALIKED/SuperPoint 的稀疏点与描述子 | 重复性、精确定位、描述区分性、匹配器兼容 |
| 相邻帧低成本跟踪 | LET-NET 的连续三通道特征场与 LK | 初值、局部收敛域、光照变化、金字塔 |
| 大规模地点候选搜索 | 全局 VPR 描述子 | 检索召回、数据库规模、季节与视角 |

ALIKED 描述子可按图像独立缓存，适合重定位中的候选图局部匹配；它本身不输出回环约束，也不替代几何验证。把它接到 [SuperGlue/LightGlue](/HomepageX/blog/sparse-feature-and-visual-recognition/superglue-lightglue/) 或 SLAM 时，还要选择与该特征训练兼容的匹配模型，并确认坐标归一化、图像缩放和描述维度。

这篇工作的可迁移启发是：当最终只需要少量输出时，可以保留共享密集表征，把昂贵任务头移到真正要使用的位置；当固定邻域难以适应输入变化时，可以让网络学习证据的读取位置，同时用几何监督约束最终任务。

## 参考资料

- [ALIKED 论文 v2](https://arxiv.org/abs/2304.03608v2)、[作者代码固定版本](https://github.com/Shiaoming/ALIKED/tree/683d7c65197395c0b3f01ebe76e1084a27e73a65)。
- [ALIKE 作者仓库](https://github.com/Shiaoming/ALIKE)。
- [Neural Reprojection Error，CVPR 2021](https://openaccess.thecvf.com/content/CVPR2021/html/Germain_Neural_Reprojection_Error_Merging_Feature_Learning_and_Camera_Pose_Estimation_CVPR_2021_paper.html)。
