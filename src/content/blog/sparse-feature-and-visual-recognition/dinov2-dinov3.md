---
title: "读懂 DINOv2 / DINOv3 的训练：没有人工类别标签，视觉特征怎样学到结构"
description: "逐步推导教师学生、自蒸馏、iBOT、Sinkhorn 和 KoLeo，再解释 DINOv3 为什么需要 Gram anchoring 修复长训练中的局部退化。"
date: 2026-09-26
tags: [论文精读, 基础模型, 自监督学习, DINO]
---

同一张街景，裁出整栋楼和一个门洞，再改变颜色，人仍能判断两块内容有关。能否利用这种已知关联，让网络在没有逐图类别标注的情况下学到视觉结构？

难点不是写出“两个特征相近”的损失。只要所有图都输出同一个向量，这个目标就能轻松满足。真正的问题是：**既让相关观察保持一致，又让不同内容保持区分，并让图像级语义不吞掉局部空间细节。** DINOv2 和 DINOv3 的训练设计都围绕这组张力展开。

> 固定来源：[DINOv2，arXiv:2304.07193v2，TMLR 2024](https://arxiv.org/abs/2304.07193v2)、[DINOv3，arXiv:2508.10104v1，2025 技术报告](https://arxiv.org/abs/2508.10104v1)，以及 [DINOv2](https://github.com/facebookresearch/dinov2)、[DINOv3](https://github.com/facebookresearch/dinov3)作者代码。下面区分初始 DINO 的教学解释、v2/v3 的实际配方和后训练阶段。

## 1. 先认识网络交出来的对象

图像被切成边长 $p$ 的 patch，经线性投影变成 token。若输入为 $H\times W$，patch token 数为 $N=(H/p)(W/p)$。ViT 通过自注意力让它们交换上下文，并包含用于全局表示的 CLS token；带 registers 的变体另有寄存 token，供内部计算使用。

输出通常取投影头之前的骨干表示：一个 CLS 向量与一张 patch 特征网格。训练时的 DINO/iBOT 投影头产生 prototype scores，主要用于建立监督分布，并不等于下游部署时必须使用的描述子。

<!-- vision-figure: dino-tokens -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dino-tokens.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dino-tokens.svg" width="1100" height="470" alt="自制图 1：CLS 聚合全局信息，patch token 保留空间索引；有空间索引并不意味着已经达到像素级几何定位精度。" loading="lazy" /></a>
  <figcaption>自制图 1 · CLS 聚合全局信息，patch token 保留空间索引；有空间索引并不意味着已经达到像素级几何定位精度。</figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov2-1 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov2-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov2-1.webp" width="1578" height="701" alt="DINOv2 原论文 Figure 1：patch 特征的 PCA 颜色在相关物体部件间呈现一致性。PCA 颜色是可视化坐标，不是人工语义标签或精确匹配概率。" loading="lazy" /></a>
  <figcaption>DINOv2 原论文 Figure 1 · patch 特征的 PCA 颜色在相关物体部件间呈现一致性。PCA 颜色是可视化坐标，不是人工语义标签或精确匹配概率。 <a href="https://arxiv.org/pdf/2304.07193v2#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov3-1 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-1.webp" width="1578" height="987" alt="DINOv3 原论文 Figure 1：分类、规模和稠密表示的整体结果。右侧可视化体现局部结构质量，不能由左侧分类分数单独推断。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 1 · 分类、规模和稠密表示的整体结果。右侧可视化体现局部结构质量，不能由左侧分类分数单独推断。 <a href="https://arxiv.org/pdf/2508.10104v1#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

图中的 PCA 颜色显示表示有结构，但颜色相近不等于某个真实语义类别，也不保证两个位置是同一物理点。可视化采用的 PCA 基底、前景筛选会影响颜色，不能从彩色图直接读出像素级精度。

## 2. 教师没有答案，它怎样教学生

### 2.1 两种更新规则，避免彼此瞬间追逐

学生参数 $\theta_s$ 由反向传播更新；教师参数由学生的指数移动平均更新：

$$
\theta_t\leftarrow m\theta_t+(1-m)\theta_s,\qquad m\in[0,1).
$$

教师前向输出停止梯度。它相当于较平滑的历史模型，不是另一个通过同一损失同步下降的网络。例如 $m=0.99$，旧参数为 1、新学生参数为 2，教师只移到 1.01。这是逐参数的时间平滑，不是对两张图片特征求平均。

多裁剪训练让学生看到全局和局部视图，教师主要看到全局视图。全局教师给出的目标引导学生从较少内容中恢复语义线索。同一个全局裁剪的自配对通常从跨视图 DINO 项中排除，避免把任务简化为复制完全相同输入。

<!-- vision-figure: dino-teacher -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dino-teacher.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dino-teacher.svg" width="1100" height="470" alt="自制图 2：两个视图的分布对齐通过学生反传，教师参数缓慢跟随学生；EMA 路径不等同于对目标概率直接求梯度。" loading="lazy" /></a>
  <figcaption>自制图 2 · 两个视图的分布对齐通过学生反传，教师参数缓慢跟随学生；EMA 路径不等同于对目标概率直接求梯度。</figcaption>
</figure>
<!-- /vision-figure -->

### 2.2 匹配的是概率分布，而不是直接复制 RGB

投影头输出 $K$ 维 logits $\mathbf z$，它们对应可学习 prototype，并不是预先命名的物体类别。学生分布为

$$
p_s(k\mid v)=\frac{\exp(z_{s,k}(v)/\tau_s)}{\sum_{k'}\exp(z_{s,k'}(v)/\tau_s)}.
$$

