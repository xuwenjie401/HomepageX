---
title: "基础模型之后，VPR 与局部特征究竟改变了什么：五篇值得拆开的工作"
description: "围绕 AnyLoc、SALAD、SelaVPR、DeDoDe 与 RoMa，比较冻结特征、可训练聚合、任务适配、三维轨迹监督和粗到细几何匹配。"
date: 2026-09-26
tags: [论文精读, 基础模型, VPR, 局部特征]
---

[DINOv2 / DINOv3](/HomepageX/blog/sparse-feature-and-visual-recognition/dinov2-dinov3/)让一个通用骨干在没有地点标签或像素对应标签的预训练中，获得相当强的视觉关系。于是研究问题发生变化：以前常问“怎样从头训练更好的特征”，现在还要问“已有表示缺少哪一层任务结构，应该冻结、适配，还是补一套几何监督”。

本文选五条互补路线精读：AnyLoc 说明冻结特征可以走多远；SALAD 改聚合和任务适配；SelaVPR 用全局与局部两级适配；DeDoDe 重新组织稀疏检测和描述的监督；RoMa 则显示稠密匹配如何结合通用语义与精细定位。它们代表有解释力、可落地的设计选择，**不是把不同年份、不同协议的成绩混成“统一最好”排行榜**。

## 1. 先区分三类输出，才能讨论谁能替换谁

| 任务 | 输出 | 成功标准 |
| --- | --- | --- |
| VPR | 每图一个全局向量、地点候选排序 | 正确地点进入 top-K |
| 稀疏检测与描述 | 点坐标、分数、每点描述子 | 重复检测、精确定位和可匹配性 |
| 稠密匹配 | 图像间 warp、对应置信度 | 广覆盖且准确的对应，最终几何成功 |

从 RoMa 采样 1000 对点，不代表 RoMa 变成独立的稀疏检测器；从 DINO 特征图取一个 patch 向量，也不代表那个 patch 中心具备角点的亚像素定位性质。稀疏描述子可离线存入地图，成对匹配网络则通常依赖另一张图后才能产出对应，系统成本不同。

<!-- vision-figure: foundation-task-map -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/foundation-task-map.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/foundation-task-map.svg" width="1100" height="470" alt="自制图 1：基础模型特征可以服务三个不同接口；全局检索、独立局部描述和成对匹配的计算与缓存成本不同。" loading="lazy" /></a>
  <figcaption>自制图 1 · 基础模型特征可以服务三个不同接口；全局检索、独立局部描述和成对匹配的计算与缓存成本不同。</figcaption>
</figure>
<!-- /vision-figure -->

一条反复出现的矛盾是：**语义稳健性希望忽略变化，几何定位却依赖精确差异。** 两个不同的门可以语义极相似，却绝不能作为同一个地图点合并。

## 2. AnyLoc：不重训骨干，能否跨到训练集以外的环境

