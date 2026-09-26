---
title: "读懂 SuperGlue 与 LightGlue：从各找各的最近邻，到共同决定谁该匹配"
description: "用重复窗格解释集合上下文、注意力、带 dustbin 的最优传输，以及 LightGlue 的匹配性、深监督、点裁剪与提前退出。"
date: 2026-09-26
tags: [论文精读, 特征匹配, Transformer, 几何视觉]
---

拍摄一栋楼的两张照片，每扇窗都有四个相似的角。局部描述子已经很强，最近邻仍然可能把第三扇窗的左上角配到第五扇窗。问题不一定是这个小图块描述得不够好，而是我们把“楼顶在哪、隔壁窗格怎么排列、另一个点已选择谁”这些证据都丢了。

[SuperPoint](/HomepageX/blog/superpoint/)负责产生点和描述子，[SIFT](/HomepageX/blog/sparse-feature-and-visual-recognition/gftt-klt-sift/)通过规范化局部坐标增强可比较性。SuperGlue 和 LightGlue 接过这些稀疏集合，回答另一个问题：**能否让两张图里的点交换信息，再共同决定对应关系和拒绝关系？**

> 来源：[SuperGlue，CVPR 2020](https://openaccess.thecvf.com/content_CVPR_2020/papers/Sarlin_SuperGlue_Learning_Feature_Matching_With_Graph_Neural_Networks_CVPR_2020_paper.pdf)及[作者实现](https://github.com/magicleap/SuperGluePretrainedNetwork)；[LightGlue，ICCV 2023，arXiv v1 含附录](https://arxiv.org/abs/2306.13643v1)及[作者实现](https://github.com/cvg/LightGlue)。

## 1. 先把输出定义正确：有些点就不该有伙伴

图 A 有 $M$ 个点，图 B 有 $N$ 个点。输入包括位置 $\mathbf p_i$、描述子 $\mathbf d_i\in\mathbb R^D$，SuperGlue 还把检测分数送入位置编码。输出不是新的图像，也不是最终相机位姿，而是对应关系的软分配矩阵 $P\in[0,1]^{M\times N}$。

理想的一对一匹配允许部分点没有对应：

$$
P\mathbf1_N\le\mathbf1_M,\qquad P^\top\mathbf1_M\le\mathbf1_N.
$$

遮挡、视野不重叠和检测器漏点都会导致“不匹配”。特别要区分：一个物理位置在 B 中可见，但 B 的检测器没在附近输出点，它对于当前稀疏匹配问题同样可能没有伙伴。

<!-- vision-figure: matching-context -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/matching-context.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/matching-context.svg" width="1100" height="470" alt="自制图 1：重复窗格产生一对多歧义；稳定邻域关系提供附加证据，但没有可区分结构时上下文也会失败。" loading="lazy" /></a>
  <figcaption>自制图 1 · 重复窗格产生一对多歧义；稳定邻域关系提供附加证据，但没有可区分结构时上下文也会失败。</figcaption>
</figure>
<!-- /vision-figure -->

单独对每一行做 softmax，会强迫每个 A 点向 B 分掉全部概率，且多个 A 点可以同时强烈选择同一个 B 点。互为最近邻能拒绝部分冲突，却是在固定描述子之后做筛选。SuperGlue 要把上下文和选择竞争一起放进可训练过程。

<!-- vision-figure: superglue-1 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/superglue-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/superglue-1.webp" width="813" height="506" alt="SuperGlue 原论文 Figure 1：局部检测器、SuperGlue 与几何后端的接口。SuperGlue 接收已有点和描述子，输出带未匹配判断的对应。" loading="lazy" /></a>
  <figcaption>SuperGlue 原论文 Figure 1 · 局部检测器、SuperGlue 与几何后端的接口。SuperGlue 接收已有点和描述子，输出带未匹配判断的对应。 <a href="https://openaccess.thecvf.com/content_CVPR_2020/papers/Sarlin_SuperGlue_Learning_Feature_Matching_With_Graph_Neural_Networks_CVPR_2020_paper.pdf#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: superglue-2 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/superglue-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/superglue-2.webp" width="813" height="632" alt="SuperGlue 原论文 Figure 2：困难室内图像对的匹配，连线按对极误差着色。看重复结构与视角变化中的错误连线，不能只比较总匹配数。" loading="lazy" /></a>
  <figcaption>SuperGlue 原论文 Figure 2 · 困难室内图像对的匹配，连线按对极误差着色。看重复结构与视角变化中的错误连线，不能只比较总匹配数。 <a href="https://openaccess.thecvf.com/content_CVPR_2020/papers/Sarlin_SuperGlue_Learning_Feature_Matching_With_Graph_Neural_Networks_CVPR_2020_paper.pdf#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

原图用实际对应和极线误差展示：好匹配需要跨视图一致性。但图中的绿线多并不自动意味着位姿可观测；纯旋转、低视差等退化条件仍然存在。

## 2. SuperGlue 第一部分：让点在集合里变得更好认

### 2.1 位置不是标签，而是关系推理的输入

初始化状态为

$$
\mathbf x_i^{(0)}=\mathbf d_i+\operatorname{MLP}_{\mathrm{enc}}(x_i,y_i,c_i).
$$

坐标在送入网络前需要按图像大小归一化，否则相同几何布局在不同分辨率下数值完全不同。检测分数 $c_i$ 是输入信息，不是最终匹配置信度。初始描述子只描述局部外观，更新后的 $\mathbf x_i$ 则会依赖整组点以及另一张图。

<!-- vision-figure: superglue-3 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/superglue-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/superglue-3.webp" width="1667" height="429" alt="SuperGlue 原论文 Figure 3：关键点编码、交替自注意力/交叉注意力和最优传输的完整结构。沿着描述子变化追踪上下文如何进入最终分配。" loading="lazy" /></a>
  <figcaption>SuperGlue 原论文 Figure 3 · 关键点编码、交替自注意力/交叉注意力和最优传输的完整结构。沿着描述子变化追踪上下文如何进入最终分配。 <a href="https://openaccess.thecvf.com/content_CVPR_2020/papers/Sarlin_SuperGlue_Learning_Feature_Matching_With_Graph_Neural_Networks_CVPR_2020_paper.pdf#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

### 2.2 Self-attention 看自己这张图，cross-attention 看另一张图

以单头为例，令 $\mathbf q_i=W_q\mathbf x_i$、$\mathbf k_j=W_k\mathbf x_j$、$\mathbf v_j=W_v\mathbf x_j$，消息为

$$
\alpha_{ij}=\frac{\exp(\mathbf q_i^\top\mathbf k_j/\sqrt{d_h})}
{\sum_{j'\in\mathcal N(i)}\exp(\mathbf q_i^\top\mathbf k_{j'}/\sqrt{d_h})},\qquad
\mathbf m_i=\sum_{j\in\mathcal N(i)}\alpha_{ij}\mathbf v_j,
$$

