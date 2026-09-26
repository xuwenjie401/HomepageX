---
title: "从 GFTT、KLT 到 SIFT：一个点为什么能被追踪，又怎样被重新认出"
description: "从亮度残差推导结构张量和光流更新，理解尺度、方向、128 维描述子与比值检验，并分清短时跟踪与跨视角匹配。"
date: 2026-09-26
tags: [论文精读, 局部特征, 光流, 计算机视觉]
---

相机沿着书桌向右移动，上一帧的书角在下一帧向左走了几像素。此时我们有一个很强的线索：它应该还在附近。隔天重新拍摄同一张桌子，书变小了、照片转了一个角度，这个线索却不再可靠。

这两种场景对应两种不同的问题：**跟踪，是利用时间连续性继续找一个已知点；匹配，是在不确定它在哪里的情况下重新认出它。** GFTT 选择适合跟踪的点，KLT 求这些点的短时运动，SIFT 则通过尺度、方向和描述子支持更大范围的重新识别。它们不是必须首尾相接的三个网络层。

本文与 [SuperPoint 精读](/HomepageX/blog/sparse-feature-and-visual-recognition/superpoint/)互相补充。先从经典方法看清“什么叫好点”，再看学习方法究竟改变了哪里。

> 主要来源：[Shi–Tomasi，Good Features to Track，CVPR 1994](https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf)、[Lucas–Kanade，1981](https://www.ri.cmu.edu/pub_files/pub3/lucas_bruce_d_1981_2/lucas_bruce_d_1981_2.pdf)、[Lowe，SIFT，IJCV 2004 作者稿](https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf)。下文的离散矩阵形式为方便实现而重写。

## 1. 不妨先写出“找对了”的标准

### 1.1 一个点没有足够的信息，一小块图像才有

设两帧灰度图为 $I_1,I_2$，关键点中心为 $\mathbf p$，窗口里的相对坐标为 $\mathbf q$。假设小窗口内所有像素共同平移 $\mathbf d=(d_x,d_y)^\top$，并暂时假设曝光和表面外观没有变化。正确位移应该让对应像素接近：

$$
I_2(\mathbf p+\mathbf q+\mathbf d)\approx I_1(\mathbf p+\mathbf q).
$$

于是定义加权平方误差：

$$
E(\mathbf d)=\frac12\sum_{\mathbf q\in\Omega}w_{\mathbf q}
\left[I_2(\mathbf p+\mathbf q+\mathbf d)-I_1(\mathbf p+\mathbf q)\right]^2.
$$

$\mathbf d$ 的单位是像素，灰度可以用 $[0,1]$ 或 $[0,255]$，但阈值必须相应变化。$w_{\mathbf q}\ge0$ 用来强调中心区域。窗口大能增加测量，也更容易同时包含书本和背景两个不同深度；这时“共同平移”可能已经错了。

对于白墙，很多位移都能让误差很小。对于直边，沿边移动仍然很像。只有局部图案在两个方向都变化时，误差才有机会把两个位移分量都约束住。

<!-- vision-figure: gftt-conditioning -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/gftt-conditioning.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/gftt-conditioning.svg" width="1100" height="470" alt="自制图 1：按二次误差计算的等高线。平坦区两方向都不确定，直边有长而窄的谷，角点形成可定位的盆地。" loading="lazy" /></a>
  <figcaption>自制图 1 · 按二次误差计算的等高线。平坦区两方向都不确定，直边有长而窄的谷，角点形成可定位的盆地。</figcaption>
</figure>
<!-- /vision-figure -->

### 1.2 KLT 并不是把所有候选位置暴力试一遍

在当前估计 $\mathbf d_k$ 附近，令

$$
r_{\mathbf q}=I_2(\mathbf p+\mathbf q+\mathbf d_k)-I_1(\mathbf p+\mathbf q),\qquad
\mathbf g_{\mathbf q}=\nabla I_2(\mathbf p+\mathbf q+\mathbf d_k).
$$

对小增量 $\Delta\mathbf d$ 作一阶近似：

$$
r_{\mathbf q}(\mathbf d_k+\Delta\mathbf d)
\approx r_{\mathbf q}+\mathbf g_{\mathbf q}^{\top}\Delta\mathbf d.
$$

对近似误差求导并令其为零，得到 Gauss–Newton 正规方程：

$$
\underbrace{\sum_{\mathbf q}w_{\mathbf q}\mathbf g_{\mathbf q}\mathbf g_{\mathbf q}^{\top}}_{G}
\Delta\mathbf d
=-\underbrace{\sum_{\mathbf q}w_{\mathbf q}\mathbf g_{\mathbf q}r_{\mathbf q}}_{\mathbf b},
\qquad
\mathbf d_{k+1}=\mathbf d_k+\Delta\mathbf d.
$$

实际程序解这个 $2\times2$ 线性系统，不必显式计算逆矩阵。更新后重新采样和线性化，直到增量足够小、达到迭代次数或跟踪被判无效。非整数坐标需要插值；不能把每次更新都取整，否则亚像素信息会被丢掉。

这里采用前向加法形式。固定模板梯度的逆向组合方法有不同的雅可比位置与更新规则；不能从两个推导各拿一半拼成实现。现代库常用金字塔和优化过的变体，“KLT”在工程里通常是这类稀疏 LK 跟踪器的简称。

<!-- vision-figure: lucas-kanade-1 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/lucas-kanade-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/lucas-kanade-1.webp" width="494" height="375" alt="Lucas–Kanade 原论文 Figure 1：两幅图像的局部位移关系，是迭代图像配准的起点。" loading="lazy" /></a>
  <figcaption>Lucas–Kanade 原论文 Figure 1 · 两幅图像的局部位移关系，是迭代图像配准的起点。 <a href="https://www.ri.cmu.edu/pub_files/pub3/lucas_bruce_d_1981_2/lucas_bruce_d_1981_2.pdf#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lucas-kanade-2 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/lucas-kanade-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/lucas-kanade-2.webp" width="480" height="366" alt="Lucas–Kanade 原论文 Figure 2：用局部梯度把强度差换算成位移修正，说明一阶近似的几何直觉。" loading="lazy" /></a>
  <figcaption>Lucas–Kanade 原论文 Figure 2 · 用局部梯度把强度差换算成位移修正，说明一阶近似的几何直觉。 <a href="https://www.ri.cmu.edu/pub_files/pub3/lucas_bruce_d_1981_2/lucas_bruce_d_1981_2.pdf#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Lucas–Kanade 原论文 Figure 1–2 将这种思想画成局部图像与一维函数：当前强度差除以局部斜率，可以得到一个位移修正。二维窗口把许多这样的测量联合起来，才得到上面的矩阵方程。在梯度很小、位移太大或对应不存在时，这个线性近似都不能独自保证正确。

## 2. GFTT：从方程里反推什么点值得跟

### 2.1 结构张量里的两个特征值在问什么

展开 $G$：

$$
G=\begin{bmatrix}
\sum w I_x^2&\sum w I_xI_y\\
\sum w I_xI_y&\sum w I_y^2
\end{bmatrix}.
$$

这个矩阵常称为结构张量、二阶矩矩阵。名字里的“二阶”来自一阶梯度的乘积，**它不是图像二阶导数组成的 Hessian**。对平方误差而言，$G=J^\top WJ$ 又确实是 Gauss–Newton 对 Hessian 的近似。这两种说法可以同时成立。

令 $G=Q\operatorname{diag}(\lambda_1,\lambda_2)Q^\top$，$\lambda_1\ge\lambda_2\ge0$。在特征向量方向上移动，误差的二次近似分别以 $\lambda_1,\lambda_2$ 的速度增长：

$$
E(\mathbf d_*+\boldsymbol\delta)-E(\mathbf d_*)
\approx\frac12\boldsymbol\delta^\top G\boldsymbol\delta.
$$

两个特征值小，意味着平坦；一个大一个小，意味着沿某方向有一条长谷；两个都大，才会形成能定位的碗。矩阵“可逆”只是最低条件，一个几乎奇异的矩阵仍会把噪声放大很多倍。

在独立同方差残差噪声、等权及局部线性模型下，位移协方差近似为

$$
\operatorname{Cov}(\widehat{\mathbf d})\approx\sigma_r^2G^{-1}.
$$

沿最弱方向的方差是 $\sigma_r^2/\lambda_2$。这就是 Shi–Tomasi 准则选择

$$
\lambda_{\min}(G)>\tau
$$

的直接理由：我们关心最不可靠的那个方向。一般加权时，只有把权重解释为正确的噪声精度，才能直接沿用相应加权逆信息矩阵的协方差解释。

### 2.2 代入一次，就看见边缘为什么不够

假设窗口内的三个梯度为 $(1,0),(0,1),(1,1)$，对应当前残差为 $-2,-1,-3$，权重都为 1。则

$$
G=\begin{bmatrix}2&1\\1&2\end{bmatrix},\quad
\mathbf b=\begin{bmatrix}-5\\-4\end{bmatrix},\quad
\Delta\mathbf d=\begin{bmatrix}2\\1\end{bmatrix}.
$$

三个线性化残差都变为零，且 $G$ 的特征值是 3 和 1。现在把梯度全部换成 $(1,0)$，则 $G=\operatorname{diag}(3,0)$；水平位移可以估计，垂直位移完全没有信息。多采一些同方向梯度，只会让 3 变大，不能补上那个零。

<!-- vision-figure: klt-update -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/klt-update.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/klt-update.svg" width="1100" height="470" alt="自制图 2：数值例子的正规方程：G 乘以 (2,1) 得到 (5,4)，更新方向由残差符号和梯度共同决定。" loading="lazy" /></a>
  <figcaption>自制图 2 · 数值例子的正规方程：G 乘以 (2,1) 得到 (5,4)，更新方向由残差符号和梯度共同决定。</figcaption>
</figure>
<!-- /vision-figure -->

这也是“检测更多点”未必改善运动估计的原因。如果所有点都来自同一条边、同一个小区域，增加的是重复约束。单点的 $G$ 良好，也不等于整个相机位姿问题良好：深度、视差、点的空间分布和运动方式还决定后端的可观测性。

### 2.3 选点分数、非极大抑制和间距是三个动作

GFTT 的核心是最小特征值评分。实际前端通常还要做局部非极大抑制、相对质量阈值、最小点间距和数量上限。相对阈值可写成 $s(\mathbf p)>\alpha\max s$；这里的 $\alpha$ 与原论文用来分析噪声的绝对 $\tau$ 不是同一个参数。

Harris 评分 $\det G-k(\operatorname{tr}G)^2$ 同样来自结构张量，但通过行列式和迹间接区分角点。GFTT 更直接地约束最弱方向。二者都不保证该点在世界中静止，也不保证在另一张图中独一无二。

## 3. KLT 能走多远：金字塔、监测与失败

### 3.1 金字塔是在扩大收敛范围

假设全分辨率位移为 24 像素。降采样三次后只剩 3 像素，更符合小增量线性化的前提。在粗层求得初值，再上采样位移并在细层修正：

$$
\mathbf d^{(\ell-1)}_0=2\mathbf d^{(\ell)}_{\mathrm{final}},\qquad
\mathbf d^{(\ell-1)}=\mathbf d^{(\ell-1)}_0+\Delta\mathbf d^{(\ell-1)}.
$$

倍率 2 对应相邻层图像缩小一半。尺度改变时，点坐标、窗口和相机参数的单位也要保持一致。金字塔没有把局部优化变成全局搜索：重复窗格会出现多个极小值，粗层也可能选错一个。

<!-- vision-figure: klt-pyramid -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/klt-pyramid.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/klt-pyramid.svg" width="1100" height="470" alt="自制图 3：教学示意：原图 12 像素位移在两次二倍下采样后为 3 像素，逐层放大估计并优化残差。" loading="lazy" /></a>
  <figcaption>自制图 3 · 教学示意：原图 12 像素位移在两次二倍下采样后为 3 像素，逐层放大估计并优化残差。</figcaption>
</figure>
<!-- /vision-figure -->

### 3.2 亮度一致性破坏时，优化可能很努力地走错

若第二帧仅发生 $I_2=aI_1+b$，真实几何位移处的亮度残差也可能很大。可以增加局部增益和偏置参数，或者用归一化图块、梯度、学习特征；代价是新增未知量或改变噪声模型。第 [7 篇 LET-NET](/HomepageX/blog/sparse-feature-and-visual-recognition/letnet/)会把这一问题继续展开。

遮挡更根本：点在下一帧已经看不见，任何优化器都无法恢复一个存在于图像中的正确观测。前后向检查是有用的拒绝机制：

$$
e_{\mathrm{FB}}=\left\|\operatorname{track}_{2\to1}\!\left(\operatorname{track}_{1\to2}(\mathbf p)\right)-\mathbf p\right\|_2.
$$

误差大说明不一致；误差小仍不能证明正确，因为重复纹理可能让两个方向一致地选错。几何 RANSAC 又增加一层检查，但只验证它所假设的场景与运动模型。

### 3.3 Shi–Tomasi 原论文不只贡献了一个角点分数

原论文强调相邻帧用平移跟踪，隔较久与初始模板比较时用仿射模型监测：

$$
E(A,\mathbf d)=\sum_{\mathbf q}w_{\mathbf q}
[I_t(A\mathbf q+\mathbf d)-I_0(\mathbf q)]^2.
$$

六个仿射参数能解释逐渐累积的缩放、剪切和旋转。若只用平移与初始模板比较，一个正确跟踪、但外形逐渐改变的点也会被误判。另一方面，增加仿射自由度不能解释真正的遮挡。

<!-- vision-figure: shi-tomasi-1 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-1.webp" width="829" height="210" alt="Shi–Tomasi 原论文 Figure 1：交通标志随相机接近而变化。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 1 · 交通标志随相机接近而变化。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: shi-tomasi-2 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-2.webp" width="829" height="312" alt="Shi–Tomasi 原论文 Figure 2：原图块与仿射校正后的图块。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 2 · 原图块与仿射校正后的图块。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: shi-tomasi-3 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-3.webp" width="850" height="637" alt="Shi–Tomasi 原论文 Figure 3：平移与仿射残差对正常形变和遮挡的反应。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 3 · 平移与仿射残差对正常形变和遮挡的反应。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: shi-tomasi-4 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-4.webp" width="850" height="199" alt="Shi–Tomasi 原论文 Figure 4：被逐步遮挡的背景窗口。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 4 · 被逐步遮挡的背景窗口。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: shi-tomasi-5 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-5.webp" width="850" height="325" alt="Shi–Tomasi 原论文 Figure 5：仿射对齐不能恢复已被遮挡的内容。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 5 · 仿射对齐不能恢复已被遮挡的内容。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 1–2 的交通标志逐渐变大，仿射对齐能让图块重新接近；Figure 3 应同时看两组曲线，低残差并不是单纯来自“模型更复杂”，还取决于内容是否仍相同。Figure 4–5 的背景窗口被遮挡后，即使允许变形也不能继续解释原模板。

<!-- vision-figure: shi-tomasi-6 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-6.webp" width="795" height="369" alt="Shi–Tomasi 原论文 Figure 6：合成斑点的迭代仿射对齐。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 6 · 合成斑点的迭代仿射对齐。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: shi-tomasi-7 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-7.webp" width="850" height="490" alt="Shi–Tomasi 原论文 Figure 7：仿射参数的收敛轨迹。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 7 · 仿射参数的收敛轨迹。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: shi-tomasi-8 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-8.webp" width="850" height="297" alt="Shi–Tomasi 原论文 Figure 8：真实图块的拟合与收敛。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 8 · 真实图块的拟合与收敛。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: shi-tomasi-9 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-9.webp" width="829" height="370" alt="Shi–Tomasi 原论文 Figure 9：在只有部分仿射自由度可观测时拟合。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 9 · 在只有部分仿射自由度可观测时拟合。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

这些后续模拟与实图试验检验的是运动拟合和特征监测。读它们时要分清：在满足仿射模型的合成变换上收敛，不等于能够抵抗任意透视、深度边界或真实动态物体。原论文的结论始终依赖图块是否仍对应同一物理表面。

### 3.4 好的初始点，也需要长期质量监测

<!-- vision-figure: shi-tomasi-10 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-10.webp" width="787" height="537" alt="Shi–Tomasi 原论文 Figure 10：前向移动相机拍摄的第一帧；随后图像中的物体会逐渐变大。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 10 · 前向移动相机拍摄的第一帧；随后图像中的物体会逐渐变大。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: shi-tomasi-11 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-11.webp" width="787" height="549" alt="Shi–Tomasi 原论文 Figure 11：按局部纹理条件筛出的 102 个跟踪点，展示良好初始可定位性。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 11 · 按局部纹理条件筛出的 102 个跟踪点，展示良好初始可定位性。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: shi-tomasi-12 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-12.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-12.webp" width="787" height="636" alt="Shi–Tomasi 原论文 Figure 12：只用平移残差监测长期跟踪时，多数曲线混在一起，难以区分好坏特征。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 12 · 只用平移残差监测长期跟踪时，多数曲线混在一起，难以区分好坏特征。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 10 是相机向前运动时的初始图像，Figure 11 标出按纹理条件选出的 102 点。Figure 12 用纯平移残差检查它们：多数曲线挤在一起，难以识别真正失效的点。可定位性保证的是初始局部问题，不能替代后续可见性与模型一致性。

<!-- vision-figure: shi-tomasi-13 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-13.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-13.webp" width="829" height="552" alt="Shi–Tomasi 原论文 Figure 13：后续监测曲线所对应的特征位置。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 13 · 后续监测曲线所对应的特征位置。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: shi-tomasi-14 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-14.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-14.webp" width="829" height="670" alt="Shi–Tomasi 原论文 Figure 14：不同特征随时间变化的图块。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 14 · 不同特征随时间变化的图块。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: shi-tomasi-15 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/shi-tomasi-15.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/shi-tomasi-15.webp" width="850" height="595" alt="Shi–Tomasi 原论文 Figure 15：仿射监测区别稳定图块与失效图块。" loading="lazy" /></a>
  <figcaption>Shi–Tomasi 原论文 Figure 15 · 仿射监测区别稳定图块与失效图块。 <a href="https://users.cs.duke.edu/~tomasi/papers/shi/shiCvpr94.pdf#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 13–14 把几个点的实际图块展开，能看到前景边缘与背景相对位置变化、遮挡及局部变形。Figure 15 允许仿射后，正常形变可以被吸收，剩余高残差更有机会指向内容失配。这里“更低的误差”必须和图块内容一起读；自由度更多的模型也可能拟合错误区域。

### 3.5 回看 1981 年实验：由粗到细的思想早于现代网络

<!-- vision-figure: lucas-kanade-3 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/lucas-kanade-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/lucas-kanade-3.webp" width="484" height="427" alt="Lucas–Kanade 原论文 Figure 3：立体相机与三维点的几何关系；同一迭代思想也可用于深度和相机参数。" loading="lazy" /></a>
  <figcaption>Lucas–Kanade 原论文 Figure 3 · 立体相机与三维点的几何关系；同一迭代思想也可用于深度和相机参数。 <a href="https://www.ri.cmu.edu/pub_files/pub3/lucas_bruce_d_1981_2/lucas_bruce_d_1981_2.pdf#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lucas-kanade-4 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/lucas-kanade-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/lucas-kanade-4.webp" width="1387" height="683" alt="Lucas–Kanade 原论文 Figure 4：原始立体图像对，为后续分频段配准提供同一组输入。" loading="lazy" /></a>
  <figcaption>Lucas–Kanade 原论文 Figure 4 · 原始立体图像对，为后续分频段配准提供同一组输入。 <a href="https://www.ri.cmu.edu/pub_files/pub3/lucas_bruce_d_1981_2/lucas_bruce_d_1981_2.pdf#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

原 LK 工作还把迭代配准用于立体深度：Figure 3 是相机与三维点的几何，Figure 4 是实验输入。此时优化变量可以换成深度或相机参数，雅可比也必须经投影模型重新推导；不能把二维平移更新式直接当深度更新式。

<!-- vision-figure: lucas-kanade-5 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/lucas-kanade-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/lucas-kanade-5.webp" width="1435" height="691" alt="Lucas–Kanade 原论文 Figure 5：较低频带的初始深度猜测，对应位置尚有误差。" loading="lazy" /></a>
  <figcaption>Lucas–Kanade 原论文 Figure 5 · 较低频带的初始深度猜测，对应位置尚有误差。 <a href="https://www.ri.cmu.edu/pub_files/pub3/lucas_bruce_d_1981_2/lucas_bruce_d_1981_2.pdf#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lucas-kanade-6 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/lucas-kanade-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/lucas-kanade-6.webp" width="1435" height="660" alt="Lucas–Kanade 原论文 Figure 6：较低频带迭代后修正对应位置，为更高频带提供初值。" loading="lazy" /></a>
  <figcaption>Lucas–Kanade 原论文 Figure 6 · 较低频带迭代后修正对应位置，为更高频带提供初值。 <a href="https://www.ri.cmu.edu/pub_files/pub3/lucas_bruce_d_1981_2/lucas_bruce_d_1981_2.pdf#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 5–6 是较低频段的初值与迭代结果：先让大结构对齐，再为更细结构提供初值。原文选择带通图像，是因为极低频的明暗变化可能来自照明，而非深度；“低频一定更可靠”也有条件。

<!-- vision-figure: lucas-kanade-7 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/lucas-kanade-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/lucas-kanade-7.webp" width="1435" height="759" alt="Lucas–Kanade 原论文 Figure 7：提高一个频带，继承上一阶段深度并增加新的细节点。" loading="lazy" /></a>
  <figcaption>Lucas–Kanade 原论文 Figure 7 · 提高一个频带，继承上一阶段深度并增加新的细节点。 <a href="https://www.ri.cmu.edu/pub_files/pub3/lucas_bruce_d_1981_2/lucas_bruce_d_1981_2.pdf#page=9" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lucas-kanade-8 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/lucas-kanade-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/lucas-kanade-8.webp" width="1435" height="699" alt="Lucas–Kanade 原论文 Figure 8：这一频带完成深度修正后的对应，展示逐级细化。" loading="lazy" /></a>
  <figcaption>Lucas–Kanade 原论文 Figure 8 · 这一频带完成深度修正后的对应，展示逐级细化。 <a href="https://www.ri.cmu.edu/pub_files/pub3/lucas_bruce_d_1981_2/lucas_bruce_d_1981_2.pdf#page=9" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lucas-kanade-9 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/lucas-kanade-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/lucas-kanade-9.webp" width="1435" height="720" alt="Lucas–Kanade 原论文 Figure 9：再提高一个频带，检查更精细图像结构下的初始对应。" loading="lazy" /></a>
  <figcaption>Lucas–Kanade 原论文 Figure 9 · 再提高一个频带，检查更精细图像结构下的初始对应。 <a href="https://www.ri.cmu.edu/pub_files/pub3/lucas_bruce_d_1981_2/lucas_bruce_d_1981_2.pdf#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lucas-kanade-10 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/lucas-kanade-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/lucas-kanade-10.webp" width="1435" height="665" alt="Lucas–Kanade 原论文 Figure 10：最后一阶段深度修正后的结果；原始实验仍需要人工选点和初值。" loading="lazy" /></a>
  <figcaption>Lucas–Kanade 原论文 Figure 10 · 最后一阶段深度修正后的结果；原始实验仍需要人工选点和初值。 <a href="https://www.ri.cmu.edu/pub_files/pub3/lucas_bruce_d_1981_2/lucas_bruce_d_1981_2.pdf#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 7–10 每次提高一个频带，继承上一阶段深度并增加可见细节点。原文的实现仍需要人工选点和初始深度，作者也把自动选点列为后续问题。这个历史实验与今天常用的全自动金字塔稀疏 LK 不应画等号，却已经明确呈现了“先用粗结构建立收敛起点，再用细结构提高精度”的思路。

## 4. 跨时间重新识别：为什么 SIFT 要先找尺度

桌上的小标签占 12 像素时，一个固定 $15\times15$ 窗口包括它和周围背景；靠近后标签占 48 像素，同样的窗口只看到局部。直接比较这两个窗口，从一开始就在比较不同范围的内容。

SIFT 为每个点建立位置、尺度、方向组成的局部坐标系，再在这个坐标系里描述图像。**点的位置应随变换移动，描述子则尽量保持可比较。** 前者是协变性，后者是近似不变性。

### 4.1 高斯尺度空间与 DoG

$$
L(\mathbf x,\sigma)=G_\sigma*I(\mathbf x),\qquad
G_\sigma(\mathbf x)=\frac{1}{2\pi\sigma^2}\exp\left(-\frac{\|\mathbf x\|^2}{2\sigma^2}\right),
$$

$$
D(\mathbf x,\sigma)=L(\mathbf x,k\sigma)-L(\mathbf x,\sigma).
$$

高斯平滑让细碎结构逐渐消失，DoG 检测在某个尺度特别突出的结构。由 $\partial G/\partial\sigma=\sigma\nabla^2G$ 得到

$$
D(\mathbf x,\sigma)\approx(k-1)\sigma^2\nabla^2L(\mathbf x,\sigma).
$$

关键是 $\sigma^2$ 的尺度归一化：不同尺度的响应必须具有可比较的意义。每个 octave 让 $\sigma$ 加倍，若分成 $s$ 个间隔，则 $k=2^{1/s}$。相邻高斯层可以用增量模糊获得，增量标准差满足 $\sigma_{\mathrm{inc}}^2=\sigma_{\mathrm{target}}^2-\sigma_{\mathrm{current}}^2$，不能把两个标准差直接相减。

<!-- vision-figure: sift-1 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-1.webp" width="1394" height="948" alt="SIFT 原论文 Figure 1：高斯金字塔与相邻尺度差分。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 1 · 高斯金字塔与相邻尺度差分。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: sift-2 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-2.webp" width="1394" height="473" alt="SIFT 原论文 Figure 2：一个 DoG 候选与 26 个邻居比较。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 2 · 一个 DoG 候选与 26 个邻居比较。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 1 里的高斯层和 DoG 层数量不同，因为相减会少一层；还要预留相邻尺度供极值比较。Figure 2 中一个候选与本层 8 个、上下层各 9 个邻居比较，总共 26 个。这里检测的是三维离散尺度空间中的极值，不是“每张图独立找角点再合并”。

### 4.2 更密地采样尺度，为什么不一定提高重复率

<!-- vision-figure: sift-3 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-3.webp" width="1536" height="584" alt="SIFT 原论文 Figure 3：尺度采样密度对重复率和点数量的不同影响。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 3 · 尺度采样密度对重复率和点数量的不同影响。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: sift-4 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-4.webp" width="1394" height="693" alt="SIFT 原论文 Figure 4：初始高斯平滑程度与重复性。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 4 · 初始高斯平滑程度与重复性。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=9" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 3 同时报告比例和数量：更密的尺度采样会发现更多极值，其中有些不稳定；因此总的正确匹配数可能增加，而重复率不再增加。Figure 4 则比较初始平滑程度。这两张图支撑作者选择每 octave 3 个尺度间隔、初始 $\sigma=1.6$ 的折中，并不是证明这组数字适合所有分辨率和噪声条件。

这些实验使用已知的合成变换，匹配位置的容差随特征尺度变化。其“重复率”不能直接与固定 1 像素阈值的现代基准并排比较。

## 5. 在检测结果上再做两次体检

### 5.1 亚像素、亚尺度定位

对 DoG 在候选附近做二阶展开，令 $\boldsymbol\xi=(\Delta x,\Delta y,\Delta\sigma)^\top$：

$$
D(\boldsymbol\xi)\approx D_0+\mathbf g_D^\top\boldsymbol\xi+\frac12\boldsymbol\xi^\top H_D\boldsymbol\xi,
\qquad\widehat{\boldsymbol\xi}=-H_D^{-1}\mathbf g_D.
$$

这是拟合 DoG 极值，与前面最小化图块匹配误差的 $G$ 不同。估计偏移超过半个采样间隔时，应移动参考格点再拟合，而不是无条件接受一个远离近似区域的结果。拟合后的响应过低则删除；论文中 0.03 的阈值对应图像值在 $[0,1]$ 的约定。

### 5.2 为什么 DoG 响应强，仍可能定位不准

空间 Hessian $H_{xy}$ 的两个特征值描述峰的曲率。沿边的脊线可以响应很强，却在切向上平坦。若曲率绝对值之比为 $r\ge1$，则

$$
\frac{(\operatorname{tr}H_{xy})^2}{\det H_{xy}}=\frac{(r+1)^2}{r}.
$$

先要求 $\det H_{xy}>0$，再对右侧设阈值，便可避免显式求特征值。原文使用最大曲率比 10，对应阈值 12.1。**GFTT 要求梯度二阶矩的最小特征值够大；SIFT 这里限制的是 DoG 空间 Hessian 的曲率比。** 两者都在拒绝定位歧义，具体矩阵不能混用。

<!-- vision-figure: sift-5 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-5.webp" width="1394" height="1016" alt="SIFT 原论文 Figure 5：低对比度与边缘响应筛除前后的点。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 5 · 低对比度与边缘响应筛除前后的点。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=11" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 5 展示了候选从 832 个到去低对比度后的 729 个，再到去边缘响应后的 536 个。减少点数是为了提高可靠性，不是为了使图显得干净。

## 6. 统一方向之后，怎样写出 128 个数

### 6.1 主方向定义一个局部坐标系

在点的尺度上计算梯度幅值和角度，用高斯加权的 36-bin 方向直方图找主峰。方向计算应使用 $\operatorname{atan2}(I_y,I_x)$ 保留象限。接近主峰强度的其他峰也可生成不同方向的特征；这解释了为何某些 SIFT 关键点位置和尺度相同，却有不同方向。

若主方向为 $\theta$，局部坐标和相对梯度角度为

$$
\mathbf q'=\frac1\sigma R(-\theta)(\mathbf q-\mathbf p),\qquad
\phi'=\operatorname{wrap}(\phi-\theta).
$$

图像旋转时，点的主方向跟着旋转，在局部坐标系里的结构就有机会保持接近。对称图案可能没有唯一主方向；这一机制不是任意视角下的不变性证明。

<!-- vision-figure: sift-6 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-6.webp" width="1394" height="693" alt="SIFT 原论文 Figure 6：增加噪声后，检测、方向和描述匹配分别失去多少稳定性。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 6 · 增加噪声后，检测、方向和描述匹配分别失去多少稳定性。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 6 把定位尺度、再加方向、最后描述匹配的成功比例逐级画出。这样才能判断瓶颈发生在检测还是描述，而不是看到最终匹配率下降就全部怪罪描述子。

### 6.2 空间分格保留结构，方向统计允许小变形

标准 SIFT 把规范化邻域分成 $4\times4$ 个空间格，每格统计 8 个方向，所以维度为 $4\times4\times8=128$。若只有一个方向直方图，“左边竖边、右边横边”和相反排列就可能不可区分。若保存每个像素的精确梯度，又会对小错位太敏感。

<!-- vision-figure: sift-7 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-7.webp" width="1394" height="559" alt="SIFT 原论文 Figure 7：局部梯度如何聚合成分格方向直方图。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 7 · 局部梯度如何聚合成分格方向直方图。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=15" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: sift-histogram -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-histogram.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-histogram.svg" width="1100" height="470" alt="自制图 4：示意梯度投票的空间布局；箭头与柱高是教学输入，展示 4×4×8 的组织方式，不是某张实测图的描述子。" loading="lazy" /></a>
  <figcaption>自制图 4 · 示意梯度投票的空间布局；箭头与柱高是教学输入，展示 4×4×8 的组织方式，不是某张实测图的描述子。</figcaption>
</figure>
<!-- /vision-figure -->

Figure 7 为方便绘图只画了 $2\times2$ 个格，不能因此把论文的标准描述子误读成 32 维。每个梯度样本会在两个空间方向和角度方向上做三线性分配，最多影响 8 个相邻 bin。例如相对 bin 小数坐标为 $(0.25,0.5,0.2)$，一个幅值为 10 的样本分给较低三个索引的贡献是 $10\times0.75\times0.5\times0.8=3$；其他七份加起来为 7。这样跨过格边界时，描述子不会突然跳变。

### 6.3 归一化解决哪些光照变化

先做 $L_2$ 归一化，将每个分量截断到不超过 0.2，再归一化。灰度加常数不改变梯度；乘以正增益会放大梯度，但单位长度归一化会抵消整体倍率。截断则降低少量特别强梯度的支配作用。

这主要应对局部近似仿射的亮度变化。局部阴影、反光、饱和裁切和模糊会改变梯度结构，不能靠一次向量归一化自动解决。$a<0$ 的对比度反转也不能直接套用正增益的方向不变解释。

<!-- vision-figure: sift-8 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-8.webp" width="1394" height="693" alt="SIFT 原论文 Figure 8：空间格与方向数量对描述区分力的影响。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 8 · 空间格与方向数量对描述区分力的影响。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=17" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: sift-9 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-9.webp" width="1394" height="693" alt="SIFT 原论文 Figure 9：平面视角倾斜下的检测和匹配退化。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 9 · 平面视角倾斜下的检测和匹配退化。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=18" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: sift-10 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-10.webp" width="1394" height="693" alt="SIFT 原论文 Figure 10：数据库干扰点增多后的匹配表现。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 10 · 数据库干扰点增多后的匹配表现。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=19" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 8 说明描述子越大并非越好：区分力和对形变的敏感性在竞争。Figure 9 明确显示随平面视角倾斜增大，各级成功率都下降；SIFT 是对尺度与平面内旋转做规范化，不是完整仿射不变。Figure 10 则把干扰候选数量增加后的识别难度单独拿出来讨论。

## 7. 最像的那个，并不一定是同一个

### 7.1 比值检验是在问“第一名领先得够不够”

设最近和次近描述子距离为 $d_1,d_2$，接受条件为 $d_1/d_2<\eta$。若两个候选距离为 0.20 和 0.21，最近邻虽然存在，证据却很弱；若为 0.20 和 0.60，区分度就高得多。若实现比较平方距离，应改用 $d_1^2/d_2^2<\eta^2$，不能保留同一个数值阈值。

<!-- vision-figure: sift-11 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-11.webp" width="1394" height="693" alt="SIFT 原论文 Figure 11：正确和错误匹配的最近邻距离比值分布。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 11 · 正确和错误匹配的最近邻距离比值分布。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=20" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 11 画的是该实验条件下正确与错误匹配的比值分布。它支撑阈值筛选，却不意味着“比值 0.8 等于正确概率 80%”。Lowe 的 0.8 是经验工作点，不是适用于每种描述子、每个数据库的概率校准。

### 7.2 互为最近邻与几何验证补上不同约束

互为最近邻限制两边的选择一致；比值检验衡量歧义；RANSAC 检验一组匹配能否共同解释几何。平面或纯旋转可考虑单应，已标定一般两视图可考虑本质矩阵，有 3D 地图时则用 PnP。使用哪一个必须来自问题本身。

原 SIFT 论文的物体识别还包括 Hough 投票和几何拟合，不应把后来常见的“两图 SIFT + RANSAC”完整归成原论文的唯一管线。

<!-- vision-figure: sift-12 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-12.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-12.webp" width="1394" height="507" alt="SIFT 原论文 Figure 12：遮挡与杂乱背景中的多物体识别。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 12 · 遮挡与杂乱背景中的多物体识别。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=23" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: sift-13 -->
<figure>
  <a href="/HomepageX/media/gftt-klt-sift/sift-13.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/gftt-klt-sift/sift-13.webp" width="1394" height="1101" alt="SIFT 原论文 Figure 13：通过局部特征进行场景位置识别。" loading="lazy" /></a>
  <figcaption>SIFT 原论文 Figure 13 · 通过局部特征进行场景位置识别。 <a href="https://www.cs.ubc.ca/~lowe/papers/ijcv04.pdf#page=24" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 12 的遮挡物体、Figure 13 的场景定位展示了多条局部证据如何支持整体识别。成功的关键不仅是一个向量很独特，还包括多个匹配在位置、尺度、方向及几何上相容。背景里额外检测出的点不会自动成为正确对应。

## 8. 把三种工具放回前端系统

| 问题 | GFTT + 金字塔 LK | SIFT 检测与描述匹配 |
| --- | --- | --- |
| 对第二帧的先验 | 点通常在预测位置附近 | 可在整图或检索候选内找 |
| 直接优化对象 | 局部光度残差 | 描述子距离，随后几何估计 |
| 输出 | 带轨迹身份的点位置与状态 | 点、尺度、方向、描述子与候选匹配 |
| 主要优势 | 利用时序连续性，计算轻，亚像素迭代 | 支持尺度和方向变化及跨时间重识别 |
| 典型瓶颈 | 曝光变化、遮挡、超出收敛域、图块跨深度 | 重复纹理、极端视角、低纹理、模糊 |

一个合理的视频前端可以连续跟踪已有点、在空区域补点、定期检查几何；失去轨迹后再借助描述子找回关联。还可以用学习检测器选点、让传统 LK 继续跟踪。检测器是否学习化、跟踪器是否优化式、匹配器是否使用上下文，是三个可以独立替换的设计轴。

最后记住一个贯穿后续文章的限制：**高分角点、低光度残差、最近描述子，都只是某一层的证据。** 它们必须继续通过可见性、几何一致性和系统状态估计的检验，才能成为可信的相机运动与地图约束。

下一篇：[SuperGlue 与 LightGlue：为什么匹配需要上下文](/HomepageX/blog/sparse-feature-and-visual-recognition/superglue-lightglue/)。