对教师视图 $v_t$ 与学生视图 $v_s$，交叉熵为

$$
H(p_t,p_s)=-\sum_{k=1}^Kp_t(k\mid v_t)\log p_s(k\mid v_s).
$$

若教师分布为 $(0.8,0.1,0.1)$，学生为 $(0.6,0.2,0.2)$，交叉熵约 0.731；学生均匀输出时为 $\log3\approx1.099$。交叉熵在学生等于教师时达到教师分布的熵，**软目标下不应期待它降到零**。

对学生 logit 的梯度为 $(p_s-p_t)/\tau_s$，因此教师高概率、学生低概率的位置被推高，其余相应降低。这比“拉近两个图像”更精确地说明了监督作用在哪里。

## 3. 一致性为什么不会自然避免坍塌

### 3.1 两种平凡答案都必须警惕

所有图都选择同一个 prototype，会产生单一模式坍塌；所有图都给出相同均匀分布，也没有区分力。EMA 和 stop-gradient 提供学习动态上的不对称，却不能单独构成“不坍塌”的数学保证。

初始 DINO 使用 teacher centering 与较低教师温度的 sharpening：中心化抑制总占优势的维度，锐化鼓励单张图给出有信息的目标。DINOv2/v3 的实际配方使用 Sinkhorn–Knopp 进行教师分配平衡，不能把最早的 EMA 中心化公式当成它们唯一的实现。

### 3.2 Sinkhorn 平衡的是 batch 中样本与 prototypes

设一个批次有 $B$ 个教师输出，构造 $Q\in\mathbb R_+^{B\times K}$。一个教学写法是

$$
Q_{bk}\propto\exp(z_{bk}/\tau_t),\qquad
\sum_kQ_{bk}=1,\quad\sum_bQ_{bk}=B/K.
$$

交替行列归一化，让每个样本有一份分布、各 prototype 在批内不过分失衡。实际分布式实现要汇总跨 GPU 的统计；iBOT 的对象是采样的 patch token，对应批次维度也不同。

<!-- vision-figure: dino-collapse -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dino-collapse.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dino-collapse.svg" width="1100" height="470" alt="自制图 3：三种教学分布：全部占用一个原型与全部均匀都可能退化；温度、批次平衡和特征分散约束承担不同角色。" loading="lazy" /></a>
  <figcaption>自制图 3 · 三种教学分布：全部占用一个原型与全部均匀都可能退化；温度、批次平衡和特征分散约束承担不同角色。</figcaption>
</figure>
<!-- /vision-figure -->

这与 [SuperGlue](/HomepageX/blog/sparse-feature-and-visual-recognition/superglue-lightglue/)都用了 Sinkhorn，但任务不同：SuperGlue 约束两组关键点和 dustbin 的部分分配；这里约束样本到 prototype 的使用平衡，没有视觉对应点对的含义。

平衡并不意味着真实类别均匀，也不意味着每批必须恰好包含 $K$ 种物体。prototype 是表示空间里的训练工具，不能把它直接当作语义标签。

### 3.3 KoLeo 补充特征空间的分散性

对归一化骨干特征 $\mathbf x_i$，定义最近其他样本距离

$$
d_i=\min_{j\ne i}\|\mathbf x_i-\mathbf x_j\|_2,\qquad
\mathcal L_{\mathrm{KoLeo}}=-\frac1B\sum_i\log(d_i+\epsilon).
$$

最近距离从 0.1 变成 0.2，该样本项从约 2.303 变成 1.609，鼓励过度拥挤的表示散开。这个正则不是手工指定正负语义对，也不保证全空间严格均匀；它通过批内最近邻近似熵的作用。