$$
\mathbf x_i^{(\ell+1)}=\mathbf x_i^{(\ell)}+
\operatorname{MLP}_{\ell}([\mathbf x_i^{(\ell)};\mathbf m_i]).
$$

$d_h$ 是单头维度。论文抽象公式省略了缩放项，这里写出常用实现形式。Self-attention 的 $\mathcal N(i)$ 是同一图的点，cross-attention 则是另一图的点。多头允许不同的关系并行表示。

对重复窗角，self-attention 可以引入楼顶、门洞等独特结构；cross-attention 可以问“另一图中哪一组点同时支持这样的布局”。二者交替，而不是先独立增强两张图，再只进行一次固定距离比较。

<!-- vision-figure: superglue-4 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/superglue-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/superglue-4.webp" width="813" height="565" alt="SuperGlue 原论文 Figure 4：自注意力与交叉注意力的权重可视化。自注意力能够连接同图远处的可区分区域，不受局部窗口限制。" loading="lazy" /></a>
  <figcaption>SuperGlue 原论文 Figure 4 · 自注意力与交叉注意力的权重可视化。自注意力能够连接同图远处的可区分区域，不受局部窗口限制。 <a href="https://openaccess.thecvf.com/content_CVPR_2020/papers/Sarlin_SuperGlue_Learning_Feature_Matching_With_Graph_Neural_Networks_CVPR_2020_paper.pdf#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