> [AnyLoc: Towards Universal Visual Place Recognition，arXiv:2308.00688v2](https://arxiv.org/abs/2308.00688v2)，[作者代码](https://github.com/AnyLoc/AnyLoc)。

### 2.1 Insight：瓶颈可能是预训练任务与聚合，而不是缺少一个 VPR 标签集

城市驾驶训练出的地点描述子，到了洞穴、空中、海底可能失效。AnyLoc 从预训练 DINO/DINOv2 等模型提取稠密特征，研究层、attention facet 和聚合方式，再用无监督 VLAD 得到全局表示。

<!-- vision-figure: anyloc-1 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/anyloc-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/anyloc-1.webp" width="1697" height="490" alt="AnyLoc 原论文 Figure 1：跨室内、城市、自然和其他域的统一检索思路。主张是冻结基础特征加无监督聚合的可迁移性。" loading="lazy" /></a>
  <figcaption>AnyLoc 原论文 Figure 1 · 跨室内、城市、自然和其他域的统一检索思路。主张是冻结基础特征加无监督聚合的可迁移性。 <a href="https://arxiv.org/pdf/2308.00688v2#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: anyloc-2 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/anyloc-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/anyloc-2.webp" width="842" height="336" alt="AnyLoc 原论文 Figure 2：冻结特征的余弦相似度图。跨视图的显著结构提供地点信息，但语义相似仍可能引发重复地点混淆。" loading="lazy" /></a>
  <figcaption>AnyLoc 原论文 Figure 2 · 冻结特征的余弦相似度图。跨视图的显著结构提供地点信息，但语义相似仍可能引发重复地点混淆。 <a href="https://arxiv.org/pdf/2308.00688v2#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

对当前图像的 $N$ 个描述子 $\mathbf x_i$，

$$
\mathbf V_k=\sum_{i=1}^{N}a_{ik}(\mathbf x_i-\mathbf c_k).
$$

词典 $\mathbf c_k$ 可从数据库或相关领域特征中无监督聚类学习。**聚类时汇总许多图像，描述单张图时只汇总当前图像**，这两个求和范围不能混用。归一化后的向量用于近邻检索。

AnyLoc 的“无需 VPR 微调”不等于“没有任何数据适配”。选择模型层、构建领域词典，都在利用数据分布。实验需说明词典来自哪里，尤其不能用查询真值挑选词典后还当成完全未知域评估。

### 2.2 为什么不直接取 CLS token

CLS 适合概括整图，但不一定保留地点级区分所需的局部构成。VLAD 将多个局部语义残差组成一个整体，能表达“有什么，以及在该视觉词附近偏向哪里”。它仍然是无序统计，无法保证重复街区的几何排列不同就一定可分。

<!-- vision-figure: anyloc-3 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/anyloc-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/anyloc-3.webp" width="841" height="385" alt="AnyLoc 原论文 Figure 3：更多区域对应展示基础特征的跨外观稳定性。高响应不等于已获得精确几何坐标。" loading="lazy" /></a>
  <figcaption>AnyLoc 原论文 Figure 3 · 更多区域对应展示基础特征的跨外观稳定性。高响应不等于已获得精确几何坐标。 <a href="https://arxiv.org/pdf/2308.00688v2#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

词典大小、层和 facet 的消融不是零碎调参：它们揭示预训练内部表示并不均质。不同层可能在语义、纹理和空间细节之间有不同平衡，因此“用了 DINOv2”并不足以复现一个方法。

<!-- vision-figure: anyloc-4 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/anyloc-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/anyloc-4.webp" width="841" height="557" alt="AnyLoc 原论文 Figure 4：不同环境中的特征聚类可视化。视觉域改变时词典的使用分布会变，词典数据选择需要单独考察。" loading="lazy" /></a>
  <figcaption>AnyLoc 原论文 Figure 4 · 不同环境中的特征聚类可视化。视觉域改变时词典的使用分布会变，词典数据选择需要单独考察。 <a href="https://arxiv.org/pdf/2308.00688v2#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: anyloc-5 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/anyloc-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/anyloc-5.webp" width="1697" height="322" alt="AnyLoc 原论文 Figure 5：模型、层、facet 与词典等消融。冻结模型仍有关键配置，不是任选一个 token 平均就能得到同等结果。" loading="lazy" /></a>
  <figcaption>AnyLoc 原论文 Figure 5 · 模型、层、facet 与词典等消融。冻结模型仍有关键配置，不是任选一个 token 平均就能得到同等结果。 <a href="https://arxiv.org/pdf/2308.00688v2#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

论文覆盖结构化与非结构化环境。要注意不同数据集的正确地点半径差异很大，例如空中和海底的单位距离不具备同一难度含义，不能把各数据集 Recall 简单看成同一个物理精度。

**适合采用的情形：**新域缺少可靠地点标签，愿意用冻结强骨干换泛化性，允许词典学习与较大描述子。需要额外解决的是存储、维度压缩和端侧推理，不应把“无需训练”理解成“很便宜”。

## 3. SALAD：强特征已经有了，哪些 token 值得聚合

> [Optimal Transport Aggregation for Visual Place Recognition，CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/papers/Izquierdo_Optimal_Transport_Aggregation_for_Visual_Place_Recognition_CVPR_2024_paper.pdf)，[作者代码](https://github.com/serizba/salad)。

### 3.1 Insight：让聚合在选择证据的同时避免全部挤进少数簇

一张街景中，天空、车辆等区域可能缺少长期地点识别价值。NetVLAD 的逐 token softmax 仍让每个 token 分出全部质量，也没有控制一个簇总共拿到多少。SALAD 学习 token 对各簇的分数，再加一个 dustbin，以最优传输进行分配。

<!-- vision-figure: salad-1 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/salad-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/salad-1.webp" width="813" height="935" alt="SALAD 原论文 Figure 1：从 ResNet+NetVLAD 到 DINOv2+SALAD 的两处变化。最终性能不能只归因于新聚合头。" loading="lazy" /></a>
  <figcaption>SALAD 原论文 Figure 1 · 从 ResNet+NetVLAD 到 DINOv2+SALAD 的两处变化。最终性能不能只归因于新聚合头。 <a href="https://openaccess.thecvf.com/content/CVPR2024/papers/Izquierdo_Optimal_Transport_Aggregation_for_Visual_Place_Recognition_CVPR_2024_paper.pdf#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: salad-2 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/salad-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/salad-2.webp" width="1667" height="539" alt="SALAD 原论文 Figure 2：局部 token 与全局 token 的路径：分数预测、最优传输、降维和聚合。聚合输出没有 VLAD 的中心残差项。" loading="lazy" /></a>
  <figcaption>SALAD 原论文 Figure 2 · 局部 token 与全局 token 的路径：分数预测、最优传输、降维和聚合。聚合输出没有 VLAD 的中心残差项。 <a href="https://openaccess.thecvf.com/content/CVPR2024/papers/Izquierdo_Optimal_Transport_Aggregation_for_Visual_Place_Recognition_CVPR_2024_paper.pdf#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: salad-transport -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/salad-transport.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/salad-transport.svg" width="1100" height="470" alt="自制图 2：数值矩阵满足 SALAD 的容量直觉。与 NetVLAD 不同，SALAD 对降维后的特征加权求和，不聚合到中心的残差。" loading="lazy" /></a>
  <figcaption>自制图 2 · 数值矩阵满足 SALAD 的容量直觉。与 NetVLAD 不同，SALAD 对降维后的特征加权求和，不聚合到中心的残差。</figcaption>
</figure>
<!-- /vision-figure -->

设 $n$ 个 token、$m$ 个保留簇，扩展分配矩阵 $\overline P\in\mathbb R_+^{n\times(m+1)}$ 满足

$$
\overline P\mathbf1=\mathbf1_n,\qquad
\overline P^\top\mathbf1=(1,\ldots,1,n-m)^\top.
$$

每个 token 有 1 单位质量，每个保留簇收到 1，剩余 $n-m$ 送往 dustbin。这个设定需要 $n\ge m$；分辨率与 patch 数变化时不能忽略它。软分配可以把一个 token 的质量分到多个簇，不能把图画成严格挑出恰好 $m$ 个完整 token。

删掉 dustbin 后，降维特征 $\mathbf f_i\in\mathbb R^l$ 被直接聚合：

$$
\mathbf V_j=\sum_{i=1}^{n}P_{ij}\mathbf f_i.
$$

**SALAD 不减聚类中心，因而不是只给 NetVLAD 换一个 softmax。** 再把聚合矩阵归一化、展开，与 CLS 投影 $\mathbf g$ 拼接，得到全局向量。

### 3.2 任务监督让强表示重新关注地点

论文微调 DINOv2-B 的最后四个 block，并训练聚合头，使用 GSV-Cities 地点分组与 multi-similarity loss。用一组 anchor 的相似度 $s_{ip}$、$s_{in}$ 表示，其典型形式为

$$
\mathcal L_i=\frac1\alpha\log\!\left(1+\sum_{p\in\mathcal P_i}e^{-\alpha(s_{ip}-\lambda)}\right)
+\frac1\beta\log\!\left(1+\sum_{n\in\mathcal N_i}e^{\beta(s_{in}-\lambda)}\right).
$$

弱正样本、强负样本贡献更大；集合包含挖掘选择，不能将它解释成均匀处理全部配对。此处展示损失的职责，复现应使用作者代码的采样和参数。

### 3.3 一个直接影响部署的数字：8448 维

论文默认 $m=64,l=128$，CLS 投影 256 维，故总维度 $64\times128+256=8448$。一百万张图用 float32 原始存储约 33.8 GB，尚未计索引；不能只看提取时间就说可直接塞入嵌入式设备。

CVPR 论文同一 Table 1 中，8448 维版本在 MSLS Challenge 的 R@1 为 75.0，较紧凑的 2112 维版本为 73.7。这里是同论文的维度折中证据，不是与所有后续方法的当前排名比较。

<!-- vision-figure: salad-3 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/salad-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/salad-3.webp" width="1667" height="556" alt="SALAD 原论文 Figure 3：未被 dustbin 丢弃的质量热图。网络倾向保留可识别结构，但植被也可能在某些地点提供区分线索。" loading="lazy" /></a>
  <figcaption>SALAD 原论文 Figure 3 · 未被 dustbin 丢弃的质量热图。网络倾向保留可识别结构，但植被也可能在某些地点提供区分线索。 <a href="https://openaccess.thecvf.com/content/CVPR2024/papers/Izquierdo_Optimal_Transport_Aggregation_for_Visual_Place_Recognition_CVPR_2024_paper.pdf#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 3 的热图显示送往 dustbin 的区域，天空等弱地点证据常被减弱。它是学习结果的可视化，不是人工语义掩码：车辆、树木是否被排除仍取决于上下文与训练。

<!-- vision-figure: salad-4 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/salad-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/salad-4.webp" width="1667" height="589" alt="SALAD 原论文 Figure 4：同地点不同视图的 patch 到簇分配。红蓝框帮助追踪对应区域是否获得相似归属，不表示簇具有固定人工类别。" loading="lazy" /></a>
  <figcaption>SALAD 原论文 Figure 4 · 同地点不同视图的 patch 到簇分配。红蓝框帮助追踪对应区域是否获得相似归属，不表示簇具有固定人工类别。 <a href="https://openaccess.thecvf.com/content/CVPR2024/papers/Izquierdo_Optimal_Transport_Aggregation_for_Visual_Place_Recognition_CVPR_2024_paper.pdf#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 4 比较同一地点不同视角中局部区域的簇分配。希望共享结构进入相容槽位，才能稳定聚合；槽位不必等于人工定义的“窗、树、路”类别。

<!-- vision-figure: salad-5 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/salad-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/salad-5.webp" width="1667" height="1268" alt="SALAD 原论文 Figure 5：MSLS 的 top-3 检索结果，绿色正确、红色错误。成功跨越天气与昼夜变化，仍有候选错误和排序失败。" loading="lazy" /></a>
  <figcaption>SALAD 原论文 Figure 5 · MSLS 的 top-3 检索结果，绿色正确、红色错误。成功跨越天气与昼夜变化，仍有候选错误和排序失败。 <a href="https://openaccess.thecvf.com/content/CVPR2024/papers/Izquierdo_Optimal_Transport_Aggregation_for_Visual_Place_Recognition_CVPR_2024_paper.pdf#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 5 同时保留检索成功和失败。最后几组相似道路、植被说明全局向量仍会受视觉混淆影响，因此 top-1 高召回不能取代回环几何验证。

消融和可视化要回答：收益来自 DINOv2、骨干微调，还是 OT 聚合？只比较完整方法与旧 CNN 系统，无法分离这些因素。保留原图可以同时看到性能和成本条件。

**适合采用的情形：**有可靠预训练权重，希望用成熟的全局检索管线迅速建立强基线；再依据数据库规模选择压缩与索引。检索后的几何验证仍然必要。

## 4. SelaVPR：不全部重训，也不完全冻结

> [SelaVPR，ICLR 2024，arXiv:2402.14505v2](https://arxiv.org/abs/2402.14505v2)，[作者代码](https://github.com/Lu-Feng/SelaVPR)。

### 4.1 Insight：全局检索和局部重排需要不同粒度

完全冻结可能保留通用语义但错过地点细节，全量微调又昂贵并可能损伤泛化。SelaVPR 在冻结主干中插入小 adapter，另用上采样模块生成更细的局部网格。

<!-- vision-figure: selavpr-1 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/selavpr-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/selavpr-1.webp" width="1340" height="357" alt="SelaVPR 原论文 Figure 1：适配前后的注意区域。目标是增强地点相关结构的利用，不是让原模型遗忘全部通用特征。" loading="lazy" /></a>
  <figcaption>SelaVPR 原论文 Figure 1 · 适配前后的注意区域。目标是增强地点相关结构的利用，不是让原模型遗忘全部通用特征。 <a href="https://arxiv.org/pdf/2402.14505v2#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: selavpr-2 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/selavpr-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/selavpr-2.webp" width="1340" height="525" alt="SelaVPR 原论文 Figure 2：串行与并行 adapter 在 Transformer 中的位置。冻结主干不等于完全没有任务参数更新。" loading="lazy" /></a>
  <figcaption>SelaVPR 原论文 Figure 2 · 串行与并行 adapter 在 Transformer 中的位置。冻结主干不等于完全没有任务参数更新。 <a href="https://arxiv.org/pdf/2402.14505v2#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: selavpr-3 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/selavpr-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/selavpr-3.webp" width="1340" height="393" alt="SelaVPR 原论文 Figure 3：全局检索与局部重排序。局部上采样特征通过匹配数量重排候选，尚未执行三维几何验证。" loading="lazy" /></a>
  <figcaption>SelaVPR 原论文 Figure 3 · 全局检索与局部重排序。局部上采样特征通过匹配数量重排候选，尚未执行三维几何验证。 <a href="https://arxiv.org/pdf/2402.14505v2#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

瓶颈 adapter 可抽象为 $A(\mathbf x)=W_{up}\sigma(W_{down}\mathbf x)$，先降维再升维。原文在注意力后串接带内部残差的 adapter，并在 MLP 路径旁加入缩放的并行 adapter，不是简单替换整个 Transformer。

全局端对 patch map 做 GeM 与归一化；局部端将 $16\times16\times1024$ 的网格经上卷积变成 $61\times61\times128$，用于候选重排序。网格更密表示预测的采样更密，**不等于骨干原本就观测到了独立的像素细节**。

### 4.2 重排指标不是严格的几何验证

对查询和候选图的局部特征，取互为最近邻集合 $\mathcal M$。原方法直接以 $|\mathcal M|$ 排序，而不在此阶段做 RANSAC。训练时不能直接对离散匹配数量求导，因此用正负图像对的平均匹配相似度差构造代理目标。

这对于地点候选排序可以有效，但**候选排名提高不能等同于所有互匹配都满足同一个 SE(3)**。将这些局部匹配用于建图、回环或 PnP 时，仍要验证几何。

<!-- vision-figure: selavpr-4 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/selavpr-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/selavpr-4.webp" width="1340" height="555" alt="SelaVPR 原论文 Figure 4：跨昼夜、天气和视角的定性检索。逐行看错误返回，避免只统计最好看的查询。" loading="lazy" /></a>
  <figcaption>SelaVPR 原论文 Figure 4 · 跨昼夜、天气和视角的定性检索。逐行看错误返回，避免只统计最好看的查询。 <a href="https://arxiv.org/pdf/2402.14505v2#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: selavpr-5 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/selavpr-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/selavpr-5.webp" width="467" height="379" alt="SelaVPR 原论文 Figure 5：特征提取、匹配和总耗时的比较。局部重排序成本随候选数变化，不能只报告全局向量前向。" loading="lazy" /></a>
  <figcaption>SelaVPR 原论文 Figure 5 · 特征提取、匹配和总耗时的比较。局部重排序成本随候选数变化，不能只报告全局向量前向。 <a href="https://arxiv.org/pdf/2402.14505v2#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

有重排的方法必须与只做单向量检索的方法分开计时、计存储。若 top-$K$ 每个候选都保存 3721 个 128 维局部特征，数据库和匹配成本远超只保存一个全局向量。

### 4.3 局部匹配数需要具备地点区分性

<!-- vision-figure: selavpr-6 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/selavpr-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/selavpr-6.webp" width="1340" height="855" alt="SelaVPR 原论文 Figure 6：适配局部特征与原始 DINOv2 的匹配对照。更多匹配有助于重排，但匹配数量并不保证满足相机几何。" loading="lazy" /></a>
  <figcaption>SelaVPR 原论文 Figure 6 · 适配局部特征与原始 DINOv2 的匹配对照。更多匹配有助于重排，但匹配数量并不保证满足相机几何。 <a href="https://arxiv.org/pdf/2402.14505v2#page=18" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: selavpr-7 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/selavpr-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/selavpr-7.webp" width="1340" height="1670" alt="SelaVPR 原论文 Figure 7：更多注意区域示例。适配后建筑结构与地点证据更突出，图中热度不是可校准定位置信度。" loading="lazy" /></a>
  <figcaption>SelaVPR 原论文 Figure 7 · 更多注意区域示例。适配后建筑结构与地点证据更突出，图中热度不是可校准定位置信度。 <a href="https://arxiv.org/pdf/2402.14505v2#page=19" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 6 对比同地点和异地点：真正需要拉开的不是“有没有相似特征”，而是两个集合之间能建立多少可信的一致对应。Figure 7 显示适配后的区域响应，说明通用语义如何转向地点结构。热图本身仍不能证明几何正确。

### 4.4 困难查询与评估范围

<!-- vision-figure: selavpr-8 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/selavpr-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/selavpr-8.webp" width="1340" height="629" alt="SelaVPR 原论文 Figure 8：Tokyo24/7 的额外查询。日夜与视角同时变化时应检查 top-1 是否真正覆盖同一地点。" loading="lazy" /></a>
  <figcaption>SelaVPR 原论文 Figure 8 · Tokyo24/7 的额外查询。日夜与视角同时变化时应检查 top-1 是否真正覆盖同一地点。 <a href="https://arxiv.org/pdf/2402.14505v2#page=20" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: selavpr-9 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/selavpr-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/selavpr-9.webp" width="1340" height="511" alt="SelaVPR 原论文 Figure 9：MSLS 的额外查询，包含明显困难返回。全局近邻结果仍受动态遮挡和外观重复影响。" loading="lazy" /></a>
  <figcaption>SelaVPR 原论文 Figure 9 · MSLS 的额外查询，包含明显困难返回。全局近邻结果仍受动态遮挡和外观重复影响。 <a href="https://arxiv.org/pdf/2402.14505v2#page=20" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 8 的 Tokyo24/7 关注光照与视角，Figure 9 的 MSLS 还包括植被、强背光及夜间。对照绿色正确候选与红色错误候选，观察方法是否真的认出同一位置，而不是仅返回同类场景。

<!-- vision-figure: selavpr-10 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/selavpr-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/selavpr-10.webp" width="1298" height="448" alt="SelaVPR 原论文 Figure 10：Pitts30k 的额外查询。最后一行的重复结构说明地点相似与地点相同之间仍有差距。" loading="lazy" /></a>
  <figcaption>SelaVPR 原论文 Figure 10 · Pitts30k 的额外查询。最后一行的重复结构说明地点相似与地点相同之间仍有差距。 <a href="https://arxiv.org/pdf/2402.14505v2#page=20" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 10 中天空占了很大面积，关键地点线索反而很小。这是自适应关注与固定平均聚合的直接矛盾：多数像素不一定携带多数定位信息。

<!-- vision-figure: selavpr-11 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/selavpr-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/selavpr-11.webp" width="1340" height="715" alt="SelaVPR 原论文 Figure 11：论文当时的 MSLS 排行榜快照，仅用于记录实验背景；不是 2026 年的实时排名。" loading="lazy" /></a>
  <figcaption>SelaVPR 原论文 Figure 11 · 论文当时的 MSLS 排行榜快照，仅用于记录实验背景；不是 2026 年的实时排名。 <a href="https://arxiv.org/pdf/2402.14505v2#page=22" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 11 是作者提交时的挑战榜单截图，只作为论文当时的实验记录；其排序不表示今天的榜单状态，也不允许忽略挑战集的具体协议。

附录的重排、适配与可视化分析帮助检查这种成本是否换来目标域中的稳定收益。重点观察首轮正确候选已经存在、但排名较低的查询：这是重排最能发挥作用的条件；正确地点未进入 top-$K$ 时，局部重排无从寻找它。

## 5. DeDoDe：稀疏点的问题，不只是把 descriptor 换成 DINO

> [DeDoDe: Detect, Don't Describe — Describe, Don't Detect，3DV 2024](https://arxiv.org/abs/2308.08479v1)，[作者代码](https://github.com/Parskatt/DeDoDe)。

### 5.1 Insight：检测与描述解耦，但用三维关联对齐目标

一个重复窗角定位准确却不独特；一块独特但平滑的彩色区域容易认，却不好精确定位。让检测分数简单等于描述子的“好匹配程度”，会混淆这两个目标。

DeDoDe 从经过 SfM 重建保留下来的三维 tracks 构造检测先验。这里的监督不是“DINO 告诉你哪些点是角点”，而是：哪些观测在多视图几何重建中形成了一致轨迹。

<!-- vision-figure: dedode-1 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/dedode-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/dedode-1.webp" width="813" height="668" alt="DeDoDe 原论文 Figure 1：独立检测/描述与完整匹配网络之间的差距。论文强调分离训练仍有潜力，而不是证明成对上下文永远没有价值。" loading="lazy" /></a>
  <figcaption>DeDoDe 原论文 Figure 1 · 独立检测/描述与完整匹配网络之间的差距。论文强调分离训练仍有潜力，而不是证明成对上下文永远没有价值。 <a href="https://arxiv.org/pdf/2308.08479v1#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dedode-2 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/dedode-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/dedode-2.webp" width="1667" height="349" alt="DeDoDe 原论文 Figure 2：与联合检测描述方案的定性匹配对比。检查大视角下点的位置及连线，不能只按密度判断质量。" loading="lazy" /></a>
  <figcaption>DeDoDe 原论文 Figure 2 · 与联合检测描述方案的定性匹配对比。检查大视角下点的位置及连线，不能只按密度判断质量。 <a href="https://arxiv.org/pdf/2308.08479v1#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dedode-3 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/dedode-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/dedode-3.webp" width="1667" height="555" alt="DeDoDe 原论文 Figure 3：先以几何轨迹训练检测，再以匹配目标训练描述的解耦方式。检测器并非必须完全不使用其他描述器生成的 SfM 数据。" loading="lazy" /></a>
  <figcaption>DeDoDe 原论文 Figure 3 · 先以几何轨迹训练检测，再以匹配目标训练描述的解耦方式。检测器并非必须完全不使用其他描述器生成的 SfM 数据。 <a href="https://arxiv.org/pdf/2308.08479v1#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dedode-4 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/dedode-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/dedode-4.webp" width="1667" height="568" alt="DeDoDe 原论文 Figure 4：SfM/MVS 可见轨迹形成检测监督。共视但未检测的点也可投影成为候选标签，减少只复制原检测器的偏差。" loading="lazy" /></a>
  <figcaption>DeDoDe 原论文 Figure 4 · SfM/MVS 可见轨迹形成检测监督。共视但未检测的点也可投影成为候选标签，减少只复制原检测器的偏差。 <a href="https://arxiv.org/pdf/2308.08479v1#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

采样一对图像，将双方可共视 tracks 投影到各自图像并平滑，再与网络预测结合。先验加入一个小的均匀背景项，使未被基础检测器找到的位置不至于概率严格为零；否则乘上网络预测也不可能产生新点。

在教学符号下，预测分布 $p_\theta(\mathbf x)$ 与先验 $p_{track}(\mathbf x)$ 结合为

$$
q(\mathbf x)\propto p_\theta(\mathbf x)p_{track}(\mathbf x).
$$

实际方法再用 top-$k$ 阈值和二值化构造目标，而不是直接无限自强化连续后验。损失让预测概率靠近这个目标，缓解简单软自监督中的退化。

### 5.2 DINOv2 在哪里发挥作用

DeDoDe 的强描述子变体将冻结 DINOv2 的粗语义特征与局部 CNN 特征结合。不同型号并非全部使用 DINOv2，检测网络也不能笼统称为“DINO 角点检测器”。描述训练使用深度、位姿提供的对应，通过双向 softmax 等匹配概率学习几何区分。

<!-- vision-figure: sparse-semantic-local -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/sparse-semantic-local.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/sparse-semantic-local.svg" width="1100" height="470" alt="自制图 3：粗语义特征与局部高分辨率结构互补；插值只能增加采样密度，不能凭空恢复骨干未保留的定位信息。" loading="lazy" /></a>
  <figcaption>自制图 3 · 粗语义特征与局部高分辨率结构互补；插值只能增加采样密度，不能凭空恢复骨干未保留的定位信息。</figcaption>
</figure>
<!-- /vision-figure -->

若 $s_{ij}=\tau\mathbf d_i^\top\mathbf d_j$，一个常见双向匹配概率为

$$
P_{ij}=\operatorname{softmax}_j(s_{ij})\operatorname{softmax}_i(s_{ij}),\qquad
\mathcal L_{desc}=-\frac1{|\mathcal M|}\sum_{(i,j)\in\mathcal M}\log P_{ij}.
$$

这类目标将语义表示拉回“同一物理位置”的训练约束。基础模型负责提高鲁棒性，细粒度特征与几何监督负责校准定位及实例区分。

<!-- vision-figure: dedode-5 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/dedode-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/dedode-5.webp" width="1667" height="630" alt="DeDoDe 原论文 Figure 5：MegaDepth 随机样例中的匹配。相似雕像和重复结构仍出现外点，独立描述子未消除全部歧义。" loading="lazy" /></a>
  <figcaption>DeDoDe 原论文 Figure 5 · MegaDepth 随机样例中的匹配。相似雕像和重复结构仍出现外点，独立描述子未消除全部歧义。 <a href="https://arxiv.org/pdf/2308.08479v1#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dedode-6 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/dedode-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/dedode-6.webp" width="1667" height="341" alt="DeDoDe 原论文 Figure 6：对比方法在不同置信阈值下的对应。过严阈值可能留下太少点，过松则引入大量错误。" loading="lazy" /></a>
  <figcaption>DeDoDe 原论文 Figure 6 · 对比方法在不同置信阈值下的对应。过严阈值可能留下太少点，过松则引入大量错误。 <a href="https://arxiv.org/pdf/2308.08479v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

读检测数量、重复性和最终位姿实验时，要固定点数和匹配器。给某方法更多点或更强 matcher，可能使结论更多反映后处理而非检测器本身。三维轨迹监督也继承初始 SfM 与 SIFT 的可见性和纹理偏好，并非完美地覆盖所有好点。

### 5.3 检测监督和数据增强的边界

<!-- vision-figure: dedode-7 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/dedode-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/dedode-7.webp" width="813" height="520" alt="DeDoDe 原论文 Figure 7：top-10k 关键点的空间分布。能输出很多点不等于几何估计应无限增加点数，还要考虑重复性和计算。" loading="lazy" /></a>
  <figcaption>DeDoDe 原论文 Figure 7 · top-10k 关键点的空间分布。能输出很多点不等于几何估计应无限增加点数，还要考虑重复性和计算。 <a href="https://arxiv.org/pdf/2308.08479v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dedode-8 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/dedode-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/dedode-8.webp" width="813" height="366" alt="DeDoDe 原论文 Figure 8：大旋转下的匹配。未显式保证旋转等变也可有一定泛化，但旋转增加时外点仍会增多。" loading="lazy" /></a>
  <figcaption>DeDoDe 原论文 Figure 8 · 大旋转下的匹配。未显式保证旋转等变也可有一定泛化，但旋转增加时外点仍会增多。 <a href="https://arxiv.org/pdf/2308.08479v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

附录 Figure 7 检查检测分布，Figure 8 展示强旋转下的对应。前者问“哪里应该产生点”，后者问“这些点在变换后还能不能匹配”；只看漂亮连线不能判断检测监督是否均匀覆盖结构。

<!-- vision-figure: dedode-9 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/dedode-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/dedode-9.webp" width="1593" height="770" alt="DeDoDe 原论文 Figure 9：IMC2022 的公开图像对，展示街景与视角变化中的局部匹配覆盖。" loading="lazy" /></a>
  <figcaption>DeDoDe 原论文 Figure 9 · IMC2022 的公开图像对，展示街景与视角变化中的局部匹配覆盖。 <a href="https://arxiv.org/pdf/2308.08479v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dedode-10 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/dedode-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/dedode-10.webp" width="850" height="655" alt="DeDoDe 原论文 Figure 10：MegaDepth 的附录样例保留局部错误。几何验证仍是把描述相似变成相机约束的必要步骤。" loading="lazy" /></a>
  <figcaption>DeDoDe 原论文 Figure 10 · MegaDepth 的附录样例保留局部错误。几何验证仍是把描述相似变成相机约束的必要步骤。 <a href="https://arxiv.org/pdf/2308.08479v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 9–10 给出具有尺度、视角差异的更多匹配案例。它们用来检查局部几何而不是证明完全尺度不变：还必须同时固定输出点数、输入尺寸和描述子型号。SfM 中从未稳定观测的低纹理表面，仍不会因为多画几条连线就获得可靠监督。

**适合采用的情形：**需要独立稀疏点和可缓存描述子，但愿意给描述计算更大的模型预算；需要核对具体 detector/descriptor 型号，不能只记录“DeDoDe”。

## 6. RoMa：语义把范围找对，细特征把像素找准

> [RoMa: Robust Dense Feature Matching，CVPR 2024](https://arxiv.org/abs/2305.15404v1)，[作者代码](https://github.com/Parskatt/RoMa)。这里以首版技术稿解释机制，使用结果时应与对应发布版本核对。

### 6.1 Insight：鲁棒粗定位与精细定位不必由一个骨干包办

RoMa 是稠密匹配器。先用冻结 DINOv2 特征建立全局粗对应，再由专门的细粒度 CNN 特征逐级修正。论文特意指出 DINOv2 的 stride-14 特征很鲁棒，却不能直接提供精确像素定位。

<!-- vision-figure: roma-1 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/roma-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/roma-1.webp" width="1667" height="441" alt="RoMa 原论文 Figure 1：极端视角、照明、尺度和弱纹理下的匹配与重建示例。下游重建效果同时依赖几何后处理。" loading="lazy" /></a>
  <figcaption>RoMa 原论文 Figure 1 · 极端视角、照明、尺度和弱纹理下的匹配与重建示例。下游重建效果同时依赖几何后处理。 <a href="https://arxiv.org/pdf/2305.15404v1#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: roma-2 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/roma-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/roma-2.webp" width="1667" height="535" alt="RoMa 原论文 Figure 2：冻结基础模型提供粗特征，另配细尺度特征，粗层概率预测与细化目标分开设计。" loading="lazy" /></a>
  <figcaption>RoMa 原论文 Figure 2 · 冻结基础模型提供粗特征，另配细尺度特征，粗层概率预测与细化目标分开设计。 <a href="https://arxiv.org/pdf/2305.15404v1#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: roma-multimodal -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/roma-multimodal.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/roma-multimodal.svg" width="1100" height="470" alt="自制图 4：按高斯混合计算的教学曲线：双峰分布的均值不一定对应真实匹配，解释粗分类与细回归分工。" loading="lazy" /></a>
  <figcaption>自制图 4 · 按高斯混合计算的教学曲线：双峰分布的均值不一定对应真实匹配，解释粗分类与细回归分工。</figcaption>
</figure>
<!-- /vision-figure -->

粗级别重复窗格可能在两个候选位置都有高概率。若直接用平方误差回归一个坐标，两个峰的平均可能落在中间墙面，两个答案都没选对。因此 RoMa 用 Transformer 匹配解码器预测 anchor 的分类分布，粗级别保留多模态结构，随后在更细尺度回归局部修正。

### 6.2 优化的分布与最终 warp 是两层对象

$$
p(\mathbf x_A,\mathbf x_B)=p(\mathbf x_B\mid\mathbf x_A)p(\mathbf x_A).
$$

第一项表示对应位置的分布，第二项表达可匹配性。最终 warp $\widehat W^{A\to B}(\mathbf x_A)$ 是从分布解码出的估计；粗层用分类，细层结合鲁棒回归与局部相关体修正。

对某层已有预测 $\widehat W_{s+1}$，细化器在其附近查看相关性并预测 $\Delta W_s$，而不是在全图再做一次同等昂贵的搜索。粗定位选错远处模式，细化器未必能救回；可见性和匹配置信度因此同样必要。

<!-- vision-figure: roma-3 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/roma-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/roma-3.webp" width="829" height="269" alt="RoMa 原论文 Figure 3：粗尺度的匹配分布可有多个模式。直接回归均值可能落在两个合理候选之间的错误位置。" loading="lazy" /></a>
  <figcaption>RoMa 原论文 Figure 3 · 粗尺度的匹配分布可有多个模式。直接回归均值可能落在两个合理候选之间的错误位置。 <a href="https://arxiv.org/pdf/2305.15404v1#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: roma-4 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/roma-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/roma-4.webp" width="813" height="510" alt="RoMa 原论文 Figure 4：不同损失的梯度随误差变化。稳健细化损失抑制大外点的影响，局部仍保留可用更新方向。" loading="lazy" /></a>
  <figcaption>RoMa 原论文 Figure 4 · 不同损失的梯度随误差变化。稳健细化损失抑制大外点的影响，局部仍保留可用更新方向。 <a href="https://arxiv.org/pdf/2305.15404v1#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: roma-5 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/roma-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/roma-5.webp" width="813" height="1809" alt="RoMa 原论文 Figure 5：冻结 VGG、ResNet、DINOv2 与完整 RoMa 的比较。基础特征提升鲁棒性，完整细化进一步恢复几何精度。" loading="lazy" /></a>
  <figcaption>RoMa 原论文 Figure 5 · 冻结 VGG、ResNet、DINOv2 与完整 RoMa 的比较。基础特征提升鲁棒性，完整细化进一步恢复几何精度。 <a href="https://arxiv.org/pdf/2305.15404v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

论文的粗特征实验把“误差小于 32 像素”定义为能够被后续修正利用的鲁棒范围，不能把它当成亚像素成功率。它强调的是分工：先落进正确区域，再改善精度。

<!-- vision-figure: roma-6 -->
<figure>
  <a href="/HomepageX/media/foundation-model-vpr-features/roma-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/foundation-model-vpr-features/roma-6.webp" width="1600" height="2002" alt="RoMa 原论文 Figure 6：与 DKM 在极端变化下的对照。图中展示的是困难样本的定性证据，不能替代完整数据集的统一指标。" loading="lazy" /></a>
  <figcaption>RoMa 原论文 Figure 6 · 与 DKM 在极端变化下的对照。图中展示的是困难样本的定性证据，不能替代完整数据集的统一指标。 <a href="https://arxiv.org/pdf/2305.15404v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

附录 Figure 6 对比困难图像对中 DKM 与 RoMa 的重建/匹配覆盖。可见区域是否被正确保留，与仅在少数容易位置取到高精度匹配是两种能力；报告覆盖与几何成功率有助于避免只挑容易点造成的印象偏差。

**适合采用的情形：**离线定位、SfM、困难图像对重验证，需要强对应且允许较高成本。不能把稠密成对前向耗时与预先缓存描述子的稀疏匹配耗时直接比较。

## 7. 五条路线放在同一个选择坐标系里

| 方法 | 基础模型怎样用 | 新增任务结构 | 更适合回答 |
| --- | --- | --- | --- |
| AnyLoc | 冻结并选择内部特征 | 无监督领域词典与聚合 | 没有目标域标签，能否先做强检索 |
| SALAD | 部分 block 微调 | 带 dustbin 的 OT 聚合 | 哪些局部证据应进入全局描述 |
| SelaVPR | 主干冻结、adapter 学习 | 全局适配和局部重排 | 如何用有限训练参数改善候选排序 |
| DeDoDe 强描述变体 | 冻结粗特征配合局部特征 | 三维轨迹检测先验与几何描述监督 | 如何产生可独立缓存的稀疏特征 |
| RoMa | 冻结粗骨干与专用细编码器 | 粗分类、逐层鲁棒回归 | 怎样把困难对应找得覆盖广且精确 |

这里最可复用的变化并不是“Transformer 替代 CNN”，而是把任务分成几类缺失能力：域泛化、证据聚合、精确定位、几何监督和计算预算，再只在缺失处增加结构。

## 8. DINOv3 更强了，能否把上面的骨干直接替换

值得测试，但不是尺寸对齐就成立。patch size、通道数、层数、特征范数、分辨率策略及训练分布都发生变化；SALAD 的投影头、DeDoDe 的融合模块、RoMa 的粗级匹配器均依赖原表示分布。直接换权重可能导致特征分布与已训练头不匹配。

可操作的验证顺序是：冻结候选 DINOv3 做最简单检索或粗匹配基线，再训练适配头，最后比较相同分辨率、点数、存储预算和几何求解器下的端到端表现。Gram anchoring 维护图内局部关系，有助于稠密表示质量，却没有在预训练中直接监督相机外参或跨视图同一 3D 点。

对于回环系统还需要更严格的一关：高 Recall 的 VPR 是否在低误报工作点仍可靠？接近但无共同视野的图片，不应因地点类别相似就加入强回环边。下一篇数据与最后一篇后端优化，会分别讨论监督从哪里来，以及错误几何证据为什么会毁掉整张地图。