DINOv3 使用分布式的局部小批次版本，原文设置每组 16 个样本，避免简单地把很大的全局 batch 直接代入而改变正则行为。

## 4. 为什么仅有图像级 DINO 还不够

### 4.1 CLS 分得清，不代表每个 patch 都定位得准

“这是桥”可以通过全局统计判断；“桥墩的边界在哪”需要保留局部差异。如果所有 patch 都过度吸收整图语义，分类可能更好，局部匹配和分割反而变差。

iBOT 增加 patch 级训练：学生的某些 patch 输入被 mask token 替换，教师看到同一裁剪的未遮挡图像。教师的对应位置输出作为目标：

$$
\mathcal L_{\mathrm{iBOT}}=-\frac1{|\mathcal M|}\sum_{i\in\mathcal M}
\sum_k p_{t,i}(k)\log p_{s,i}(k).
$$

$\mathcal M$ 是被遮挡的位置集合。这是预测教师的**潜在表示分布**，不是重建像素。用于这项损失的师生 patch 网格已对齐；跨裁剪的图像级目标与同裁剪对应 patch 目标不能混为一条连线。

<!-- vision-figure: dino-masking -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dino-masking.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dino-masking.svg" width="1100" height="470" alt="自制图 4：虚线只连接同一裁剪坐标中的被遮挡位置；patch 目标与跨不同裁剪的 CLS 目标不能混为一项。" loading="lazy" /></a>
  <figcaption>自制图 4 · 虚线只连接同一裁剪坐标中的被遮挡位置；patch 目标与跨不同裁剪的 CLS 目标不能混为一项。</figcaption>
</figure>
<!-- /vision-figure -->

DINOv2 将全局 DINO 头和局部 iBOT 头解耦。在大规模训练中，不要求两类目标共用全部投影头参数，给它们各自调整的空间。某些原 iBOT 小规模消融支持共享头，与 v2 的规模条件不同，不能忽略条件解释成论文自相矛盾。

### 4.2 数据策划也是训练算法的一部分

DINOv2 从约 12 亿去重候选图中构建 1.42 亿张 LVD-142M。其策划借助检索、聚类和多个参考数据集，提高多样性与覆盖。无需人工类别标签参与预训练损失，不代表数据管线完全不利用已有数据集及其选择偏好。

<!-- vision-figure: dinov2-2 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov2-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov2-2.webp" width="1579" height="747" alt="DINOv2 原论文 Figure 2：模型规模与八类视觉任务表现。冻结特征的可迁移性应通过多种任务观察，不能只看 ImageNet 分类。" loading="lazy" /></a>
  <figcaption>DINOv2 原论文 Figure 2 · 模型规模与八类视觉任务表现。冻结特征的可迁移性应通过多种任务观察，不能只看 ImageNet 分类。 <a href="https://arxiv.org/pdf/2304.07193v2#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov2-3 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov2-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov2-3.webp" width="1578" height="509" alt="DINOv2 原论文 Figure 3：数据处理：嵌入、去重和基于已整理数据的检索扩充。数据分布设计与扩大模型共同影响通用性。" loading="lazy" /></a>
  <figcaption>DINOv2 原论文 Figure 3 · 数据处理：嵌入、去重和基于已整理数据的检索扩充。数据分布设计与扩大模型共同影响通用性。 <a href="https://arxiv.org/pdf/2304.07193v2#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov2-4 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov2-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov2-4.webp" width="1578" height="255" alt="DINOv2 原论文 Figure 4：比较模型规模与训练数据规模。大模型在小数据集上并不会自动获得相同收益。" loading="lazy" /></a>
  <figcaption>DINOv2 原论文 Figure 4 · 比较模型规模与训练数据规模。大模型在小数据集上并不会自动获得相同收益。 <a href="https://arxiv.org/pdf/2304.07193v2#page=9" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

数据规模相同不代表学习信号相同。大量重复图片会使梯度反复强调同一视觉模式；只扩大来源而不控制分布，也可能让常见互联网类别压过下游需要的内容。相关消融应比较相同训练预算下的策划数据和随机数据。

DINOv2 最大 ViT-g/14 约 11 亿参数，再蒸馏较小模型。训练中使用高效注意力、序列打包、随机深度和 FSDP 等工程手段。序列打包必须保留分块注意力 mask，不能让不同图片的 tokens 偷看彼此。后期短暂提高到 $518\times518$，改善小物体和稠密任务，避免全程高分辨率的成本。