原图中的注意力射线不是最终匹配。权重大表示该点的 value 对当前状态更新影响较大，不能直接解释为“这两个点就是同一物理点”。Self-attention 本来就连接同图点，更不可能每条边都是跨视图对应。

<!-- vision-figure: superglue-7 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/superglue-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/superglue-7.webp" width="1667" height="424" alt="SuperGlue 原论文 Figure 7：不同层和注意力头关注不同信息。图中同时出现局部、全局、自相似和候选匹配模式，不应给所有头赋予同一种语义。" loading="lazy" /></a>
  <figcaption>SuperGlue 原论文 Figure 7 · 不同层和注意力头关注不同信息。图中同时出现局部、全局、自相似和候选匹配模式，不应给所有头赋予同一种语义。 <a href="https://openaccess.thecvf.com/content_CVPR_2020/papers/Sarlin_SuperGlue_Learning_Feature_Matching_With_Graph_Neural_Networks_CVPR_2020_paper.pdf#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 7 进一步展开不同层与不同头：有些关注局部邻域，有些利用全局结构，有些寻找自相似或跨图候选。不要给每个头都贴上同一种几何含义；真正被监督的是最终对应，内部注意力只是一条信息传递路径。

### 2.3 网络学到几何线索，不等于执行了刚体求解

网络允许远距离交互，计算随点数增长。完整自注意力和交叉注意力的主要项约为 $O((M^2+N^2+MN)D)$。这也是检测点数量需要预算的原因。

这些模块没有显式强制所有匹配服从一个本质矩阵。重复建筑、训练分布外的透视以及动态区域仍可能产生自洽但错误的答案。后面的 RANSAC/PnP/BA 依然有独立作用。

## 3. SuperGlue 第二部分：把拒绝和竞争放进分配矩阵

### 3.1 Dustbin 是有容量的“不匹配”出口

更新后的描述经线性投影得到 $\mathbf f_i$，相似度为 $S_{ij}=\langle\mathbf f_i^A,\mathbf f_j^B\rangle$。这些 matching descriptors 不必像输入描述子那样单位归一化，其模长也能参与表达分数。

在矩阵右侧和底部各加一个 dustbin，所有新增分数由可学习标量 $z$ 初始化。目标边际为

$$
\mathbf a=(\underbrace{1,\ldots,1}_{M},N)^\top,\qquad
\mathbf b=(\underbrace{1,\ldots,1}_{N},M)^\top.
$$

$$
\overline P\mathbf1=\mathbf a,\qquad \overline P^\top\mathbf1=\mathbf b.
$$

两边总质量都为 $M+N$。dustbin 不是“第 $N+1$ 个普通点”：它必须可以接收多个没有伙伴的点。若把所有行列质量都设成 1，在点数不同或大量遮挡时，问题本身就设错了。

<!-- vision-figure: matching-dustbin -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/matching-dustbin.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/matching-dustbin.svg" width="1100" height="470" alt="自制图 2：一个满足 SuperGlue 扩展边缘约束的硬分配极限：a3 未匹配，空槽之间的质量用于平衡矩阵。" loading="lazy" /></a>
  <figcaption>自制图 2 · 一个满足 SuperGlue 扩展边缘约束的硬分配极限：a3 未匹配，空槽之间的质量用于平衡矩阵。</figcaption>
</figure>
<!-- /vision-figure -->

例如 $M=3,N=2$，两组真对应为 $a_1\leftrightarrow b_1$、$a_2\leftrightarrow b_2$，$a_3$ 被遮挡。一个合法硬分配是

$$
\overline P=\begin{bmatrix}1&0&0\\0&1&0\\0&0&1\\0&0&2\end{bmatrix}.
$$

末行、末列分别是 dustbin；右下角的 2 用于平衡质量，不代表两条视觉匹配。删去 dustbin 后，就是有一个全零行的部分匹配。

