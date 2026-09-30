---
title: "从 NetVLAD 到 HF-Net：先知道大概在哪里，再把相机位姿算准确"
description: "从 BoW、VLAD 的残差统计走到可训练聚合，再解释 HF-Net 的多任务蒸馏、共视聚类、局部匹配与 PnP 定位。"
date: 2026-09-26
tags: [论文精读, VPR, 视觉定位, 知识蒸馏]
---

给机器人一张包含整座校园的三维地图，再给它一张夜晚拍摄的照片。直接把照片里的每个点与全校所有地图点比较，既昂贵，又容易遇到大量相似窗格。人通常先认出“这是图书馆附近”，再靠门框和台阶确定观察位置。

HF-Net 把这种先粗后细的过程变成可计算的定位管线。理解它之前，需要先理解 NetVLAD：**怎样把整张图压成一个适合检索的向量，而又不只是在统计“这里有楼、有树”？**

> 来源：[NetVLAD，arXiv:1511.07247v3](https://arxiv.org/abs/1511.07247v3)；[HF-Net，arXiv:1812.03506v2](https://arxiv.org/abs/1812.03506v2)及[作者代码](https://github.com/ethz-asl/hfnet)。本文的图号以这些固定版本为准，HF-Net 不同版本的架构图编号有变化。

## 训练资源、卡时与数据量

| 项目 | 论文与代码能确认的内容 |
| --- | --- |
| NetVLAD 数据 | 主要使用 Google Street View Time Machine 的同地点跨时间图像，并在 Pitts30k、Tokyo 24/7 等地点识别基准上评估；不同表的训练、验证和测试协议不能合并计数。 |
| HF-Net 数据 | 训练使用 Google Landmarks 185k 图像与 Berkeley Deep Drive 夜间/黎明序列 37k 图像，共约 222k；Aachen、RobotCar、CMU 主要是评测域。 |
| 硬件与卡时 | HF-Net 训练 85k iterations、batch size 32；论文未披露墙钟时间/GPU-hours。NetVLAD 的固定版本也未给出可核对的卡时；文中运行时间图是推理链路，不是训练成本。 |


## 1. 地点检索与六自由度定位，输出根本不同

地点检索输入查询图 $I_q$，返回数据库图片的排序；六自由度定位输入图像及几何地图，输出旋转 $R$ 和平移 $\mathbf t$。最近数据库图的位置可以作为粗略地点提示，但它与当前相机之间可能相差数米、朝向也不同。

<!-- vision-figure: hfnet-1 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-1.webp" width="813" height="474" alt="HF-Net 原论文 Figure 1：先全局检索，再局部特征匹配求 6DoF 位姿。候选检索与几何定位解决不同粒度的问题。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 1 · 先全局检索，再局部特征匹配求 6DoF 位姿。候选检索与几何定位解决不同粒度的问题。 <a href="https://arxiv.org/pdf/1812.03506v2#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: localization-hierarchy -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/localization-hierarchy.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/localization-hierarchy.svg" width="1100" height="470" alt="自制图 1：全局检索缩小数据库范围，局部对应连接三维地图，最后几何估计输出位姿。" loading="lazy" /></a>
  <figcaption>自制图 1 · 全局检索缩小数据库范围，局部对应连接三维地图，最后几何估计输出位姿。</figcaption>
</figure>
<!-- /vision-figure -->

设数据库有 $B$ 张图片，每张有 $n$ 个局部描述子。全量局部匹配需要面对约 $Bn$ 个候选，而全局检索只比较 $B$ 个固定长度向量，并可使用近似近邻索引。取 top-$K$ 后，再在其关联的少量三维点上寻找精确对应。

这个分层有一个硬边界：真实地点根本没有进入候选，后面的局部匹配通常无从挽回。因此检索的 Recall@$K$ 不只是一个独立榜单指标，也约束了整条管线的成功率上限。最终的条件成功率仍取决于地图覆盖和几何质量。

## 2. 从“数有多少”走向“看偏向哪里”

### 2.1 BoW：把描述子量化成词，再计数

给定 $N$ 个局部描述子 $\mathbf x_i\in\mathbb R^D$，用 $K$ 个聚类中心构成视觉词典。硬分配

$$
a_{ik}=\mathbf1\!\left[k=\arg\min_{k'}\|\mathbf x_i-\mathbf c_{k'}\|^2\right]
$$

产生词频 $h_k=\sum_i a_{ik}$。检索中还可以用逆文档频率降低常见词的影响。它保留“每类外观出现多少”，却丢掉了同一词格子内部的变化。

BoW 不是 ORB 的同义词，可以作用于不同局部描述子；DBoW 系统常与 ORB/BRIEF/BRISK 结合，是具体工程选择。

### 2.2 VLAD：在每个词内部记录残差方向

$$
\mathbf V_k=\sum_{i=1}^{N}a_{ik}(\mathbf x_i-\mathbf c_k),\qquad
V\in\mathbb R^{K\times D}.
$$

一个词格里有两组二维描述子。A 图的残差是 $(0.2,0.1),(0.3,0.1)$，B 图的是 $(-0.2,0.1),(-0.3,0.1)$。词频都为 2，但残差和分别为 $(0.5,0.2)$ 与 $(-0.5,0.2)$，可以区分它们位于中心的不同方向。

<!-- vision-figure: vlad-residuals -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/vlad-residuals.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/vlad-residuals.svg" width="1100" height="470" alt="自制图 2：两簇各有四个局部特征，VLAD 保留位置相对中心的残差信息；软分配版本再用归属概率加权。" loading="lazy" /></a>
  <figcaption>自制图 2 · 两簇各有四个局部特征，VLAD 保留位置相对中心的残差信息；软分配版本再用归属概率加权。</figcaption>
</figure>
<!-- /vision-figure -->

残差也会相消，所以 VLAD 并不保留完整局部分布，更不是无损编码。它是一阶统计表示，在紧凑性和区分力之间作取舍。

每个 $\mathbf V_k$ 先做 intra-normalization，再展开并整体归一化：

$$
\widehat{\mathbf V}_k=\frac{\mathbf V_k}{\|\mathbf V_k\|_2+\epsilon},\qquad
\mathbf v=\frac{\operatorname{vec}(\widehat V)}{\|\operatorname{vec}(\widehat V)\|_2+\epsilon}.
$$

这减少同类重复纹理过量出现导致的支配效应。零残差簇要安全处理；归一化不会凭空产生其缺失的信息。$K=64,D=512$ 时展开为 32768 维，可进一步 PCA/白化压缩，但压缩矩阵、训练域和归一化顺序都会影响性能。

## 3. NetVLAD：让聚合本身服务于地点识别

### 3.1 先把硬边界变得可微

硬分配跨越聚类边界时会跳变，难以直接反向传播。以距离生成软分配：

$$
a_{ik}=\frac{\exp(-\alpha\|\mathbf x_i-\mathbf c_k\|^2)}
{\sum_{k'}\exp(-\alpha\|\mathbf x_i-\mathbf c_{k'}\|^2)}.
$$