### 4.3 小模型蒸馏不是继续 EMA 自蒸馏

v2 的小模型蒸馏使用已经训练好的大模型作为固定教师，另保留学生 EMA 用于最终评估；去掉 mask 和随机深度，并在全局裁剪上施加局部目标。这里“固定大教师”和预训练中的“学生 EMA 教师”是两种不同角色。

<!-- vision-figure: dinov2-5 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov2-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov2-5.webp" width="1578" height="603" alt="DINOv2 原论文 Figure 5：固定大教师蒸馏与同尺寸模型从头训练的比较。学生偶尔超过教师的某个指标，不表示获得了更多训练信息。" loading="lazy" /></a>
  <figcaption>DINOv2 原论文 Figure 5 · 固定大教师蒸馏与同尺寸模型从头训练的比较。学生偶尔超过教师的某个指标，不表示获得了更多训练信息。 <a href="https://arxiv.org/pdf/2304.07193v2#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov2-6 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov2-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov2-6.webp" width="1578" height="404" alt="DINOv2 原论文 Figure 6：训练与测试分辨率的关系。低分辨率预训练后短暂提高分辨率，可以改变高分辨率下的冻结特征质量。" loading="lazy" /></a>
  <figcaption>DINOv2 原论文 Figure 6 · 训练与测试分辨率的关系。低分辨率预训练后短暂提高分辨率，可以改变高分辨率下的冻结特征质量。 <a href="https://arxiv.org/pdf/2304.07193v2#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

这些消融需分别看检索、分割和分类。某改动使 kNN 或检索变好，未必使线性分类完全同步提高；选择一个单指标最大化，不足以证明得到了通用特征。

<!-- vision-figure: dinov2-7 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov2-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov2-7.webp" width="1578" height="862" alt="DINOv2 原论文 Figure 7：冻结特征上的线性分割与深度探针。结果体现特征包含可读取信息，仍使用了下游有监督探针。" loading="lazy" /></a>
  <figcaption>DINOv2 原论文 Figure 7 · 冻结特征上的线性分割与深度探针。结果体现特征包含可读取信息，仍使用了下游有监督探针。 <a href="https://arxiv.org/pdf/2304.07193v2#page=17" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov2-8 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov2-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov2-8.webp" width="1578" height="646" alt="DINOv2 原论文 Figure 8：分布外图像的线性探针结果。需要同时观察细边界和错误区域，不只看大块语义颜色。" loading="lazy" /></a>
  <figcaption>DINOv2 原论文 Figure 8 · 分布外图像的线性探针结果。需要同时观察细边界和错误区域，不只看大块语义颜色。 <a href="https://arxiv.org/pdf/2304.07193v2#page=17" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov2-9 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov2-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov2-9.webp" width="1579" height="883" alt="DINOv2 原论文 Figure 9：更多 PCA 部件一致性结果。共同 PCA 与背景筛除属于可视化过程，不等同于模型直接输出这些颜色。" loading="lazy" /></a>
  <figcaption>DINOv2 原论文 Figure 9 · 更多 PCA 部件一致性结果。共同 PCA 与背景筛除属于可视化过程，不等同于模型直接输出这些颜色。 <a href="https://arxiv.org/pdf/2304.07193v2#page=18" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov2-10 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov2-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov2-10.webp" width="1578" height="1031" alt="DINOv2 原论文 Figure 10：跨姿态、风格甚至不同物体的 patch 对应。语义相似不保证两点属于同一三维实体，不能直接作为 SLAM 地标关联。" loading="lazy" /></a>
  <figcaption>DINOv2 原论文 Figure 10 · 跨姿态、风格甚至不同物体的 patch 对应。语义相似不保证两点属于同一三维实体，不能直接作为 SLAM 地标关联。 <a href="https://arxiv.org/pdf/2304.07193v2#page=19" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

定性结果与特征分析展示了跨图像的结构，但它们不是经过两视图几何验证的稀疏特征轨迹。接入定位任务还需要明确采样层、token 类型、分辨率、聚合或精细匹配方式。

## 5. DINOv3 的转折：继续训练，局部特征却变坏

DINOv3 进一步扩大数据与模型：策划数据 LVD-1689M 约 16.89 亿图，旗舰 ViT 的参数量约 67 亿，patch size 从 14 改为 16。其初始目标仍以图像自蒸馏、局部潜在预测和分散正则为主：

$$
\mathcal L_{\mathrm{Pre}}=\mathcal L_{\mathrm{DINO}}+\mathcal L_{\mathrm{iBOT}}+0.1\mathcal L_{\mathrm{DKoLeo}}.
$$