### 3.2 Sinkhorn 实际在迭代什么

把熵正则化目标写成

$$
\max_{\overline P\ge0}\ \langle\overline S,\overline P\rangle+
\varepsilon H(\overline P),\qquad
H(\overline P)=-\sum_{ij}\overline P_{ij}\log\overline P_{ij},
$$

并满足上面的边际。令 $K=\exp(\overline S/\varepsilon)$，交替更新

$$
\mathbf u\leftarrow\mathbf a\oslash(K\mathbf v),\qquad
\mathbf v\leftarrow\mathbf b\oslash(K^\top\mathbf u),\qquad
\overline P=\operatorname{diag}(\mathbf u)K\operatorname{diag}(\mathbf v).
$$

$\oslash$ 表示逐元素除法。一次调整行和，又会改变列和，因此要迭代。实现通常在 log 域用 log-sum-exp，避免指数溢出；还可能先把边际除以 $M+N$，最后再恢复尺度。不能拿中间的归一化运输质量直接当成论文最终匹配分数。

有限次 Sinkhorn 给出熵正则化的软分配，**不等同于精确 Hungarian 硬指派**。推理还要取互为最大值的候选并使用匹配阈值。降低温度或熵强度让分配更尖锐，也可能放大错误峰。

## 4. 监督从哪里来：不是把最近邻当真值

已知平面单应，或相机位姿、深度和内参，可以把 A 点投到 B。深度情况下，采用相机 A 到 B 的变换 $T_{BA}$：

$$
\mathbf p'_B=\pi\!\left(K_B\begin{bmatrix}I_3&0\end{bmatrix}T_{BA}
\begin{bmatrix}z_AK_A^{-1}\widetilde{\mathbf p}_A\\1\end{bmatrix}\right).
$$

这里 $T_{BA}$ 为 $4\times4$ 齐次变换，$[I_3\;0]$ 取出三维坐标，$\pi(x,y,z)=(x/z,y/z)$ 完成投影除法。还需要前方深度、图像范围、双向重投影和目标深度一致性检查，才能判断点是否可见以及是否接近某个 B 检测点。深度空洞不是“确定不存在对应”；监督实现应区分未知和负样本。

<!-- vision-figure: matching-supervision -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/matching-supervision.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/matching-supervision.svg" width="1100" height="470" alt="自制图 3：教学概率矩阵展示标签与负对数监督；这些示意概率不代表 Sinkhorn 完整扩展矩阵。" loading="lazy" /></a>
  <figcaption>自制图 3 · 教学概率矩阵展示标签与负对数监督；这些示意概率不代表 Sinkhorn 完整扩展矩阵。</figcaption>
</figure>
<!-- /vision-figure -->

令真匹配集合为 $\mathcal M$，确定无伙伴集合为 $\mathcal U_A,\mathcal U_B$，原论文的负对数似然写成

$$
\mathcal L_{SG}=-\sum_{(i,j)\in\mathcal M}\log\overline P_{ij}
-\sum_{i\in\mathcal U_A}\log\overline P_{i,N+1}
-\sum_{j\in\mathcal U_B}\log\overline P_{M+1,j}.
$$

一个真匹配分到 0.8 的概率，损失约 0.223；分到 0.1 则约 2.303。所有点都送进 dustbin 会被正匹配项惩罚；强制每个点配一个伙伴又会被无匹配项惩罚。论文公式为求和，批实现如何取平均会改变不同图像和样本数量的相对权重。