展开平方，所有簇共有的 $-\alpha\|\mathbf x_i\|^2$ 抵消，得到

$$
a_{ik}=\operatorname{softmax}_k(\mathbf w_k^\top\mathbf x_i+b_k),\qquad
\mathbf V_k=\sum_i a_{ik}(\mathbf x_i-\mathbf c_k).
$$

最初可令 $\mathbf w_k=2\alpha\mathbf c_k$、$b_k=-\alpha\|\mathbf c_k\|^2$。NetVLAD 最终把 $\mathbf w_k,b_k,\mathbf c_k$ 作为独立可学习参数：分配边界和残差原点可以各自为任务调整。

<!-- vision-figure: netvlad-2 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-2.webp" width="1667" height="331" alt="NetVLAD 原论文 Figure 2：NetVLAD 的可微计算路径。卷积特征经软分配、残差聚合与归一化，所有可训练部分都能接收检索目标梯度。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 2 · NetVLAD 的可微计算路径。卷积特征经软分配、残差聚合与归一化，所有可训练部分都能接收检索目标梯度。 <a href="https://arxiv.org/pdf/1511.07247v3#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: netvlad-3 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-3.webp" width="813" height="292" alt="NetVLAD 原论文 Figure 3：同一簇内的残差内积影响图像相似性。学习簇中心和分配可改变哪些局部变化被保留。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 3 · 同一簇内的残差内积影响图像相似性。学习簇中心和分配可改变哪些局部变化被保留。 <a href="https://arxiv.org/pdf/1511.07247v3#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 2 中的 $1\times1$ 卷积产生每个空间位置对各簇的分数；softmax 沿簇维归一化，不沿像素位置归一化。Figure 3 则解释为什么学习残差原点有意义：即使局部描述仍落在同一个词格，移动参考原点也能改变两张图聚合向量的相似度。