图像来自多种策划与原始数据成分的混合，使用分层聚类平衡与检索等策略。预训练采用 warmup 后恒定的学习率、权重衰减和 EMA momentum，以便延长训练，而不是必须预先确定一个余弦退火终点。

<!-- vision-figure: dinov3-2 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-2.webp" width="1579" height="538" alt="DINOv3 原论文 Figure 2：DINOv3 家族与其他特征在多种任务中的规模比较。计算量和任务评价协议都需一起读。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 2 · DINOv3 家族与其他特征在多种任务中的规模比较。计算量和任务评价协议都需一起读。 <a href="https://arxiv.org/pdf/2508.10104v1#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov3-3 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-3.webp" width="1578" height="1203" alt="DINOv3 原论文 Figure 3：4096×4096 图像中的特征余弦相似度。红十字选定查询 patch，亮区代表特征相似而非深度接近。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 3 · 4096×4096 图像中的特征余弦相似度。红十字选定查询 patch，亮区代表特征相似而非深度接近。 <a href="https://arxiv.org/pdf/2508.10104v1#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov3-4 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-4.webp" width="1578" height="397" alt="DINOv3 原论文 Figure 4：同一内容在越来越高分辨率下的 PCA。边界更细与语义保持同时重要，背景筛除属于展示处理。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 4 · 同一内容在越来越高分辨率下的 PCA。边界更细与语义保持同时重要，背景筛除属于展示处理。 <a href="https://arxiv.org/pdf/2508.10104v1#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

RoPE 提供随相对位置变化的注意力编码，坐标 box jittering 又让模型适应尺度和长宽比变化。$256/16=224/14=16$，因此 v3 使用 256 的全局裁剪并不意味着初始 patch 序列比 v2 的 224 更长。比较计算量应看 token 数及模型宽度，而不只看像素边长。

### 5.1 这不是所有样本都变成同一个向量

<!-- vision-figure: dinov3-5 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-5.webp" width="1578" height="729" alt="DINOv3 原论文 Figure 5：训练中分类提升而局部分割退化的证据。patch 与 CLS 相似性变化提示局部特征逐渐过度全局化。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 5 · 训练中分类提升而局部分割退化的证据。patch 与 CLS 相似性变化提示局部特征逐渐过度全局化。 <a href="https://arxiv.org/pdf/2508.10104v1#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov3-6 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-6.webp" width="1579" height="603" alt="DINOv3 原论文 Figure 6：同一查询 patch 的相似度图随训练变得弥散。对照局部结构，才能看见单一分类指标掩盖的退化。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 6 · 同一查询 patch 的相似度图随训练变得弥散。对照局部结构，才能看见单一分类指标掩盖的退化。 <a href="https://arxiv.org/pdf/2508.10104v1#page=11" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 5 同时画分类与分割：训练变长，分类继续提高，稠密任务却开始下降。Figure 6 的参考 patch 相似度图逐渐出现与该位置无关的高响应。模型还会分类，因此这是**局部表示一致性退化**，不是最简单的全局常量坍塌。

register tokens 能缓解某些高范数离群 patch，却没有自动解决这类长训练中的相似度结构退化。二者的问题对象不同。只画训练总损失下降曲线，会把这个问题藏起来。

## 6. Gram anchoring：保住关系，不把每个向量钉死

### 6.1 一个图像内的相似度矩阵包含什么

设学生的 $P$ 个归一化 patch 特征组成 $X_s\in\mathbb R^{P\times d}$，Gram 矩阵

$$
G_s=X_sX_s^\top\in\mathbb R^{P\times P},\qquad
(G_s)_{ij}=\cos(\mathbf x_i,\mathbf x_j).
$$

每个元素回答“图内第 i、j 个 patch 的表示多相似”。这是 token-token 的 $P\times P$ 矩阵，不是风格迁移中常见的通道相关 $d\times d$ 矩阵，也不是 cross-image 的匹配矩阵。

<!-- vision-figure: dino-gram -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dino-gram.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dino-gram.svg" width="1100" height="470" alt="自制图 5：三个单位 token 的数值例子：共同正交旋转改变特征坐标，却不改变 token–token Gram 矩阵。" loading="lazy" /></a>
  <figcaption>自制图 5 · 三个单位 token 的数值例子：共同正交旋转改变特征坐标，却不改变 token–token Gram 矩阵。</figcaption>
</figure>
<!-- /vision-figure -->

若三个 patch 分别是楼面、相邻楼面、天空，早期教师给出相似度结构