<!-- vision-figure: superglue-5 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/superglue-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/superglue-5.webp" width="815" height="325" alt="SuperGlue 原论文 Figure 5：室内与室外位姿估计对比。应在相同局部特征与误差阈值下比较，避免把特征更换的收益都归因于匹配器。" loading="lazy" /></a>
  <figcaption>SuperGlue 原论文 Figure 5 · 室内与室外位姿估计对比。应在相同局部特征与误差阈值下比较，避免把特征更换的收益都归因于匹配器。 <a href="https://openaccess.thecvf.com/content_CVPR_2020/papers/Sarlin_SuperGlue_Learning_Feature_Matching_With_Graph_Neural_Networks_CVPR_2020_paper.pdf#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: superglue-6 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/superglue-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/superglue-6.webp" width="1667" height="1496" alt="SuperGlue 原论文 Figure 6：与最近邻加外点过滤的定性比较。绿色为正确对应、红色为错误对应，重点看重复纹理与视角变化下的内点覆盖。" loading="lazy" /></a>
  <figcaption>SuperGlue 原论文 Figure 6 · 与最近邻加外点过滤的定性比较。绿色为正确对应、红色为错误对应，重点看重复纹理与视角变化下的内点覆盖。 <a href="https://openaccess.thecvf.com/content_CVPR_2020/papers/Sarlin_SuperGlue_Learning_Feature_Matching_With_Graph_Neural_Networks_CVPR_2020_paper.pdf#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

结合论文的下游实验看：关注的终点是正确的单应或相对位姿，而不是网络把分配矩阵画得多接近对角线。原文在不同任务上使用不同数据和阈值，结果不能去掉条件后当成一个通用准确率。

## 5. LightGlue：容易的图像对为什么也要算到底

两帧仅相差一点，很多匹配在浅层已经确定。大视角且重叠很少的图像对则需要更多上下文。固定深度网络给两者相同计算预算，不够经济。

LightGlue 同时改变注意力、预测头和训练方式；因此它不是“把 SuperGlue 少运行几层”。

<!-- vision-figure: lightglue-1 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-1.webp" width="814" height="561" alt="LightGlue 原论文 Figure 1：匹配速度与位姿精度的折中。曲线上的不同点包含提前停止等设置，不能只取最快和最准的两端拼成一个配置。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 1 · 匹配速度与位姿精度的折中。曲线上的不同点包含提前停止等设置，不能只取最快和最准的两端拼成一个配置。 <a href="https://arxiv.org/pdf/2306.13643v1#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lightglue-2 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-2.webp" width="814" height="600" alt="LightGlue 原论文 Figure 2：容易与困难图像对需要不同深度。上方容易样本较早停止，下方难样本继续聚合上下文。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 2 · 容易与困难图像对需要不同深度。上方容易样本较早停止，下方难样本继续聚合上下文。 <a href="https://arxiv.org/pdf/2306.13643v1#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lightglue-3 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-3.webp" width="1667" height="487" alt="LightGlue 原论文 Figure 3：每层既更新描述，也估计匹配与判断置信度。停止深度与点剪枝是两个不同的自适应维度。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 3 · 每层既更新描述，也估计匹配与判断置信度。停止深度与点剪枝是两个不同的自适应维度。 <a href="https://arxiv.org/pdf/2306.13643v1#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

### 5.1 相对位置放进 self-attention

LightGlue 使用旋转位置编码，使同图点的注意力分数依赖相对位置。用二维坐标生成多个频率的旋转矩阵 $R(\mathbf p)$，关键关系为

$$
[R(\mathbf p_i)\mathbf q_i]^\top[R(\mathbf p_j)\mathbf k_j]
=\mathbf q_i^\top R(\mathbf p_j-\mathbf p_i)\mathbf k_j.
$$

这是编码构造的相对性，不能扩大解释成对任意相机平移都几何不变：真实不同深度的点在相机平移后会有不同视差。跨图坐标也没有直接可比的原点，论文不把这套相对位置编码直接用于 cross-attention。

交叉注意力还共享两向的相似度计算：$a^{AB}_{ij}=\mathbf k_i^{A\top}\mathbf k_j^B=a^{BA}_{ji}$。同一个相似度矩阵可分别沿两个方向归一化并聚合 value，减少重复乘法。

### 5.2 把“像不像”与“有没有伙伴”分开

LightGlue 对每个点预测 matchability $\sigma_i\in[0,1]$，并使用双向 softmax：

