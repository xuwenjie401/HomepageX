---
title: "LET-NET 与 LET-NET2：让网络学习一个更适合 Lucas–Kanade 的世界"
description: "从亮度一致性失效、局部特征学习到可微 LK，结合论文与作者代码拆解监督、损失、收敛域和部署边界。"
date: 2026-09-26
tags: [论文精读, 光流, 特征跟踪, 视觉里程计]
---

相机从阴影走到阳光下，同一块墙的亮度变了，位置却没有突然跳走。经典 LK 通过比较局部图块估计位移；当它把曝光变化误认成运动，窗口再大、迭代再多，也可能只是在更认真地求解一个错误目标。

LET-NET 的思路很具体：**保留轻量的局部优化器，学习它要比较的图像表示**。LET-NET2 进一步让训练目标直接看 LK 最后追到了哪里。前者主要塑造特征与角点，后者尝试把优化器本身接进训练链路。

> LET-NET 以 [Breaking of brightness consistency in optical flow with a lightweight CNN network，arXiv:2310.15655v1](https://arxiv.org/abs/2310.15655v1) 为准；LET-NET2 以[作者仓库](https://github.com/linyicheng1/LET-NET2/tree/4713802d256ecf3bb463837e80b9d3d0ccba5a1a)为准。后者按代码解析，不假定存在另一篇同名论文。这里的阅读日期是 2026 年 9 月 26 日。

## 1. LK 的问题究竟出在哪里

### 1.1 正确位置也可能有很大的灰度误差

设第一幅图为 $I_A$，第二幅为 $I_B$，窗口中心为 $\mathbf p$，待估位移为 $\mathbf u$。经典目标是

$$
E_I(\mathbf u)=\frac12\sum_{\mathbf q\in\Omega(\mathbf p)}[I_B(\mathbf q+\mathbf u)-I_A(\mathbf q)]^2.
$$

若真实关系为 $I_B(\mathbf q+\mathbf u^*)=aI_A(\mathbf q)+b$，那么即使 $\mathbf u=\mathbf u^*$，残差仍是 $(a-1)I_A+b$。图像梯度会把这些亮度残差投影成一个错误的更新方向。局部增益、偏置模型能补偿部分变化，但空间不均匀的光照、饱和与模糊超出了两个参数能表达的范围。

<!-- vision-figure: let-illumination -->
<figure>
  <a href="/HomepageX/media/letnet/let-illumination.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/letnet/let-illumination.svg" width="1100" height="470" alt="自制图 1：同一条边在增益和偏置变化后的强度曲线，说明光度误差并不只由运动造成。" loading="lazy" /></a>
  <figcaption>自制图 1 · 同一条边在增益和偏置变化后的强度曲线，说明光度误差并不只由运动造成。</figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: letnet-1 -->
<figure>
  <a href="/HomepageX/media/letnet/letnet-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/letnet/letnet-1.webp" width="841" height="623" alt="LET-NET 原论文 Figure 1：亮度变化下灰度 LK 与学习特征跟踪的对比。关注光照变化处的跟踪失效，而不只是角点数量。" loading="lazy" /></a>
  <figcaption>LET-NET 原论文 Figure 1 · 亮度变化下灰度 LK 与学习特征跟踪的对比。关注光照变化处的跟踪失效，而不只是角点数量。 <a href="https://arxiv.org/pdf/2310.15655v1#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

原论文 Figure 1 应比较同一场景在剧烈亮度变化下的跟踪行为，而不是只数最终图中有多少彩点。多保留错误跟踪点，反而会伤害后端。

### 1.2 把残差换到学习的三通道空间

网络输出 $F_\theta(I)\in\mathbb R^{H\times W\times C}$。LET-NET 使用很低的通道数 $C=3$，随后优化

$$
E_F(\mathbf u)=\frac12\sum_{\mathbf q\in\Omega}\sum_{c=1}^{C}
[F_{B,c}(\mathbf q+\mathbf u)-F_{A,c}(\mathbf q)]^2.
$$

记残差为 $r_{qc}$，目标特征的空间梯度为 $\mathbf J_{qc}=[\partial_xF_{B,c},\partial_yF_{B,c}]$，一次 Gauss–Newton 更新满足

$$
\left(\sum_{q,c}\mathbf J_{qc}^{\mathsf T}\mathbf J_{qc}\right)\Delta\mathbf u
=-\sum_{q,c}\mathbf J_{qc}^{\mathsf T}r_{qc}.
$$

这与 [GFTT/KLT 篇](/HomepageX/blog/sparse-feature-and-visual-recognition/gftt-klt-sift/)的结构完全相同，只是每个像素提供三组残差与梯度。三通道不是三个位移：同一个二维 $\Delta\mathbf u$ 必须同时解释所有通道。

原论文的式 (5) 已经把右端定义成负时间差，式 (6) 又出现额外负号；本文使用上面的残差定义统一符号，避免照抄时得到反方向更新。实际实现也应对一个已知平移图块做符号检查。

### 1.3 学到“不变”还不够，必须保留可定位的变化

假如所有像素都输出相同向量，那么任意两幅图的特征误差都为零，看起来完美满足一致性；但空间梯度也为零，$\mathbf J^{\mathsf T}\mathbf J$ 无法确定运动。

理想表示必须同时具有两种性质：同一物理位置在光照变化下相近；相邻但不同的位置仍有足够、方向丰富的变化。因此真正要学的不是把图像变平，而是把**不相关的光度变化压下去，把可用于定位的空间结构留下来**。后面所有监督，都要围绕这个矛盾理解。

<!-- vision-figure: let-landscape -->
<figure>
  <a href="/HomepageX/media/letnet/let-landscape.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/letnet/let-landscape.svg" width="1100" height="470" alt="自制图 2：二次代价与常量特征的教学对比：让所有对应相似并不足够，还要防止失去定位梯度。" loading="lazy" /></a>
  <figcaption>自制图 2 · 二次代价与常量特征的教学对比：让所有对应相似并不足够，还要防止失去定位梯度。</figcaption>
</figure>
<!-- /vision-figure -->

## 2. LET-NET：轻推理网络与重训练监督分开

### 2.1 网络究竟输出什么

论文的推理网络保持原分辨率：两层 $3\times3$ 卷积提取 8 通道特征，接 $1\times1$ 卷积扩到 16 通道，最后一层 $1\times1$ 输出四个通道。三个通道构成经过 $L_2$ 归一化的局部跟踪特征，一个通道经 sigmoid 得到角点分数 $S$。

这不是 SuperPoint 式的高维稀疏描述子查找。LET-NET 的三通道特征形成整张连续场，LK 在它上面取窗口、算梯度、迭代。它为相邻帧的小范围搜索服务，不承担全地图检索。

<!-- vision-figure: letnet-2 -->
<figure>
  <a href="/HomepageX/media/letnet/letnet-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/letnet/letnet-2.webp" width="1697" height="492" alt="LET-NET 原论文 Figure 2：浅网络分别产生跟踪特征和角点分数；金字塔 LK 与前后向检查在网络输出后执行。" loading="lazy" /></a>
  <figcaption>LET-NET 原论文 Figure 2 · 浅网络分别产生跟踪特征和角点分数；金字塔 LK 与前后向检查在网络输出后执行。 <a href="https://arxiv.org/pdf/2310.15655v1#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 2 中应分清两条路径：分数图经过 NMS、阈值与最小间距筛点；特征图构建金字塔并进行光流。前后向检查验证跟踪一致性。网络只生成输入表示，最终位移来自优化器。

### 2.2 为什么训练时需要额外的深网络

浅网络有利于 CPU 部署，却不容易单靠三个通道判断“这个角点在整张图中是否可靠”。作者在训练时引入 VGG 风格、多尺度的深描述网络，以高维描述的可区分性监督角点可靠性；推理时移除这部分。

<!-- vision-figure: letnet-3 -->
<figure>
  <a href="/HomepageX/media/letnet/letnet-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/letnet/letnet-3.webp" width="1697" height="607" alt="LET-NET 原论文 Figure 3：训练时的深描述分支提供可靠性监督，推理移除；它与浅三通道跟踪特征的职责不同。" loading="lazy" /></a>
  <figcaption>LET-NET 原论文 Figure 3 · 训练时的深描述分支提供可靠性监督，推理移除；它与浅三通道跟踪特征的职责不同。 <a href="https://arxiv.org/pdf/2310.15655v1#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 3 的深分支不应计入部署时的网络成本，也不能把训练图误读成教师输出直接蒸馏到三通道特征的逐元素回归。论文把高维描述用于可靠性学习，把浅特征用于局部一致性学习，两者职责不同。

## 3. 四类训练约束怎样一起作用

### 3.1 几何重投影：两个角点必须指向同一位置

训练用 MegaDepth 的相机、深度建立映射 $w_{AB}$。若可见点 $\mathbf p_A$ 投到 $\mathbf p_{AB}=w_{AB}(\mathbf p_A)$，其近邻检测点为 $\mathbf p_B$，可对双向位置误差求平均：

$$
\ell_{rp}=\frac12\left(\|w_{AB}(\mathbf p_A)-\mathbf p_B\|+
\|w_{BA}(\mathbf p_B)-\mathbf p_A\|\right).
$$

必须先限定可见性、有效深度和配对阈值；“找最近点”不意味着它在物理上一定对应。梯度经局部可微坐标回到分数图，促使两幅图的峰值在几何变换后重合。

### 3.2 Line peaky loss：别让角点长成一条亮线

普通峰值损失会压缩峰周围的分数质量，但直边上许多位置都可能同样好。作者对水平、竖直和两条对角线分别加权，取损失最大的方向进行压制。

在 $N\times N$ 窗口内，峰坐标为 $(\hat i,\hat j)$，四种权重分别是到四条过峰直线的距离经过高斯函数后的值，例如

$$
w_1(i,j)=G(|i-\hat i|),\qquad
w_3(i,j)=G(|i+j-\hat i-\hat j|).
$$

其核心形式为

$$
\ell_{line}=\frac1{N^2}\max_{k\in\{1,2,3,4\}}
\sum_{i,j}w_k(i,j)\,d(i,j)\,s(i,j).
$$

这里 $d$ 是像素距峰位置的距离，$s$ 是窗口分数。若高分沿水平线延伸，过该线的权重会保留较多远离峰的质量，最大项就把这条“脊”暴露出来。它只检查四个方向，是低成本约束，不是对所有边缘方向的解析保证。

<!-- vision-figure: letnet-4 -->
<figure>
  <a href="/HomepageX/media/letnet/letnet-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/letnet/letnet-4.webp" width="842" height="257" alt="LET-NET 原论文 Figure 4：直线形高响应与峰状响应的区别。line peaky 约束针对沿边缘延伸的分数脊，而不是任意提高分数。" loading="lazy" /></a>
  <figcaption>LET-NET 原论文 Figure 4 · 直线形高响应与峰状响应的区别。line peaky 约束针对沿边缘延伸的分数脊，而不是任意提高分数。 <a href="https://arxiv.org/pdf/2310.15655v1#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

### 3.3 可靠性：能重复检测，也要容易区分

可靠性 $r_i$ 由深描述分支的匹配概率提供。论文使用双图分数乘积 $a_i=S_A(\mathbf p_i)S_B(w_{AB}(\mathbf p_i))$，其单向形式可写成

$$
\mathcal L^A_{rel}=\frac1{N_A}\sum_i
\frac{a_i}{\sum_j a_j}(1-r_i).
$$

双向平均得到总可靠性项。归一化权重促使高可靠点占据更多分数质量。假设两个点 $r=(0.9,0.2)$，把归一化分数从 $(0.5,0.5)$ 改成 $(0.8,0.2)$，括号内加权代价从 $0.45$ 变成 $0.24$；还要保留论文外面的点数归一化，才能复现数值尺度。

这个损失主要决定“把分数给谁”，并不单独保证每张图都有足够、分布均匀的角点；几何与峰值约束、推理筛点共同承担这个责任。

### 3.4 Masked NRE：让三通道完成局部区分任务

标准 Neural Reprojection Error 把描述匹配变成概率预测，并在真实对应位置施加负对数损失。LET-NET 用局部 mask 限制训练关注的范围，让小网络优先学习 LK 所需的局部不变性，而不强迫三个通道区分整幅图所有重复结构。

令几何真值为 $\mathbf p_{AB}$，匹配概率为 $q_m(\mathbf q\mid\mathbf d_A,F_B)$。最容易理解的概率版本，是在局部候选集合 $\mathcal N$ 内归一化相似度，再计算

$$
q_{\mathcal N}(\mathbf q)=
\frac{\exp(s(\mathbf d_A,F_B(\mathbf q))/\tau)}
{\sum_{\mathbf v\in\mathcal N}\exp(s(\mathbf d_A,F_B(\mathbf v))/\tau)},
\qquad \ell=-\log q_{\mathcal N}(\mathbf p_{AB}).
$$

这是解释“局部竞争”的规范化写法。原论文式 (13)–(15) 把 mask 写在 $q_m$ 外侧，符号对 mask 中心和归一化细节交代得较简略；不能据此把上式声称为逐字符相同的实现。复现时要核对实际训练代码中 mask 是在 softmax 前屏蔽候选，还是在之后选择损失元素。两者对负样本和概率总和的影响不同。

原版 LET-NET 这些损失塑造角点与特征，**论文训练目标并没有把最终 LK 迭代结果的位移误差直接作为主监督**。这正是理解 LET-NET2 的入口。

## 4. LET-NET2：通过求解器监督特征

### 4.1 先用 TartanAir 构造稀疏运动真值

仓库的数据类首先用 GFTT 在第一帧取点，再用深度与相对相机位姿重投影到第二帧。设 $T_{BA}$ 把 A 相机坐标变到 B，深度为相机轴向 $Z$，则

$$
\mathbf p_B^*=\pi\left(K_B\begin{bmatrix}I_3&0\end{bmatrix}T_{BA}
\begin{bmatrix}Z_AK_A^{-1}\tilde{\mathbf p}_A\\1\end{bmatrix}\right),
\qquad \mathbf u^*=\mathbf p_B^*-\mathbf p_A.
$$

式中 $[I_3\;0]$ 取出三维坐标，$\pi$ 完成投影除法；在实际实现中更常把 $T$ 分成 $R,t$。深度类型、相机轴方向、缩放后内参必须一致，详见 [TartanAir 篇](/HomepageX/blog/sparse-feature-and-visual-recognition/tartanair/)。该仓库投影函数主要检查有效深度、正向深度和图像边界；这些条件不能替代第二帧深度一致性的遮挡检验。

### 4.2 内层求位移，外层改网络

把三通道特征送进 `SparseLucasKanadeFlow`。代码按点、窗口像素、通道组织残差，用 Theseus 的 Levenberg–Marquardt 迭代。将有限次求解记作 $\Phi_K$：

$$
\widehat{\mathbf u}=\Phi_K(F_\theta(I_A),F_\theta(I_B),\mathbf u_0),
\qquad
\mathcal L_{flow}=
\frac{\sum_{i,d}m_i(\widehat u_{id}-u^*_{id})^2}
{2\sum_i m_i+\epsilon}.
$$

$m_i\in\{0,1\}$ 表示有效点，$d$ 遍历横纵两个分量；这是代码中 `MSELoss(reduction='none')` 加 mask 的平均方式。一个点的预测误差为 $(2,0)$ 像素，贡献的平均平方误差是 $2$，单位为像素平方，而端点误差是 $2$ 像素，两者不可混写。

<!-- vision-figure: let-unroll -->
<figure>
  <a href="/HomepageX/media/letnet/let-unroll.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/letnet/let-unroll.svg" width="1100" height="470" alt="自制图 3：有限步优化的教学展开：红点逐步接近局部极小值，外层监督最终坐标；图不声称每次真实 LM 都采用该步长。" loading="lazy" /></a>
  <figcaption>自制图 3 · 有限步优化的教学展开：红点逐步接近局部极小值，外层监督最终坐标；图不声称每次真实 LM 都采用该步长。</figcaption>
</figure>
<!-- /vision-figure -->

若使用最优解的隐式表达 $\nabla_uE(u^*,\theta)=0$，有

$$
\frac{\partial u^*}{\partial\theta}=
-\left(\frac{\partial^2E}{\partial u^2}\right)^{-1}
\frac{\partial^2E}{\partial u\partial\theta}.
$$

它解释了为什么外层位移误差能要求网络改变局部误差曲面。但这个推导假设平滑、局部解稳定和 Hessian 可逆；有限步展开优化是另一种求导路径，不能把二者当作无条件等价。仓库通过可微求解层构图，具体反传行为还取决于 Theseus 版本与求导配置。

### 4.3 最关键的细节：训练从真值附近出发

固定版本 `train.py` 实际启用的调用是

$$
\mathbf u_0=\mathbf u^*+\boldsymbol\epsilon,
\qquad \boldsymbol\epsilon\sim\mathcal N(0,2^2I)
$$

，随后在原尺度运行 LK。代码中的两级粗尺度调用被注释掉了。这相当于训练“如何把真值附近的扰动拉回来”，并不等价于训练“从零位移解决任意大运动”。

因此即使训练误差很低，也应在推理时分别测试不同初值误差半径、金字塔层数、位移大小和曝光变化。网络可能学出了一个很好的局部吸引域，却没有让吸引域覆盖几十像素的快速运动。

<!-- vision-figure: let-basin -->
<figure>
  <a href="/HomepageX/media/letnet/let-basin.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/letnet/let-basin.svg" width="1100" height="470" alt="自制图 4：示意多极小值目标与局部初始化范围。LET-NET2 固定训练代码使用真值加标准差 2 像素的噪声，不能据此证明任意大运动可收敛。" loading="lazy" /></a>
  <figcaption>自制图 4 · 示意多极小值目标与局部初始化范围。LET-NET2 固定训练代码使用真值加标准差 2 像素的噪声，不能据此证明任意大运动可收敛。</figcaption>
</figure>
<!-- /vision-figure -->

### 4.4 仓库写了某项 loss，不代表训练使用它

在固定版本中，`orth_loss` 计算 $\|J^{\mathsf T}J-I\|^2$ 并乘 $0.01$，`nll_loss` 也被计算；但最后赋值是 `loss = flow_loss`，不确定度项处于注释中，正交项也未加入总损失。因此本文不会把这两项写成该版本已经训练成功的机制。

`model.py` 也与原论文不同：最后卷积输出 **3 个通道**，三个都经 sigmoid 构成特征，最后一个通道同时乘 10 当作 `score_map`。这不是独立四通道头，也不是原版的单位长度特征。由于主损失只监督光流，不能把这个 `score_map` 宣称为经过 NLL 校准的不确定度预测。

另一个实现细节是 `lk.py` 用 Sobel 滤波近似空间 Jacobian，并显式构造各点互不耦合的块对角结构，但以大矩阵张量存放。数学上每个点只有二维未知量，通用实现的内存开销不代表稀疏 LK 本身必须如此昂贵。部署实现可以逐点求解，训练实现则需同时考虑自动微分开销。

这些差异都能在[固定版本训练代码](https://github.com/linyicheng1/LET-NET2/blob/4713802d256ecf3bb463837e80b9d3d0ccba5a1a/train.py)与[模型代码](https://github.com/linyicheng1/LET-NET2/blob/4713802d256ecf3bb463837e80b9d3d0ccba5a1a/model.py)中核对。本文未运行完整训练，也不把作者演示视频当作统一数据集上的对照实验。

## 5. 实验怎样支持原版 LET-NET 的主张

### 5.1 重复率不等于完整跟踪能力

论文 HPatches 对比用 300 点、$240\times320$ 分辨率、3 像素重复阈值及统一 NMS。LET-NET 的光照/视角重复率分别是 $0.618/0.606$；SuperPoint 为 $0.652/0.503$，ALIKE(T) 为 $0.638/0.563$。它在这组设置下的视角重复率较好，光照重复率却没有超过二者，不能笼统写成所有重复性指标领先。

CPU 时间表给 LET-NET 5.2 ms、SuperPoint 93.5 ms、ALIKE(T) 84.4 ms；学习方法在较小图上算分数后上采样，传统方法的检测分辨率不同。这组数说明作者实现的轻量性，不能直接当作任意平台、任意端到端系统的速度比例。

### 5.2 光照变化、运动模糊与系统收益

<!-- vision-figure: letnet-5 -->
<figure>
  <a href="/HomepageX/media/letnet/letnet-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/letnet/letnet-5.webp" width="841" height="641" alt="LET-NET 原论文 Figure 5：室内、室外、主动光源和散射模糊的测试图像。饱和造成的信息丢失仍不能靠不变性恢复。" loading="lazy" /></a>
  <figcaption>LET-NET 原论文 Figure 5 · 室内、室外、主动光源和散射模糊的测试图像。饱和造成的信息丢失仍不能靠不变性恢复。 <a href="https://arxiv.org/pdf/2310.15655v1#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: letnet-6 -->
<figure>
  <a href="/HomepageX/media/letnet/letnet-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/letnet/letnet-6.webp" width="842" height="625" alt="LET-NET 原论文 Figure 6：跟踪存活比例随序列推进变化，并附帧示例。长期保留的点还应通过几何检查，存活比例不是单独的正确率。" loading="lazy" /></a>
  <figcaption>LET-NET 原论文 Figure 6 · 跟踪存活比例随序列推进变化，并附帧示例。长期保留的点还应通过几何检查，存活比例不是单独的正确率。 <a href="https://arxiv.org/pdf/2310.15655v1#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 5 给出室内光源变化、主动光源、室外照明和散射模糊的测试情形；Figure 6 用跟踪结果检查学习特征能否减少亮度假设失效。看图时需同时看存活点位置、错误连线和纹理分布。完全过曝区域丢失的信息，任何不变性表示都不能恢复。

<!-- vision-figure: letnet-7 -->
<figure>
  <a href="/HomepageX/media/letnet/letnet-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/letnet/letnet-7.webp" width="841" height="572" alt="LET-NET 原论文 Figure 7：在 VINS-Mono 中更换前端后的 HDR 轨迹。系统结果同时受跟踪、外点和后端影响，不等于单个损失的因果消融。" loading="lazy" /></a>
  <figcaption>LET-NET 原论文 Figure 7 · 在 VINS-Mono 中更换前端后的 HDR 轨迹。系统结果同时受跟踪、外点和后端影响，不等于单个损失的因果消融。 <a href="https://arxiv.org/pdf/2310.15655v1#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 7 把前端放入 VIO 后比较轨迹，回答“收益能否传到系统”。它并不能把全部误差改善归因于某一种损失，因为筛点、可跟踪性、外点比例和后端的相互作用都影响结果。公平复现应固定后端参数、IMU 数据、相机标定和关键帧策略，再更换前端。

## 6. 怎样把这条思路接入自己的 VO/VIO

一个稳妥的验证顺序是：先固定几何变换和可见性，测端点误差随初值偏差的曲线；再加入曝光、局部光源与模糊，检查误差曲面有没有额外极小值；最后跑闭环前的长轨迹，分别报告跟踪时间、内点数、失败次数与轨迹误差。

推理时仍需要金字塔、前后向检查、边界与纹理退化检查、几何 RANSAC，以及必要的重新检测。对三通道特征检查 $\lambda_{\min}(J^{\mathsf T}J)$，仍然是理解局部可观性的好方法。学习特征不能取消孔径问题，只能在有信息的输入中更合理地组织梯度。

LET-NET 最有启发性的地方，是把“学习”和“优化”放在不同位置：网络可以只学习残差的材料，也可以进一步学习让求解过程得到正确答案。后一种训练更贴近任务，却更依赖初始化分布、求解器实现和训练数据的几何质量。

## 参考资料

- [LET-NET 原论文](https://arxiv.org/abs/2310.15655v1)、[推理仓库](https://github.com/linyicheng1/LET-NET)、[训练仓库](https://github.com/linyicheng1/LET-NET-Train)。
- [LET-NET2 固定代码版本](https://github.com/linyicheng1/LET-NET2/tree/4713802d256ecf3bb463837e80b9d3d0ccba5a1a)。
- [TartanAir](https://arxiv.org/abs/2003.14338v2)、[ALIKE](https://github.com/Shiaoming/ALIKE)。