$$
G_g=\begin{bmatrix}1&0.9&0.1\\0.9&1&0.2\\0.1&0.2&1\end{bmatrix},
$$

而学生把楼面与天空相似度升为 0.7，即使图像级分类仍正确，局部关系也已污染。Gram 目标会针对这些非对角关系产生惩罚。

### 6.2 Gram 教师与 EMA 教师是两条时间线

DINOv3 从稠密特征还好的较早 checkpoint 初始化 Gram teacher，并在 refinement 阶段加入

$$
\mathcal L_{\mathrm{Gram}}=\|X_sX_s^\top-X_gX_g^\top\|_F^2.
$$

教师目标停止梯度。报告中的公式是 Frobenius **求和**；如果实现或教学计算改成除以 $P^2$ 的均方误差，损失权重也必须随之理解，不能直接复制系数。

固定关系为什么比直接回归特征灵活？对任何正交矩阵 $Q$，

$$
(X_sQ)(X_sQ)^\top=X_sX_s^\top.
$$

因此整体旋转表示基底不会改变这项损失。学生可以继续调整特征坐标，只要局部相似度结构保留。Gram 并未对所有变换都不敏感，也没有要求各 patch 彼此正交；对角线因单位归一化本来就约为 1。

<!-- vision-figure: dinov3-7 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-7.webp" width="1578" height="564" alt="DINOv3 原论文 Figure 7：iBOT、DINO 与 Gram 损失的训练过程。新增关系约束旨在修复局部结构，不要求替换原有全局目标。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 7 · iBOT、DINO 与 Gram 损失的训练过程。新增关系约束旨在修复局部结构，不要求替换原有全局目标。 <a href="https://arxiv.org/pdf/2508.10104v1#page=12" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov3-8 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-8.webp" width="1579" height="496" alt="DINOv3 原论文 Figure 8：Gram anchoring 与高分辨率教师的影响。分别比较 VOC、ADE20k 分割及 ObjectNet 分类，不从单一曲线推断所有任务同步改善。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 8 · Gram anchoring 与高分辨率教师的影响。分别比较 VOC、ADE20k 分割及 ObjectNet 分类，不从单一曲线推断所有任务同步改善。 <a href="https://arxiv.org/pdf/2508.10104v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

原报告在 1M 迭代之后开始 refinement，并每 10k 迭代将 Gram teacher 更新为主 EMA 教师。它不是永远冻结在早期，也不是每步都直接等于最新学生。较慢更新让改善后的关系逐步接力。

### 6.3 用更高分辨率教师修复粗网格

教师先以两倍边长处理图像，再将特征图双三次下采样到学生网格，之后计算关系目标。这样传递的是更平滑、细节更一致的 patch 关系，不是让不对齐的两个矩阵硬做差。

<!-- vision-figure: dinov3-9 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-9.webp" width="1578" height="497" alt="DINOv3 原论文 Figure 9：高分辨率 Gram 教师下采样后的局部关系更清楚。右侧量化比较用于检验这一步是否真正有收益。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 9 · 高分辨率 Gram 教师下采样后的局部关系更清楚。右侧量化比较用于检验这一步是否真正有收益。 <a href="https://arxiv.org/pdf/2508.10104v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov3-10 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-10.webp" width="1578" height="937" alt="DINOv3 原论文 Figure 10：使用 Gram 约束前后的相似度图。改善应表现为相关物体局部集中，而不只是颜色对比增强。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 10 · 使用 Gram 约束前后的相似度图。改善应表现为相关物体局部集中，而不只是颜色对比增强。 <a href="https://arxiv.org/pdf/2508.10104v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 9 的消融支持两个具体结论：早期教师比已退化的晚期教师更适合作锚；高分辨率目标还能进一步提高稠密任务。Figure 10 给出对应的相似度图变化。它们不能推出“任意领域都应固定第 200k 步”——这个时刻依赖训练数据、模型和配方。

## 7. 后训练的三件事，解决三个部署问题

### 7.1 分辨率适应

DINOv3 用混合的全局、局部裁剪尺寸再训练，继续保留 Gram 约束。较高分辨率增加空间 token，能显露小结构，也显著增加注意力成本。高分辨率特征稳定不代表网络免费输出原图逐像素信息。

<!-- vision-figure: dinov3-11 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-11.webp" width="1578" height="367" alt="DINOv3 原论文 Figure 11：分辨率后训练在多个测试分辨率上的影响。不同任务对输入分辨率的敏感程度不同。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 11 · 分辨率后训练在多个测试分辨率上的影响。不同任务对输入分辨率的敏感程度不同。 <a href="https://arxiv.org/pdf/2508.10104v1#page=15" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 11 分开比较分类、分割和跟踪及多个输入尺寸，说明“提高输入尺寸”不是所有指标都单调改善。