NetVLAD 层能聚合 CNN 的稠密特征，不要求先检测稀疏关键点。这里的“局部”指特征图位置的感受野，不能直接当成可用于 PnP 的精确像素坐标。

### 3.2 地理位置近，不等于图像一定看向同一处

Google Street View 的位置和时间信息提供弱监督。同一个路口朝四个方向拍摄，GPS 很近，却未必有共同视野。因此对查询 $q$，论文构造可能正样本集合 $\mathcal P_q$ 与地理上足够远的负样本集合 $\mathcal N_q$，在可能正样本中选择当前最接近者：

$$
p^*=\arg\min_{p\in\mathcal P_q}\|f(q)-f(p)\|_2^2.
$$

再以排序损失训练：

$$
\mathcal L=\sum_{n\in\mathcal N_q}
\left[m+\|f(q)-f(p^*)\|_2^2-\|f(q)-f(n)\|_2^2\right]_+.
$$

假设正距离平方 0.4、负距离平方 0.5、间隔 0.2，则损失为 0.1；负距离变成 0.9 时损失为零。梯度推动最接近的潜在正样本更近、困难负样本更远，而不是把地理邻域里所有方向都强行压到一起。

<!-- vision-figure: netvlad-1 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-1.webp" width="813" height="338" alt="NetVLAD 原论文 Figure 1：夜间查询与白天数据库图像。地点识别需要跨照明、遮挡与视角保持全局描述的一致性。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 1 · 夜间查询与白天数据库图像。地点识别需要跨照明、遮挡与视角保持全局描述的一致性。 <a href="https://arxiv.org/pdf/1511.07247v3#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: netvlad-4 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-4.webp" width="813" height="634" alt="NetVLAD 原论文 Figure 4：Street View Time Machine 的近地点跨时刻图像。GPS 邻近提供弱标签，但不保证每一对都共享可见内容。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 4 · Street View Time Machine 的近地点跨时刻图像。GPS 邻近提供弱标签，但不保证每一对都共享可见内容。 <a href="https://arxiv.org/pdf/1511.07247v3#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: retrieval-supervision -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/retrieval-supervision.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/retrieval-supervision.svg" width="1100" height="470" alt="自制图 3：NetVLAD 的弱监督不把所有 GPS 邻近照片都视作必然正对；视角不重叠的近邻可能不适合作为正样本。" loading="lazy" /></a>
  <figcaption>自制图 3 · NetVLAD 的弱监督不把所有 GPS 邻近照片都视作必然正对；视角不重叠的近邻可能不适合作为正样本。</figcaption>
</figure>
<!-- /vision-figure -->

这仍可能选到错误潜在正样本，因此数据覆盖、时间变化和困难负样本挖掘很重要。它是弱监督，不是完全不需要地点信息的训练；后面的 AnyLoc 才会进一步讨论无需 VPR 任务监督的聚合路径。

### 3.3 原论文实验说明“训练什么”与“如何聚合”都重要

<!-- vision-figure: netvlad-5 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-5.webp" width="1667" height="500" alt="NetVLAD 原论文 Figure 5：训练表示与现成分类特征在地点识别上的对比。读曲线时同时看骨干、聚合方式和候选数量。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 5 · 训练表示与现成分类特征在地点识别上的对比。读曲线时同时看骨干、聚合方式和候选数量。 <a href="https://arxiv.org/pdf/1511.07247v3#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 5 用多组 Recall 曲线比较现成分类特征、地点训练特征与不同聚合。横轴允许返回更多候选时，成功率自然更高；R@1 与 R@20 回答的是不同搜索预算下的问题。

<!-- vision-figure: netvlad-6 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-6.webp" width="841" height="485" alt="NetVLAD 原论文 Figure 6：遮挡敏感性热图展示哪些区域影响表征。它不是注意力权重；每个值来自遮住对应区域后表示发生的变化。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 6 · 遮挡敏感性热图展示哪些区域影响表征。它不是注意力权重；每个值来自遮住对应区域后表示发生的变化。 <a href="https://arxiv.org/pdf/1511.07247v3#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 6 的颜色来自遮挡敏感性：遮住某块区域，再测量描述向量改变多少。这不是 Transformer attention。建筑区域影响增大与地点识别目标相符，但热图仍只是对当前模型行为的局部探测。

