---
title: "BoxerNet 精读：把开放世界二维框，稳稳放进三维房间"
description: "从单目尺度歧义、稀疏深度 patch 和不确定性损失，到世界坐标融合；逐图读懂 Boxer 的系统边界与实验条件。"
date: 2026-09-29
tags: [论文精读, 3D Perception, Project Aria, BoxerNet, 三维检测]
draft: false
---

走进厨房，眼镜很容易在图像中圈出“杯子”。但若要告诉你杯子在桌角、离手多远、占据多大空间，一个二维矩形还远远不够。它没有回答深度；你转一下头，矩形也会变；连续一百帧检测出一百个杯子框，并不代表房间里有一百个杯子。

**Boxer 把这个问题拆成三层：成熟的二维检测器负责找物体，BoxerNet 负责恢复每个框的三维几何，融合模块负责把多次观测收成一份静态世界地图。** 论文名是 *Boxer: Robust Lifting of Open-World 2D Bounding Boxes to 3D*；BoxerNet 是其中的提升网络，不是整条系统。

本文固定阅读 Daniel DeTone 等的 [arXiv v1 原文与附录](https://arxiv.org/abs/2604.05212v1)，并参照[作者项目与推理代码](https://facebookresearch.github.io/boxer/)。这是 [3D Perception and Project Aria 专栏](/HomepageX/blog/3d-perception-and-project-aria/)的第一篇；它承接上一专栏的[视觉特征表示](/HomepageX/blog/sparse-feature-and-visual-recognition/dinov2-dinov3/)，把问题从“像什么”推进到“在世界哪里”。

## 训练资源、卡时与数据量

| 项目 | 论文可确认的规模 |
| --- | --- |
| 训练数据 | 内部 Aria/Quest 数据，加上 NymeriaPlus、CA-1M、ScanNet、SUN-RGBD 等公开来源；作者以约 122 万个独立三维框计数，特意不把同一物体的重复帧观测再乘进去。 |
| 训练资源 | 图像、深度/点云、相机标定和三维框共同进入训练；作者报告使用 16 张 H100、约两周训练。按墙钟时间粗算约 $16\times14\times24=5376$ H100-hours，论文没有说明这是否包含失败实验与消融。 |
| 复现边界 | RTX 4090 上约 20 ms 是 $960\times960$、bfloat16 条件下的 Boxernet 提升前向，不是训练卡时，也不包含二维检测、SLAM、点云生成和全局融合。 |

<!-- aria-figure: boxer-1 -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-1.webp" width="1141" height="444" alt="Boxer 原论文 Figure 1：静态场景中小物体与长尾类别的三维框。看不同视角是否落在同一个实体上。" loading="lazy" /></a>
  <figcaption>Boxer 原论文 Figure 1 · 静态场景中小物体与长尾类别的三维框。看不同视角是否落在同一个实体上。 <a href="https://arxiv.org/pdf/2604.05212v1#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 1 要看的是那些不止“床、桌、椅”的小物体。二维语义模型带来长尾类别入口，三维提升补上位置与尺度。不过，这张成功样例还不能说明任何新类别都能被可靠定位；上游漏检、几何歧义和训练分布仍会限制结果。

## 1. 一张二维框，为什么对应无数个三维盒子？

### 像素告诉我们方向，深度决定物理大小

用最简单的针孔相机说明。空间点在相机坐标中为 $(X,Y,Z)$，像素为

$$
u=f_x\frac{X}{Z}+c_x,\qquad v=f_y\frac{Y}{Z}+c_y.
$$

$f_x,f_y$ 是以像素计的焦距，$(c_x,c_y)$ 是主点。如果把 $(X,Y,Z)$ 同时乘以两倍，投影完全不变。一个小杯子放在近处，一个两倍大的模型放在两倍远处，可以占据相同图像区域。二维框的四条边只能给出一个视锥，不能直接决定盒子落在视锥的哪一段。

对于正对相机、深度变化很小的物体，像宽近似满足 $w_{\rm px}=f_x W/Z$。取 $f_x=600$ 像素、像宽 $120$ 像素：$Z=1$ 米对应 $W=0.2$ 米；$Z=2$ 米对应 $W=0.4$ 米。这里是教学近似；倾斜、遮挡和鱼眼投影不能直接照套。

<!-- aria-figure: boxer-depth -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-depth.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-depth.svg" width="1100" height="500" alt="自制图 1：按相似三角形绘制的尺度歧义。物体尺寸与深度同时加倍，图像高度不变；这是教学几何，不是检测输出。" loading="lazy" /></a>
  <figcaption>自制图 1 · 按相似三角形绘制的尺度歧义。物体尺寸与深度同时加倍，图像高度不变；这是教学几何，不是检测输出。</figcaption>
</figure>
<!-- /aria-figure -->

### Aria 提供的，不只是另一张 RGB 照片

带标定与定位的设备能提供像素的真实三维射线、重力方向，以及 SLAM 重建的有尺度点云。三者回答不同问题：射线解决“这块图像朝哪里看”，重力解决“竖直朝哪里”，点云提供“某些表面离相机多远”。

BoxerNet 允许没有深度输入，此时依赖图像中的大小和场景先验。但**没有深度不等于没有标定，也不等于没有尺度歧义**。而要把多帧结果合并到一个世界地图，仍需要相机在统一坐标系中的位姿。

## 2. 先分清 Boxer 与 BoxerNet 的输入输出

<!-- aria-figure: boxer-2 -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-2.webp" width="1166" height="462" alt="Boxer 原论文 Figure 2：Boxer 完整系统：二维检测、单帧提升、跨视角融合分别承担不同职责。" loading="lazy" /></a>
  <figcaption>Boxer 原论文 Figure 2 · Boxer 完整系统：二维检测、单帧提升、跨视角融合分别承担不同职责。 <a href="https://arxiv.org/pdf/2604.05212v1#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

给定图像 $I$、二维检测框 $b_i^{2D}$、标定与重力，可选深度输入，BoxerNet 输出

$$
\hat b_i^{3D}=(\hat x_i,\hat y_i,\hat z_i,\hat w_i,\hat h_i,\hat d_i,\hat\theta_i).
$$

前三项是中心，接着三项是物理边长，单位为米；最后一项是绕重力轴的 yaw，单位为弧度。输出在**重力对齐的相机坐标**中。它是 7 自由度盒子：模型假定竖直方向已经给定，并不预测物体任意倾倒时的完整三维朝向。

全系统再用相机位姿把中心和朝向变换到世界坐标，融合成每个静态实体的一个框。二维类别与分数来自 DETIC、OWLv2 等外部检测器，BoxerNet 主要学习几何提升。因而换一个更强二维检测器有机会改善覆盖率，但也会改变框的松紧、遮挡模式及分数分布。

## 3. 网络怎么把图像、射线与稀疏点云放在一起？

### 用 patch 中位深度保留尺度，允许空缺

DINOv3 为每个图像 patch 提供视觉特征。标定模型把 patch 中心反投影成单位射线，再转入重力对齐坐标。论文描述将可见点云投影回图像后，每个 patch 计算落入其中的深度中位数；没有点的 patch 写入 $-1$ 这个缺失标记。

假设一个 patch 的有效深度为 $1.9,2.0,2.1,8.0$ 米，中位数为 $2.05$ 米。均值则为 $3.5$ 米，会明显被远处背景牵走。这解释了中位数的鲁棒直觉，但不保证它总是物体深度：如果多数点本来就来自后面的墙，中位数也会落在墙上。另一个完全没点的 patch 不能写成零米，因为“未知”与“贴着相机”是不同含义。

<!-- aria-figure: boxer-patches -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-patches.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-patches.svg" width="1100" height="500" alt="自制图 2：四个有效像素深度的普通中位数为 2.05 m，均值为 3.50 m。论文描述中位数，所核查公开代码的稀疏点分支实际取均值；此图比较两种聚合的行为。" loading="lazy" /></a>
  <figcaption>自制图 2 · 四个有效像素深度的普通中位数为 2.05 m，均值为 3.50 m。论文描述中位数，所核查公开代码的稀疏点分支实际取均值；此图比较两种聚合的行为。</figcaption>
</figure>
<!-- /aria-figure -->

这里有一处必须区分论文和发布代码：在核查的[公开提交 `1f86542dc342`](https://github.com/facebookresearch/boxer/blob/1f86542dc342a4b1d474c87c97c5d1d6566d9148/boxernet/boxernet.py)中，`sdp_to_patches` 先对投到同一像素的点取平均，再对 patch 内有效像素取**均值**，空 patch 仍为 $-1$。文件中虽有 `masked_median` 函数与 median 注释，这条路径并未调用它。因此上图解释论文所写的稳健聚合直觉，不能据此断言当前发布实现采用中位数。

这些信息按位置拼在一起：

$$
\mathbf f_p=[\mathbf f_p^{\rm img};\mathbf d_p^g;z_p],\qquad
\mathbf d_p^g=R_{g\leftarrow c}\operatorname{unproject}(\mathbf u_p).
$$

这里射线有三个分量；本地相机原点固定为零，因此无需把全球平移加入每个 patch。鱼眼的反投影必须使用对应标定，不能把普通 $K^{-1}(u,v,1)^\mathsf T$ 当作所有镜头的通用表达。

### 二维框是 query，整幅图像是上下文

<!-- aria-figure: boxer-3 -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-3.webp" width="1166" height="523" alt="Boxer 原论文 Figure 3：BoxerNet：图像、射线与可选深度按 patch 编码，二维框作为独立查询。" loading="lazy" /></a>
  <figcaption>Boxer 原论文 Figure 3 · BoxerNet：图像、射线与可选深度按 patch 编码，二维框作为独立查询。 <a href="https://arxiv.org/pdf/2604.05212v1#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

编码器先在所有 patch 间做自注意力，让局部外观与场景深度交换信息。二维框的四个坐标经线性映射变成 query，再向整幅图像的 patch token 做交叉注意力。这让“杯子框”不只看到杯子内部，还能利用桌面、附近物体与可见深度来推断尺度。

不同框的 query **彼此不做注意力**。因此改变输入框顺序，只应改变对应输出顺序；它没有在这个阶段学一套联合去重规则。逐帧重复、跨帧重复，仍由后面的系统处理。

解码后的每个框走两个预测头：一个给 7 自由度盒子，一个给不确定性。后者的意义，是区分“二维检测器非常确信它是杯子”与“我们非常确信杯子的三维位置”。

## 4. 监督从哪里来：三维标注怎样变成一帧训练样本？

### 三维框存在，不代表这一帧看得见

训练数据来自内部 Aria／Quest 数据，以及 NymeriaPlus、CA-1M、ScanNet、SUN-RGBD 等来源。作者以约 122 万个**独立三维框**描述规模，特意区别于同一物体在大量帧中的重复观测。

把三维框八个角投到图像中，确实可以生成一个二维框，却可能“穿墙”：物体被墙挡住时，投影仍在图像内。作者利用可见深度检查至少两个可见点位于三维框内，再要求沿框边采样的点有足够比例位于相机有效成像区域，阈值为 80%。这里两个检查分别补充遮挡证据与视场覆盖；仅在图像内并不等价于物理可见。

### 检测框很紧，投影框很松，训练会错位

杯子的三维盒子投影，可能包含大片并非杯子的背景；部分遮挡时差异更大。作者用投影框提示 SAM，再从分割结果生成较紧的二维框，同时扰动二维框，使网络见到更接近推理检测器的输入。

<!-- aria-figure: boxer-7 -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-7.webp" width="1169" height="1192" alt="Boxer 原论文 Figure 7：四类增强：光度、相机、深度点与二维框；最后一行比较投影框和 SAM 收紧框。" loading="lazy" /></a>
  <figcaption>Boxer 原论文 Figure 7 · 四类增强：光度、相机、深度点与二维框；最后一行比较投影框和 SAM 收紧框。 <a href="https://arxiv.org/pdf/2604.05212v1#page=18" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 7 的最后一行值得仔细看：桌子遮住椅子时，“完整三维盒子的投影”与“可见区域的紧框”不是同一个东西。前几行分别模拟亮度变化、标定变化、稀疏点缺失，其中整批丢掉深度也训练了图像独立工作的能力。增强在训练中改变输入，三维真值仍要保持对应关系，不能凭空跟着二维框扩大而扩大真实物体。

## 5. 不确定性损失：为什么困难样本可以少罚，却不能永远逃避？

### 用角点集合比较几何，减轻等价盒子参数的歧义

两个盒子可能有不同的 yaw 与宽深排列，却占据同一空间。例如绕竖直轴转 $90^\circ$ 再交换水平边长，可以表示同一个几何盒子。直接对七个参数逐项做误差，不一定尊重这种对称性。

论文用预测框和真值框角点之间的 Chamfer 几何损失。为了理解其作用，可以看下面这个常见的对称平方距离写法；这是教学展开，原文没有明确给出角点归约的完整实现细节：

$$
D(P,Q)=\frac1{|P|}\sum_{\mathbf p\in P}\min_{\mathbf q\in Q}\|\mathbf p-\mathbf q\|_2^2
+\frac1{|Q|}\sum_{\mathbf q\in Q}\min_{\mathbf p\in P}\|\mathbf q-\mathbf p\|_2^2.
$$

第一项惩罚预测角点离真值远，第二项防止预测只覆盖真值角点的一小部分。它约束的是三维几何集合，**不是最终评测的三维 IoU 本身**；相同角点距离在小物体上可能导致更大的 IoU 损失。

### 不确定性调节的是这一个样本的几何误差

论文的核心训练式为

$$
\mathcal L=D\exp(-\hat\sigma)+\hat\sigma.
$$

附录把 $\hat\sigma$ 描述为 log-variance。它不是一个可直接当标准差使用的米制数。第一项随不确定性增大而减小，第二项惩罚无节制增大不确定性。固定 $D>0$ 时：

$$
\frac{\partial\mathcal L}{\partial\hat\sigma}=1-D\exp(-\hat\sigma),\qquad
\hat\sigma^*=\log D.
$$

例如在一个固定归一化约定下取 $D=4$：$\hat\sigma=0$ 时损失为 $4$；取 $\log4$ 时为 $1+\log4\approx2.386$；取 $4$ 时反而约为 $4.073$。所以网络可以承认某个样本难，但不能靠无限放大不确定性把总损失压到零。改变距离单位、平方与否或平均方式，都会改变 $D$ 的数值及这个平衡点。

<!-- aria-figure: boxer-loss -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-loss.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-loss.svg" width="1100" height="500" alt="自制图 3：直接计算 D=4 时的损失曲线。最优 log-variance 为 log 4≈1.386；蓝线为加权几何误差，灰线为不确定性惩罚，红线为总和。" loading="lazy" /></a>
  <figcaption>自制图 3 · 直接计算 D=4 时的损失曲线。最优 log-variance 为 log 4≈1.386；蓝线为加权几何误差，灰线为不确定性惩罚，红线为总和。</figcaption>
</figure>
<!-- /aria-figure -->

推理时，作者定义

$$
s^{3D}=\operatorname{sigmoid}(-\hat\sigma),\qquad
s=\frac{s^{2D}+s^{3D}}2.
$$

这是用于排序的启发式分数，并非严格校准的“盒子正确概率”。$s^{2D}=0.9$、$s^{3D}=0.3$ 时，最终分数为 $0.6$。几何歧义会拉低语义高置信检测的排名。

<!-- aria-figure: boxer-6 -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-6.webp" width="765" height="699" alt="Boxer 原论文 Figure 6：CA-1M、IoU 0.25 下的 PR 曲线：二维与三维置信度平均改善排序。" loading="lazy" /></a>
  <figcaption>Boxer 原论文 Figure 6 · CA-1M、IoU 0.25 下的 PR 曲线：二维与三维置信度平均改善排序。 <a href="https://arxiv.org/pdf/2604.05212v1#page=17" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 6 在相同 IoU 阈值下比较三种排序，平均分数带来更好的 PR 曲线。这里证明的是置信排序有用，不能据此推出每个框的几何都因后处理变得更准；训练不确定性对回归的作用还需看消融。

## 6. 一百帧里的同一个杯子，怎样只留下一个？

### 先统一坐标，再判断是不是同一物体

设局部中心为 $\mathbf c_g$，世界变换为 $(R_{w\leftarrow g},\mathbf t_{w\leftarrow g})$：

$$
\mathbf c_w=R_{w\leftarrow g}\mathbf c_g+\mathbf t_{w\leftarrow g}.
$$

若两帧分别把杯子放在自身前方一米，而两帧相机已经移动，两份“前方一米”不能直接相加或平均。只有转到共同世界坐标，才能检验它们是否落在相同体积。

离线融合把每个检测当成图节点。两个框三维 IoU 达到阈值且文本语义相近，才连边；连通分量作为物体簇。附录默认关联 IoU 阈值为 $0.3$，融合后 NMS 阈值为 $0.6$。连通分量有传递性：A 连 B、B 连 C，不要求 A 与 C 本身也高度重叠，因此错误桥接可能把不同实体合并。

### 朝向不能直接做普通平均

簇内先处理 $90^\circ$ 对称性与宽深交换，再按置信度平均位置和尺寸。长方体本身还具有 $180^\circ$ 等价性，因此公开实现的 yaw 均值用**倍角**计算：

$$
\bar\theta=\frac12\operatorname{atan2}
\left(\sum_iw_i\sin2\theta_i,\sum_iw_i\cos2\theta_i\right).
$$

例如，尺寸已经对齐的两个非正方形盒子分别为 $89^\circ$ 和 $-89^\circ$，它们实际几乎重合；普通平均给 $0^\circ$，把长短轴转错了，倍角均值则接近等价的 $90^\circ$。

<!-- aria-figure: boxer-fusion -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-fusion.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-fusion.svg" width="1100" height="500" alt="自制图 4：俯视教学示意。左侧同一静态物体可融合，右侧红框是不同时间观测的置信加权结果，不对应这三个观测时刻中的任何一个；采样位置和权重保存在脚本中。" loading="lazy" /></a>
  <figcaption>自制图 4 · 俯视教学示意。左侧同一静态物体可融合，右侧红框是不同时间观测的置信加权结果，不对应这三个观测时刻中的任何一个；采样位置和权重保存在脚本中。</figcaption>
</figure>
<!-- /aria-figure -->

<!-- aria-figure: boxer-5 -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-5.webp" width="1169" height="754" alt="Boxer 原论文 Figure 5：把逐帧框叠到统一世界坐标中；更集中的伪热图表示跨帧估计更一致。" loading="lazy" /></a>
  <figcaption>Boxer 原论文 Figure 5 · 把逐帧框叠到统一世界坐标中；更集中的伪热图表示跨帧估计更一致。 <a href="https://arxiv.org/pdf/2604.05212v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 5 把融合前的逐帧框叠起来看：集中的边缘说明估计较一致。它不是精确概率密度图，也不是最终融合后的 AP。正文实验使用离线融合；附录另有在线跟踪模式，不能把其实现存在当作论文所有实验都在线完成。

## 7. 实验怎么读：先问框从哪里来，再问用了什么深度

### mAP 在这里不考类别名是否正确

本文按三维 IoU 从 $0.05$ 到 $0.5$、步长 $0.05$ 计算 AP 后平均，且采用 **class-agnostic** 协议：把所有类别视为“物体”。所以这个分数主要检验覆盖与几何，不能拿来证明“开放词汇类别全都识别正确”。

下面摘录原论文 Table 2 的逐帧结果。同一列才是同一测试集；GT2D 表示给了真值二维框，是隔离提升能力的理想输入。

| 二维框与提升模型 | 几何输入 | NymeriaPlus mAP | CA-1M mAP |
| --- | --- | ---: | ---: |
| GT2D + CuTR | RGB | 0.010 | 0.119 |
| GT2D + BoxerNet | RGB | 0.296 | 0.126 |
| GT2D + CuTR | RGB + 稠密深度 | 未报告 | 0.250 |
| GT2D + BoxerNet | RGB + 可用深度 | 0.532 | 0.412 |
| OWLv2 + BoxerNet | RGB | 0.061 | 0.081 |
| OWLv2 + BoxerNet | RGB + 可用深度 | 0.297 | 0.204 |

NymeriaPlus 的“可用深度”是 SLAM 稀疏点云，CA-1M 是稠密深度。**摘要中 0.532 对 0.010 不能读成两个纯 RGB 模型的同条件比较。** 纯 RGB、GT2D 下应比较 0.296 对 0.010。CA-1M 的 0.412 对 0.250 才是这两种提升方法都获得稠密深度的对比。

<!-- aria-figure: boxer-4 -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-4.webp" width="1169" height="892" alt="Boxer 原论文 Figure 4：逐帧三维 IoU 的定性比较；黄色表示与真值重叠更好，须同时区分二维框来源。" loading="lazy" /></a>
  <figcaption>Boxer 原论文 Figure 4 · 逐帧三维 IoU 的定性比较；黄色表示与真值重叠更好，须同时区分二维框来源。 <a href="https://arxiv.org/pdf/2604.05212v1#page=12" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 4 的 GT2D 列和 OWLv2 列不能混看。理想二维框与真实检测之间的差距提醒我们：提升网络再强，也救不回上游完全没提出的物体。

### 融合并不保证每一项分数都升高

原论文 Table 3 中，OWLv2 + BoxerNet 在 NymeriaPlus 的 RGB 结果由逐帧 $0.061$ 变为场景级 $0.145$；但带稀疏深度时是逐帧 $0.297$、场景级 $0.278$。两种评测的对象集合与重复框处理不同，不能把差值当成纯粹的“融合模块收益”。同理，场景级去重有助于应用，不代表任何融合阈值都提高所有指标。

### 哪个改动最重要？消融要保留原表基线

原论文 Table 4 的 NymeriaPlus 完整模型是 $0.518$，不同于主表的 $0.532$；这里沿用消融自身基线，不擅自把它们混成一组。

| 消融设置，GT2D 输入 | NymeriaPlus mAP | CA-1M mAP |
| --- | ---: | ---: |
| 完整模型 | 0.518 | 0.412 |
| 去掉不确定性头 | 0.485 | 0.401 |
| 只用公开训练数据 | 0.463 | 0.376 |
| 去掉深度 | 0.279 | 0.126 |
| 只用 CA-1M 训练 | 0.002 | 0.357 |

从这张表看，深度与跨设备数据覆盖都非常重要。不能把全部提升归因于“不确定性头”，也不能把只在 CA-1M 训练后的跨域失败，简单归因于某一种 Transformer 架构不好。

<!-- aria-figure: boxer-10 -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-10.webp" width="1166" height="415" alt="Boxer 原论文 Figure 10：按物体体积分桶的 PR 曲线；小物体解释了较大部分性能差距。" loading="lazy" /></a>
  <figcaption>Boxer 原论文 Figure 10 · 按物体体积分桶的 PR 曲线；小物体解释了较大部分性能差距。 <a href="https://arxiv.org/pdf/2604.05212v1#page=23" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 10 将 CA-1M 物体按体积分成小于 $0.01\,\mathrm m^3$、$0.01$ 至 $0.1\,\mathrm m^3$、大于 $0.1\,\mathrm m^3$ 三组，IoU 阈值为 $0.25$。小物体的 PR 差距较明显；对小物体而言，几厘米位移就可能丢掉很大比例的体积重叠。

## 8. 补充实验：伪标注的价值与比较的边界

<!-- aria-figure: boxer-8 -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-8.webp" width="1165" height="466" alt="Boxer 原论文 Figure 8：ScanNet 的既有闭集标注与 Boxer 开放集伪标注；覆盖变多不等于新增人工真值。" loading="lazy" /></a>
  <figcaption>Boxer 原论文 Figure 8 · ScanNet 的既有闭集标注与 Boxer 开放集伪标注；覆盖变多不等于新增人工真值。 <a href="https://arxiv.org/pdf/2604.05212v1#page=21" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 8 的意义是把已有闭集扫描扩展为更密的开放集候选标注。新增框来自模型，类别也继承二维检测与多帧聚合；它们适合做待审核伪标签，不能直接等同于可靠的全量真值。

<!-- aria-figure: boxer-9 -->
<figure>
  <a href="/HomepageX/media/boxernet/boxer-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/boxernet/boxer-9.webp" width="991" height="1010" alt="Boxer 原论文 Figure 9：SAM3 与 SAM3D 的 ADT 样例；同时观察二维投影与三维、俯视视角。" loading="lazy" /></a>
  <figcaption>Boxer 原论文 Figure 9 · SAM3 与 SAM3D 的 ADT 样例；同时观察二维投影与三维、俯视视角。 <a href="https://arxiv.org/pdf/2604.05212v1#page=22" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 9 展示 SAM3 + SAM3D 的对照，原论文 Table 5 使用 ADT 的 100 张图、缩减后的类别提示，并给两者相同 SAM3 检测与稠密真值深度。mAP 为 SAM3D 的 $0.027$、BoxerNet 的 $0.064$。召回率很低的部分原因是提示类别少、评测对象却仍然较多；这不是完整开放世界检测榜单，也不能说明 BoxerNet 具备 SAM3D 的网格与纹理输出能力。

## 9. 它在哪里失效，下一层该补什么？

回到厨房：如果你拿起杯子，静态融合假设立刻被破坏。旧位置和新位置可能被拆成多个实体，也可能经错误连接融合到中间。若目标是移动物体，应该显式建模轨迹和时间，不能只不断提高静态 NMS 阈值。

电线、藤蔓和严重倾斜的物体也难由重力对齐盒子表达。盒子是紧凑的位置摘要，不是碰撞精度足够的表面网格。错误标定、重力估计、二维漏检，则分别污染射线、盒子朝向与候选覆盖。

论文报告的约 $20\,\mathrm{ms}$ 是 RTX 4090、$960\times960$、bfloat16 条件下的 **BoxerNet 提升前向**。二维检测器、SLAM、点云生成与全局融合另有成本。开源仓库提供推理与模型，内部训练数据并未全部公开；能跑 demo 与能原样复现训练是两件不同的事。

最值得带走的设计，是先用可靠几何接口接住成熟语义模型，再让网络专注几何缺口。下一篇 [LAMP](/HomepageX/blog/3d-perception-and-project-aria/lamp/)把“静态物体框”换成“持续运动的人”，继续利用已知设备位姿，把观察者自己的运动先拿掉。

## 参考资料

- [Boxer，固定版本 v1，含完整附录](https://arxiv.org/abs/2604.05212v1)
- [Boxer 官方项目](https://facebookresearch.github.io/boxer/)与[推理实现](https://github.com/facebookresearch/boxer)
- [Project Aria 原始设备论文](https://arxiv.org/abs/2308.13561)