$$
P_{ij}=\sigma_i^A\sigma_j^B
\frac{e^{S_{ij}}}{\sum_{j'}e^{S_{ij'}}}
\frac{e^{S_{ij}}}{\sum_{i'}e^{S_{i'j}}}.
$$

假设两向选择概率分别是 0.8 和 0.75，两点匹配性分别为 0.9 和 0.8，则最终分数为 $0.8\times0.75\times0.9\times0.8=0.432$。若某点确定没有伙伴，只要它的 $\sigma$ 很低，就能抑制全部候选。

这不是 Sinkhorn 的逐轮行列平衡，也没有同样的指定边际。它是一个更便宜的部分分配预测头，互为最大值与阈值仍用于输出筛选。

### 5.3 三种“分数”不能互换

| 量 | 回答的问题 | 典型用途 |
| --- | --- | --- |
| Matchability $\sigma_i$ | 这个点在另一组点中有没有伙伴？ | 拒绝没有对应的点 |
| Assignment $P_{ij}$ | 这一对对应的支持度有多高？ | 选择最终对应 |
| Confidence $c_i^{(\ell)}$ | 当前层的决定是否已接近最终层？ | 提前退出与点裁剪 |

Confidence 高，可能表示“我很确定这个点没有匹配”，而不是“它是一条高质量匹配”。这一区分决定了裁剪逻辑是否正确。

<!-- vision-figure: lightglue-pruning -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-pruning.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-pruning.svg" width="1100" height="470" alt="自制图 4：点剪枝并非直接删掉低匹配分数点；应结合对最终判断的置信度，防止过早删除尚未消歧的点。" loading="lazy" /></a>
  <figcaption>自制图 4 · 点剪枝并非直接删掉低匹配分数点；应结合对最终判断的置信度，防止过早删除尚未消歧的点。</figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lightglue-4 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-4.webp" width="813" height="404" alt="LightGlue 原论文 Figure 4：逐层剔除不可匹配点。先排除视野不重叠区域，再逐渐识别不重复的检测点。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 4 · 逐层剔除不可匹配点。先排除视野不重叠区域，再逐渐识别不重复的检测点。 <a href="https://arxiv.org/pdf/2306.13643v1#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

## 6. 自适应推理为什么需要自适应的训练支持

### 6.1 每层都监督，让浅层真的会匹配

对每层的匹配分数和匹配性施加损失：

$$
\mathcal L_{LG}=-\frac1L\sum_{\ell=1}^{L}\left[
\frac1{|\mathcal M|}\sum_{(i,j)\in\mathcal M}\log P_{ij}^{(\ell)}
+\frac1{2|\mathcal U_A|}\sum_{i\in\mathcal U_A}\log(1-\sigma_i^{A,(\ell)})
+\frac1{2|\mathcal U_B|}\sum_{j\in\mathcal U_B}\log(1-\sigma_j^{B,(\ell)})\right].
$$

空集合项在实现中要跳过或安全归一化。正样本与两侧负样本分别平均，避免不重叠区域多的图像对仅靠数量压倒正匹配。相似度只会让真对应在行列竞争中突出；匹配性则接收是否应拒绝的信号。

### 6.2 Confidence 的标签来自最终决定的一致性

先训练匹配网络，再训练 confidence 分类器。若第 $\ell$ 层对点 $i$ 的决定 $m_i^{(\ell)}$ 与最终层 $m_i^{(L)}$ 相同，标签就是 1；否则为 0。决定包括“无匹配”。这个二分类损失可以写成

$$
\mathcal L_c=-y_i\log c_i-(1-y_i)\log(1-c_i),\qquad
 y_i=\mathbf1[m_i^{(\ell)}=m_i^{(L)}].
$$

它预测的是提前停止是否会改变最终网络答案，**不是几何真值正确性的校准概率**。最终层也可能错。

如果两组点中足够大的比例 $c_i>\lambda_\ell$，则整对图提前退出；如果还不能退出，则只剔除“有信心且无匹配”的点，让后续层在剩下的集合上计算。困难而不确定的点应保留，否则恰好会把最需要推理的对象删掉。