<!-- vision-figure: netvlad-8 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-8.webp" width="813" height="375" alt="NetVLAD 原论文 Figure 8：维度与检索性能的折中，横轴为对数尺度。白化和降维可以节省数据库存储，但低维收益应按同一协议判断。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 8 · 维度与检索性能的折中，横轴为对数尺度。白化和降维可以节省数据库存储，但低维收益应按同一协议判断。 <a href="https://arxiv.org/pdf/1511.07247v3#page=12" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 8 明确把描述维度放在横轴，检查压缩后的性能。高维向量的收益要与数据库内存、近邻索引和带宽一起估计；不能给两种方法不同存储预算，却只把差异归因于架构。

这些结果从召回、表示维度和任务迁移等角度比较方法。读性能变化时应区分两个变量：基础 CNN 是否经过地点识别训练，以及聚合采用 max pooling 还是 NetVLAD。不能把联合训练的收益全部归给一个 softmax 层，也不能把压缩后的表示与未压缩方法混为同一存储预算。

### 3.4 附录补足数据多样性与失败边界

<!-- vision-figure: netvlad-7 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-7.webp" width="1667" height="679" alt="NetVLAD 原论文 Figure 7：更多跨时间、视角与遮挡的训练候选。植被、车辆和行人说明需要抑制随时间变化的干扰。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 7 · 更多跨时间、视角与遮挡的训练候选。植被、车辆和行人说明需要抑制随时间变化的干扰。 <a href="https://arxiv.org/pdf/1511.07247v3#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: netvlad-9 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-9.webp" width="1667" height="639" alt="NetVLAD 原论文 Figure 9：更多遮挡敏感性热图。不同网络依赖区域不同，较强的建筑响应提供解释线索，但不能单独证明因果。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 9 · 更多遮挡敏感性热图。不同网络依赖区域不同，较强的建筑响应提供解释线索，但不能单独证明因果。 <a href="https://arxiv.org/pdf/1511.07247v3#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

更多 Time Machine 图像与遮挡热图，让我们检验网络面对行人、车辆、植被时关注什么。不同时间拍到同一处不意味着所有局部区域都稳定，训练必须学会抑制变化证据。

<!-- vision-figure: netvlad-10 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-10.webp" width="1667" height="1826" alt="NetVLAD 原论文 Figure 10：多数据集完整检索曲线。分别比较相同骨干和表示维度，不把不同条件的最高点合成一个结论。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 10 · 多数据集完整检索曲线。分别比较相同骨干和表示维度，不把不同条件的最高点合成一个结论。 <a href="https://arxiv.org/pdf/1511.07247v3#page=15" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 10 的完整曲线按数据集和骨干分别报告结果。应在同一个子图、相同候选数下读差异，而不是把不同数据集的最高点合在一起。

<!-- vision-figure: netvlad-11 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-11.webp" width="1667" height="1726" alt="NetVLAD 原论文 Figure 11：Tokyo 24/7 的查询、NetVLAD 返回与传统基线返回；绿色边框为正确，红色为错误。跨昼夜也有明显失败列。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 11 · Tokyo 24/7 的查询、NetVLAD 返回与传统基线返回；绿色边框为正确，红色为错误。跨昼夜也有明显失败列。 <a href="https://arxiv.org/pdf/1511.07247v3#page=16" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: netvlad-12 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/netvlad-12.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/netvlad-12.webp" width="1667" height="850" alt="NetVLAD 原论文 Figure 12：额外困难检索样本保留了不利案例。外观变化和可见结构不足仍可能使最相似向量对应错误地点。" loading="lazy" /></a>
  <figcaption>NetVLAD 原论文 Figure 12 · 额外困难检索样本保留了不利案例。外观变化和可见结构不足仍可能使最相似向量对应错误地点。 <a href="https://arxiv.org/pdf/1511.07247v3#page=17" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

附录保留更多数据和检索案例，让“相似外观”和“同一地点”之间的差异更可见。正确地点可能因遮挡、方向或夜景排在后面；错误地点也可能因为重复立面得高分。向量排序只能提出假设，后续仍需验证。

## 4. HF-Net：共享计算，但不要求三个头学同一种东西

如果每帧分别跑 NetVLAD 和 SuperPoint，主干计算重复。HF-Net 用 MobileNet 共享一部分特征提取，输出三个对象：全局描述子、关键点分数、局部描述子图。