### 7.2 一位固定大教师，教多位小学生

<!-- vision-figure: dinov3-12 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-12.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-12.webp" width="1579" height="734" alt="DINOv3 原论文 Figure 12：多学生共享教师前向的蒸馏组织。减少重复教师计算属于训练效率设计，不是推理时必须同时运行多个学生。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 12 · 多学生共享教师前向的蒸馏组织。减少重复教师计算属于训练效率设计，不是推理时必须同时运行多个学生。 <a href="https://arxiv.org/pdf/2508.10104v1#page=16" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

v3 将固定大教师的前向结果在多个学生之间共享，减少重复教师计算。报告的小模型蒸馏未观察到同样的局部退化，所以这一阶段不使用 Gram anchoring；不能把旗舰预训练的每个损失无条件写到所有发布模型的训练流程中。

### 7.3 文本对齐是后加的能力

DINOv3 的主体预训练没有用图文对做 CLIP 式语义对齐。文本阶段冻结视觉骨干、训练文本编码器，并在视觉侧增加适配层；目标才包含图文对应。因此裸 DINO 特征不能直接拿任意文本 embedding 做点积就当成开放词汇分类。



## 8. 如何判断“基础模型更强”是否支持你的任务

### 8.1 先看特征结构，再看任务头

<!-- vision-figure: dinov3-13 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-13.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-13.webp" width="1578" height="1516" alt="DINOv3 原论文 Figure 13：多种骨干的稠密 PCA 比较。局部边界、跨区域一致性和背景泄漏需一起观察。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 13 · 多种骨干的稠密 PCA 比较。局部边界、跨区域一致性和背景泄漏需一起观察。 <a href="https://arxiv.org/pdf/2508.10104v1#page=18" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 13 对比多种骨干的稠密 PCA 结构。相邻物体的边界更清晰是有用迹象，但颜色来自降维，不能直接当语义标签或几何真值。冻结骨干、线性探测、训练解码器、全量微调属于不同评估协议；“无需微调”通常只指骨干冻结。

<!-- vision-figure: dinov3-21 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-21.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-21.webp" width="1578" height="911" alt="DINOv3 原论文 Figure 21：不同层特征的任务表现。最终层并非每个任务唯一最佳选择，选择层号也是下游设计变量。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 21 · 不同层特征的任务表现。最终层并非每个任务唯一最佳选择，选择层号也是下游设计变量。 <a href="https://arxiv.org/pdf/2508.10104v1#page=56" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 21 检查不同 Transformer 层：分类、深度、分割与对应估计的最佳层未必一致。选取最后一层 CLS token 适合的任务，与需要细粒度 patch 对应的任务可能不同。部署时应把层、token 类型、输入分辨率一起视为设计选择。

<!-- vision-figure: dinov3-14 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-14.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-14.webp" width="1578" height="604" alt="DINOv3 原论文 Figure 14：TokenCut 在冻结 patch 特征上进行无监督物体发现，以 CorLoc 评估。红色掩码没有使用人工分割标注或后处理，不涉及文本查询。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 14 · TokenCut 在冻结 patch 特征上进行无监督物体发现，以 CorLoc 评估。红色掩码没有使用人工分割标注或后处理，不涉及文本查询。 <a href="https://arxiv.org/pdf/2508.10104v1#page=21" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 14 展示的是 TokenCut 无监督物体发现：在 patch 特征上分割显著对象，再用 CorLoc 衡量定位。红色掩码没有给定文本，也没有使用人工分割标注；这是视觉表示配合无监督算法的结果，与上一节的图文对齐应用是不同任务。

### 8.2 小模型和高分辨率的成本也要看

<!-- vision-figure: dinov3-16 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-16.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-16.webp" width="1578" height="662" alt="DINOv3 原论文 Figure 16：蒸馏模型的参数、计算量和任务表现。卷积与 ViT 学生的收益需分别核对，不能直接继承大教师的所有指标。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 16 · 蒸馏模型的参数、计算量和任务表现。卷积与 ViT 学生的收益需分别核对，不能直接继承大教师的所有指标。 <a href="https://arxiv.org/pdf/2508.10104v1#page=30" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov3-17 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-17.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-17.webp" width="1579" height="1071" alt="DINOv3 原论文 Figure 17：不同尺寸 DINOv3 模型在不同分辨率下的 PCA。学生模型质量应逐项验证，不能从大教师结果自动继承。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 17 · 不同尺寸 DINOv3 模型在不同分辨率下的 PCA。学生模型质量应逐项验证，不能从大教师结果自动继承。 <a href="https://arxiv.org/pdf/2508.10104v1#page=31" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 16 列出模型规模和计算量，Figure 17 展示不同模型在更大输入下的局部结构。细网格能让可视化更丰富，但相同输出尺寸不代表相同运行成本；也不能用小模型的速度搭配旗舰模型的精度，写成一个配置的表现。