<!-- vision-figure: lightglue-12 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-12.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-12.webp" width="817" height="340" alt="LightGlue 原论文 Figure 12：合成单应预训练样本，包含透视和强光度增强。平面变换监督仍不能覆盖真实三维遮挡的全部变化。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 12 · 合成单应预训练样本，包含透视和强光度增强。平面变换监督仍不能覆盖真实三维遮挡的全部变化。 <a href="https://arxiv.org/pdf/2306.13643v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 12 给出预训练中的强透视与光度增强。合成单应能提供精确二维标签，但真实场景还会出现非平面视差和遮挡，因此后续真实数据训练仍有作用。

<!-- vision-figure: lightglue-5 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-5.webp" width="817" height="310" alt="LightGlue 原论文 Figure 5：单应预训练的收敛速度比较。这里衡量训练图像对数量与训练目标，不是最终真实场景定位成功率。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 5 · 单应预训练的收敛速度比较。这里衡量训练图像对数量与训练目标，不是最终真实场景定位成功率。 <a href="https://arxiv.org/pdf/2306.13643v1#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 5 对比训练进度与损失、召回。更快收敛来自整套架构和训练设计，不能只归因于推理时的裁剪。

## 7. 读实验：快了多少，要和什么一起看

LightGlue 论文的 HPatches 评估将图像短边缩到 480，稀疏方法使用 1024 个点；MegaDepth-1500 相对位姿评估使用 2048 个点、长边 1600。两个任务的数字不能直接混在同一张性能表里。

以论文 Table 2 的 SuperPoint 输入、LO-RANSAC 结果为例：

| 匹配器 | 位姿 AUC@5° / 10° / 20° | 表中时间 ms |
| --- | --- | --- |
| SuperGlue | 65.8 / 78.7 / 87.5 | 70.0 |
| LightGlue | 66.7 / 79.3 / 87.9 | 44.2 |
| LightGlue，自适应 | 66.3 / 79.0 / 87.9 | 31.4 |