<!-- vision-figure: hfnet-2 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-2.webp" width="813" height="479" alt="HF-Net 原论文 Figure 2：HF-Net 层次定位的模块与运行成本。沿图看检索、局部匹配和位姿估计，而不是把它当成单网络直接回归位姿。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 2 · HF-Net 层次定位的模块与运行成本。沿图看检索、局部匹配和位姿估计，而不是把它当成单网络直接回归位姿。 <a href="https://arxiv.org/pdf/1812.03506v2#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: hfnet-3 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-3.webp" width="813" height="524" alt="HF-Net 原论文 Figure 3：一个共享骨干产生全局描述、局部分数和局部描述图。三个头接受不同教师的联合蒸馏。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 3 · 一个共享骨干产生全局描述、局部分数和局部描述图。三个头接受不同教师的联合蒸馏。 <a href="https://arxiv.org/pdf/1812.03506v2#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: hfnet-6 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-6.webp" width="813" height="669" alt="HF-Net 原论文 Figure 6：MobileNet 骨干和三个头的细节。局部输出与全局输出在不同分辨率上处理，避免把全部任务强压到同一张特征图。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 6 · MobileNet 骨干和三个头的细节。局部输出与全局输出在不同分辨率上处理，避免把全部任务强压到同一张特征图。 <a href="https://arxiv.org/pdf/1812.03506v2#page=9" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

局部头较早分叉，因为需要更高空间分辨率；全局头继续向深层走，再经 NetVLAD 聚合。检测和局部描述解码借鉴 SuperPoint。网络输出稠密分数和描述图，之后才做筛点、NMS 和描述子采样。

三个头共享编码器不代表它们的目标没有冲突。地点识别希望对局部细节变化稳健，精确点匹配却要区分相邻的两个窗角。分支位置和网络容量就是对这组矛盾的具体处理。

## 5. 多任务蒸馏：不用凑齐一种同时拥有全部标签的数据

### 5.1 三个学生输出，分别跟随对应教师

局部与全局任务需要的监督不同。大规模地点图像不容易拥有精确像素对应；局部几何增强又可能破坏全局场景的自然性。HF-Net 用已训练的全局、局部教师为同一张图片提供目标。

记学生和教师的全局描述为 $\mathbf d_s^g,\mathbf d_t^g$，局部描述图为 $D_s^l,D_t^l$，检测分布为 $p_s,p_t$。原文目标为

$$
\mathcal L=e^{-w_1}\|\mathbf d_s^g-\mathbf d_t^g\|_2^2
+e^{-w_2}\|D_s^l-D_t^l\|_2^2
+2e^{-w_3}\operatorname{CE}(p_t,p_s)
+\sum_{i=1}^3w_i.
$$

这里明确用 $\operatorname{CE}(p_t,p_s)=-\sum_c p_t(c)\log p_s(c)$，避免不同库的参数顺序造成歧义。局部描述项的空间采样、归一化及平均方式必须与作者实现相同才能复现权重。检测头是学习教师的类别分布，不能随意改成对筛点后坐标做欧氏回归。

<!-- vision-figure: hfnet-distillation -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-distillation.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-distillation.svg" width="1100" height="470" alt="自制图 4：共享骨干服务三个不同粒度的输出；虚线表示训练监督，推理只运行学生网络。" loading="lazy" /></a>
  <figcaption>自制图 4 · 共享骨干服务三个不同粒度的输出；虚线表示训练监督，推理只运行学生网络。</figcaption>
</figure>
<!-- /vision-figure -->

单位归一化描述子的平方距离满足 $\|\mathbf a-\mathbf b\|^2=2-2\mathbf a^\top\mathbf b$，所以蒸馏也可理解为对齐方向。一个学生检测分布若把教师的高概率位置分给别处，会受到交叉熵惩罚；dustbin 的语义则对应没有检测点的 cell。

### 5.2 可学习权重不是“模型自己宣布困难任务不重要”

$w_i$ 是要共同优化的标量。对一个固定正损失 $L_i$，$e^{-w_i}L_i+w_i$ 的导数为 $-e^{-w_i}L_i+1$。若试图把权重压到零，$w_i$ 本身会增长并产生代价，不能无成本丢掉一个任务。