### 8.3 视频的掩码传播与分类，要分开评价

<!-- vision-figure: dinov3-15 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-15.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-15.webp" width="1578" height="580" alt="DINOv3 原论文 Figure 15：视频中的分割传播。首帧掩码提供任务条件，后续帧通过特征关联传播，并非零提示自动得到实例身份。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 15 · 视频中的分割传播。首帧掩码提供任务条件，后续帧通过特征关联传播，并非零提示自动得到实例身份。 <a href="https://arxiv.org/pdf/2508.10104v1#page=22" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov3-22 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-22.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-22.webp" width="1578" height="1102" alt="DINOv3 原论文 Figure 22：视频分类的时间和空间采样。训练片段与推理多视图采样不同，计算预算与结果必须按相同设置比较。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 22 · 视频分类的时间和空间采样。训练片段与推理多视图采样不同，计算预算与结果必须按相同设置比较。 <a href="https://arxiv.org/pdf/2508.10104v1#page=62" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 15 展示视频中的对象传播，Figure 22 给出视频分类评估的时间与空间采样，它不属于前一张图的掩码传播算法。遮挡后身份保持、跨帧采样间隔和累积误差都会改变难度。只展示相邻帧特征相似，尚不足以证明长时跟踪可靠。

### 8.4 领域迁移与异常 token 要单独检查

<!-- vision-figure: dinov3-18 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-18.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-18.webp" width="1578" height="405" alt="DINOv3 原论文 Figure 18：卫星影像中的模型差异。领域适配数据改变了特征关注方式，说明通用预训练仍受数据分布影响。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 18 · 卫星影像中的模型差异。领域适配数据改变了特征关注方式，说明通用预训练仍受数据分布影响。 <a href="https://arxiv.org/pdf/2508.10104v1#page=35" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: dinov3-19 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-19.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-19.webp" width="1578" height="459" alt="DINOv3 原论文 Figure 19：遥感冠层高度预测的示例。这里包含任务头和监督，不代表 patch 特征的颜色就是物理高度。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 19 · 遥感冠层高度预测的示例。这里包含任务头和监督，不代表 patch 特征的颜色就是物理高度。 <a href="https://arxiv.org/pdf/2508.10104v1#page=36" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 18–19 进入遥感与树冠高度等任务。它们支持表示可迁移的论点，同时使用相应领域数据、头和评估条件；不能据此把自然图像模型未经适配的输出当成米制高度。

<!-- vision-figure: dinov3-20 -->
<figure>
  <a href="/HomepageX/media/dinov2-dinov3/dinov3-20.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/dinov2-dinov3/dinov3-20.webp" width="1578" height="736" alt="DINOv3 原论文 Figure 20：抑制高范数异常 patch 的策略消融。比较无处理、四个 register token、attention bias 与 value gating，观察范数和下游效果。" loading="lazy" /></a>
  <figcaption>DINOv3 原论文 Figure 20 · 抑制高范数异常 patch 的策略消融。比较无处理、四个 register token、attention bias 与 value gating，观察范数和下游效果。 <a href="https://arxiv.org/pdf/2508.10104v1#page=54" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 20 比较 register 等异常 token 处理策略及 patch 范数。少数异常高范数 token 会污染局部解释，但缓解这种异常与 Gram anchoring 解决的长期关系退化并非完全同一个问题。视觉关系更干净仍不能消除重复纹理；同类对象的语义相似，有时恰好会伤害“是不是同一个窗角”的实例匹配。

真正有用的训练监控应同时看全局与局部：教师输出熵、prototype 使用、特征最近邻距离、全局检索、patch 相似度和稠密下游探测。损失正常、没有 NaN，仅说明数值计算没有明显崩溃，不等于局部表示健康。

DINOv2 的关键经验，是把数据策划、全局与局部目标、分散正则和可扩展实现结合起来。DINOv3 再指出：扩大规模后，必须直接维护局部关系，不能期待图像级能力增长自动带来几何可用性。

下一篇：[基础模型如何改变 VPR 与稀疏特征研究](/HomepageX/blog/sparse-feature-and-visual-recognition/foundation-model-vpr-features/)。