这里的位姿误差取旋转角误差和**平移方向**角误差的较大者，不评价单目平移的米制长度。时间属于论文实验设置，不能直接承诺为你的 CPU、嵌入式设备或整条 SLAM 管线的延迟。原文还分别报告普通 RANSAC，说明求解器选择会明显改变最终 AUC。[原文 Table 2](https://arxiv.org/pdf/2306.13643v1#page=7)

<!-- vision-figure: lightglue-6 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-6.webp" width="749" height="565" alt="LightGlue 原论文 Figure 6：可匹配性对错误对应的过滤。视觉上相似的点也可能没有真实对应，matchability 提供额外拒绝能力。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 6 · 可匹配性对错误对应的过滤。视觉上相似的点也可能没有真实对应，matchability 提供额外拒绝能力。 <a href="https://arxiv.org/pdf/2306.13643v1#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lightglue-7 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-7.webp" width="815" height="284" alt="LightGlue 原论文 Figure 7：运行时间随关键点数变化。自适应深度与宽度共同影响耗时，点数不同不宜直接比较单个毫秒数。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 7 · 运行时间随关键点数变化。自适应深度与宽度共同影响耗时，点数不同不宜直接比较单个毫秒数。 <a href="https://arxiv.org/pdf/2306.13643v1#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

这些曲线应连同点数、是否启用优化实现和精度代价一起读。动态推理的平均速度收益不会给出严格的最坏延迟上界；机器人系统仍要测困难图像对的尾部耗时。

<!-- vision-figure: lightglue-8 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-8.webp" width="1667" height="1877" alt="LightGlue 原论文 Figure 8：由易到难的图像对，同时展示剪枝、可匹配性与最终连线。注意困难样本何时仍需后续层。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 8 · 由易到难的图像对，同时展示剪枝、可匹配性与最终连线。注意困难样本何时仍需后续层。 <a href="https://arxiv.org/pdf/2306.13643v1#page=9" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lightglue-9 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-9.webp" width="1670" height="1931" alt="LightGlue 原论文 Figure 9：同一匹配框架接收 SIFT、SuperPoint、DISK 的结果。输入特征的检测覆盖不同，匹配器无法补回没有检测的点。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 9 · 同一匹配框架接收 SIFT、SuperPoint、DISK 的结果。输入特征的检测覆盖不同，匹配器无法补回没有检测的点。 <a href="https://arxiv.org/pdf/2306.13643v1#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

定性图补充了哪些图像更难、哪些点被拒绝。选择性拒绝有价值，但也可能降低召回：如果检测器本来只留下少量可靠点，过于激进的阈值会使后端缺少足够几何约束。

### 7.1 失败图比平均时间更能暴露边界

<!-- vision-figure: lightglue-10 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-10.webp" width="813" height="683" alt="LightGlue 原论文 Figure 10：InLoc 失败案例：重复物体和强纹理可能胜过真正的几何结构。高置信匹配仍需后端几何验证。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 10 · InLoc 失败案例：重复物体和强纹理可能胜过真正的几何结构。高置信匹配仍需后端几何验证。 <a href="https://arxiv.org/pdf/2306.13643v1#page=12" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 10 的 InLoc 案例中，重复而有强纹理的物体仍会误导匹配。上下文并没有显式施加全场景刚体约束，错误对应可能成组出现；几何验证应检查空间覆盖和多帧一致性。

### 7.2 自适应省掉的是哪些计算

<!-- vision-figure: lightglue-11 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-11.webp" width="817" height="336" alt="LightGlue 原论文 Figure 11：不可匹配点随层数逐步被识别。曲线说明剪枝判断是在推理中累积证据，而非一次阈值筛除。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 11 · 不可匹配点随层数逐步被识别。曲线说明剪枝判断是在推理中累积证据，而非一次阈值筛除。 <a href="https://arxiv.org/pdf/2306.13643v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: lightglue-13 -->
<figure>
  <a href="/HomepageX/media/superglue-lightglue/lightglue-13.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superglue-lightglue/lightglue-13.webp" width="817" height="236" alt="LightGlue 原论文 Figure 13：固定 1024 点的模块耗时拆分。双向交叉注意力复用与更轻的分配层是速度收益的重要来源。" loading="lazy" /></a>
  <figcaption>LightGlue 原论文 Figure 13 · 固定 1024 点的模块耗时拆分。双向交叉注意力复用与更轻的分配层是速度收益的重要来源。 <a href="https://arxiv.org/pdf/2306.13643v1#page=15" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 11 显示不可匹配点是在各层逐步被发现的；Figure 13 在固定 1024 点时拆开 self-attention、cross-attention 和分配头耗时。要把架构本身更便宜，与动态深度/宽度跳过计算的收益分开，才能解释硬件或输入难度改变后加速比例为什么会变。

附录进一步展示不同图像和配置下的行为。阅读时沿着“输入覆盖 → 中间决定 → 最终几何”追踪，不要只看连线数量。它们也提醒我们，自适应收益来自输入难度分布，不能用一对高度重叠图像代表整套任务。

## 8. 接入系统之前，要明确哪一层的错误被改善

学习匹配器不能生成检测器没有提供的关键点，也不能把可见性缺失变成对应。图像缩放后点坐标与内参必须同步；不同特征类型的维度、分布和训练权重必须匹配，不能因为张量维度碰巧一样就随意换权重。

一个完整的验证顺序是：先固定提点与分辨率比较匹配质量，再固定几何求解器比较位姿，最后测包括特征提取、数据搬运、匹配和 RANSAC 的总延迟。在光流前端中替换匹配器，还要考虑轨迹 ID、关键帧策略和 IMU 预测，而不只是把每对图匹配成功。

SuperGlue 的主要推进，是让“上下文 + 部分分配”一起学习；LightGlue 的主要推进，是把匹配决策拆得更轻，并使不同难度输入得到不同计算量。它们都把局部描述子提升为成组的对应证据，最终仍需要几何与后端来决定这些证据能支持什么。

继续阅读：[NetVLAD 与 HF-Net：先找地点，再求位姿](/HomepageX/blog/sparse-feature-and-visual-recognition/netvlad-hfnet/)。