这是一种基于不确定性建模的任务平衡方式，不会创造教师没有的能力，也不保证三个任务都达到各自独立大网络的最优值。学生容量不够时，蒸馏仍会损失信息。

## 6. 检索之后：共视聚类到底在做什么

### 6.1 不是把 top-K 图片平均成一个位姿

SfM 地图记录关键帧、三维点及观测关系。两张数据库图共同看到三维点，就在共视图中有关联。检索的 top-$K$ 可能混有几个相似但不同的地点，HF-Net 用共视关系把它们聚成候选地点，随后分别尝试定位。

<!-- vision-figure: covisibility-retrieval -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/covisibility-retrieval.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/covisibility-retrieval.svg" width="1100" height="470" alt="自制图 5：共视聚类把检索出的图像按地图连接分组，防止将外观相似但空间不同的候选混入同一次位姿估计。" loading="lazy" /></a>
  <figcaption>自制图 5 · 共视聚类把检索出的图像按地图连接分组，防止将外观相似但空间不同的候选混入同一次位姿估计。</figcaption>
</figure>
<!-- /vision-figure -->

这样做既限制局部搜索范围，又避免把多个错误地点的点混为一大团。聚类所用的连通关系来自三维地图，和全局描述子距离不是同一种边。数据库图没有可靠三维观测时，只有检索向量还不够构成 HF-Net 所需的几何地图。

### 6.2 从 2D–2D 匹配继承到 2D–3D 关联

查询点 $\mathbf u_i$ 与数据库图中的局部描述匹配；数据库观测若关联地图点 $\mathbf X_j$，便形成候选 $(\mathbf u_i,\mathbf X_j)$。应合并同一地图点的重复观测，处理一个查询点被赋给多个不一致地图点的情况。

用 PnP-RANSAC 求位姿，再优化重投影：

$$
\widehat T_{CW}=\arg\min_{T_{CW}}\sum_{(i,j)\in\mathcal I}
\rho\!\left(\|\mathbf u_i-\pi\!\left(K\begin{bmatrix}I_3&0\end{bmatrix}T_{CW}\widetilde{\mathbf X}_j\right)\|_{\Sigma_i^{-1}}^2\right).
$$

$T_{CW}$ 是世界到相机的齐次变换，$[I_3\;0]$ 取前三维，$\pi(x,y,z)=(x/z,y/z)$，$\mathcal I$ 是通过验证的观测集合。这个优化若固定地图点，只优化一个查询相机，是位姿细化；同时优化多相机和地图点才是通常意义的 BA。

这里的米制精度依赖地图本身的尺度。仅用单目 SfM 建图且没有外部尺度时，PnP 返回的是该地图坐标系里的位姿，不能凭网络输出自动变成米。

## 7. 教师、学生和整条管线，要分别评价

### 7.1 最终位姿的误差曲线

<!-- vision-figure: hfnet-4 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-4.webp" width="1667" height="391" alt="HF-Net 原论文 Figure 4：Aachen、RobotCar 和 CMU 的位置误差累积分布。RobotCar 上学生落后于组合教师，提示蒸馏在困难条件下仍有损失。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 4 · Aachen、RobotCar 和 CMU 的位置误差累积分布。RobotCar 上学生落后于组合教师，提示蒸馏在困难条件下仍有损失。 <a href="https://arxiv.org/pdf/1812.03506v2#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: hfnet-5 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-5.webp" width="813" height="625" alt="HF-Net 原论文 Figure 5：Aachen 昼夜定位成功例，左侧查询与右侧最多内点的数据库图像对应。成功需要检索和局部几何两环同时通过。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 5 · Aachen 昼夜定位成功例，左侧查询与右侧最多内点的数据库图像对应。成功需要检索和局部几何两环同时通过。 <a href="https://arxiv.org/pdf/1812.03506v2#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 4 的位置误差累计曲线显示 HF-Net 接近大教师组合，但在 RobotCar 夜间条件下仍有差距。论文将其中问题与模糊、低质量夜景下蒸馏的全局描述子不足联系起来。这里不能仅凭局部匹配图好看就说系统定位已解决：全局检索失败会直接截断后续几何验证。

### 7.2 局部特征的可重复性与空间覆盖

<!-- vision-figure: hfnet-7 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-7.webp" width="1667" height="788" alt="HF-Net 原论文 Figure 7：HPatches 上的关键点重复性和匹配。绿色为可重复点、红色为不可重复点、蓝色为另一图不可见点，不能把蓝点当误检。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 7 · HPatches 上的关键点重复性和匹配。绿色为可重复点、红色为不可重复点、蓝色为另一图不可见点，不能把蓝点当误检。 <a href="https://arxiv.org/pdf/1812.03506v2#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: hfnet-8 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-8.webp" width="1284" height="833" alt="HF-Net 原论文 Figure 8：SfM 图像对中 SIFT、SuperPoint、HF-Net 的局部结果。视角与纹理分布变化会改变可用对应的空间覆盖。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 8 · SfM 图像对中 SIFT、SuperPoint、HF-Net 的局部结果。视角与纹理分布变化会改变可用对应的空间覆盖。 <a href="https://arxiv.org/pdf/1812.03506v2#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

这两张附录图检查平面基准和三维场景下的局部表现。重复率、定位误差、描述子匹配和最终位姿是不同指标。点较多或重复率高，不保证定位最精确；相邻点偏移可能在远距离地图里被放大。

### 7.3 将检索失败和几何失败分开诊断

<!-- vision-figure: hfnet-9 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-9.webp" width="1667" height="496" alt="HF-Net 原论文 Figure 9：Aachen 夜间的成功、检索失败和局部匹配失败分别列出。先判断候选是否正确，再判断是否有足够几何内点。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 9 · Aachen 夜间的成功、检索失败和局部匹配失败分别列出。先判断候选是否正确，再判断是否有足够几何内点。 <a href="https://arxiv.org/pdf/1812.03506v2#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: hfnet-10 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-10.webp" width="1667" height="832" alt="HF-Net 原论文 Figure 10：RobotCar 夜间和雨夜案例。错误全局检索与候选正确但局部对应不足是两种不同失败。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 10 · RobotCar 夜间和雨夜案例。错误全局检索与候选正确但局部对应不足是两种不同失败。 <a href="https://arxiv.org/pdf/1812.03506v2#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: hfnet-11 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-11.webp" width="1667" height="658" alt="HF-Net 原论文 Figure 11：CMU 郊区定位中的光照与植被变化。检索命中也可能因局部特征不足而无法给出位姿。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 11 · CMU 郊区定位中的光照与植被变化。检索命中也可能因局部特征不足而无法给出位姿。 <a href="https://arxiv.org/pdf/1812.03506v2#page=15" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: hfnet-12 -->
<figure>
  <a href="/HomepageX/media/netvlad-hfnet/hfnet-12.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/netvlad-hfnet/hfnet-12.webp" width="1667" height="262" alt="HF-Net 原论文 Figure 12：同一夜间查询的 HF-Net 与 NetVLAD+SIFT 对比。看 PnP 内点和全部匹配的差别，原始连线数量不是最终定位依据。" loading="lazy" /></a>
  <figcaption>HF-Net 原论文 Figure 12 · 同一夜间查询的 HF-Net 与 NetVLAD+SIFT 对比。看 PnP 内点和全部匹配的差别，原始连线数量不是最终定位依据。 <a href="https://arxiv.org/pdf/1812.03506v2#page=15" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Aachen、RobotCar 和 CMU 的例子分别包含夜间、夜雨和季节性变化。Figure 12 放大一个 HF-Net 成功、NetVLAD+SIFT 失败的查询，比较 PnP 内点与所有候选连线。它解释这个案例的差异，不能单独支持所有条件下的胜负判断。

部署评估至少要记录四段时间：网络特征提取、全局检索、候选局部匹配、几何验证。一个轻网络不保证整个大数据库系统更快；候选数量、地图点密度、索引和 CPU/GPU 搬运都可能成为瓶颈。

## 8. HF-Net 留下的思路，比某个主干更长久

NetVLAD 让聚合和局部表示共同为地点任务优化；HF-Net 则让全局候选生成和局部几何验证共享一次特征提取，并借助教师解决多任务标签难以共存的问题。

后来换成 DINOv2、SALAD 或其他全局描述子，分层定位的因果顺序仍然成立：先检索，再构造精确关联，再求位姿。全局向量可以换，几何证据的职责不能省略。

继续阅读：[DINOv2 / DINOv3 的训练](/HomepageX/blog/sparse-feature-and-visual-recognition/dinov2-dinov3/)与[基础模型怎样改变 VPR 和局部特征](/HomepageX/blog/sparse-feature-and-visual-recognition/foundation-model-vpr-features/)。
