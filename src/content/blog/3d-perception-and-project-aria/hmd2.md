---
title: "HMD² 精读：只戴一副眼镜，为什么也能生成全身动作？"
description: "拆解头部条件、CLIP、局部点云和动作扩散，推导重叠窗口补全；区分合理生成、真实重建与低延迟部署的代价。"
date: 2026-09-29
tags: [论文精读, 3D Perception, Project Aria, HMD2, 扩散模型]
draft: false
---

站在厨房里，你的眼镜能看见水槽、桌面，也可能偶尔看见伸出去的手。但当你面对水槽不动时，腿可能站直、微蹲，也可能一只脚踩在低台阶上。相机几乎看不到这些区别。

这个问题与 [LAMP](/HomepageX/blog/3d-perception-and-project-aria/lamp/)不同：LAMP 观察别人，HMD² 生成**佩戴者自己**的动作。后者不能仅靠更强的网络，把从未进入传感器的信息变成唯一真值。它要做的是：尽可能服从已知观测，同时为不可见的部分保留合理变化。

本文固定阅读 Vladimir Guzov、Yifeng Jiang 等的 *HMD²: Environment-aware Motion Generation from Single Egocentric Head-Mounted Device*，[arXiv v2](https://arxiv.org/abs/2409.13426v2)，3DV 2025，并覆盖附录。名字可理解为从 HMD 进行 Human Motion Diffusion；论文的重点是有环境条件的动作生成。

<!-- aria-figure: hmd2-1 -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-1.webp" width="1653" height="848" alt="HMD² 原论文 Figure 1：外向相机只看到环境和少量身体，系统生成与头部及场景相容的全身动作。" loading="lazy" /></a>
  <figcaption>HMD² 原论文 Figure 1 · 外向相机只看到环境和少量身体，系统生成与头部及场景相容的全身动作。 <a href="https://arxiv.org/pdf/2409.13426v2#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

## 1. 第一层歧义：知道头在哪里，身体也未必唯一

### 同一个头部位姿，可以配不同的膝盖和手臂

头部的六自由度位姿约束很强：我们知道人在什么地方、头朝哪里。但人体有很多关节，固定头部不能固定所有肢体。坐在椅子上、蹲下、跪坐，可能产生近似相同的头部高度。

如果直接训练一个确定性回归器，用平方误差面对多个同样合理的目标，它倾向于给出条件平均值。可“坐下”与“蹲下”的关节坐标平均，不一定是自然的人体动作，可能变成悬在半空的中间姿态。

<!-- aria-figure: hmd2-ambiguity -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-ambiguity.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-ambiguity.svg" width="1100" height="500" alt="自制图 1：两个人工骨架共享头部位置，分别呈坐姿与蹲姿。环境和语义可减少歧义，但无法证明不可见肢体只有一个真实解。" loading="lazy" /></a>
  <figcaption>自制图 1 · 两个人工骨架共享头部位置，分别呈坐姿与蹲姿。环境和语义可减少歧义，但无法证明不可见肢体只有一个真实解。</figcaption>
</figure>
<!-- /aria-figure -->

这张图不是说扩散模型永远优于回归。若观测足以确定唯一解，回归很有效。HMD² 的场景恰好处于信息严重不足的一侧：生成模型用分布表达多个解，而环境和视觉条件把明显不相容的解排除。

### 一个设备不等于一颗 RGB 传感器

论文输入是头戴设备的多模态信息：外向 RGB 图像、SLAM 头部轨迹及其环境点云。SLAM 本身可以使用设备的其他相机与惯性传感器。因此不能把结果描述成“完全无标定的单张 RGB 恢复全身”，也不能混同于直接朝下拍摄整个身体的鱼眼系统。

<!-- aria-figure: hmd2-3 -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-3.webp" width="797" height="194" alt="HMD² 原论文 Figure 3：连续第一人称图像中，手臂只间歇出现，完整身体并不可见。" loading="lazy" /></a>
  <figcaption>HMD² 原论文 Figure 3 · 连续第一人称图像中，手臂只间歇出现，完整身体并不可见。 <a href="https://arxiv.org/pdf/2409.13426v2#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 3 中只有少量身体部位间歇出现。这个事实解释了为什么专门在完整人体图像上训练的骨架编码器，在这里未必是最佳选择。

## 2. 三种条件，分别补上哪一块信息？

<!-- aria-figure: hmd2-2 -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-2.webp" width="1655" height="817" alt="HMD² 原论文 Figure 2：头部运动、CLIP 图像特征和局部点云特征共同条件化动作扩散。" loading="lazy" /></a>
  <figcaption>HMD² 原论文 Figure 2 · 头部运动、CLIP 图像特征和局部点云特征共同条件化动作扩散。 <a href="https://arxiv.org/pdf/2409.13426v2#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

### 头部轨迹给出运动锚点

每帧条件包含位置 $\mathbf t$、旋转 $R$，以及由时间差分得到的线速度 $\mathbf v$ 和角速度 $\boldsymbol\omega$：

$$
\mathbf p=\{\mathbf t,R,\mathbf v,\boldsymbol\omega\}.
$$

每个动作窗口相对第一帧做规范化，避免模型绑定一个固定房间原点。沿楼梯上下时，局部窗口仍保留头部升降；不能把每帧高度都归零，否则正好删掉了重要地形线索。

模型预测 23 个关节的局部旋转，每个旋转使用旋转矩阵前两列的 6D 表示。因此输出 $x\in\mathbb R^{T\times138}$，不是直接回归每个关节的世界三维坐标。全局运动在推理时通过头部轨迹“接回去”，让生成身体的头部与已知设备运动对齐。

一个容易漏掉的实验条件是：论文在可视化和位置误差计算时使用各受试者的**真值骨长**。模型本身不以体型为条件，不等于其关节位置评测已经解决未知用户的身体尺度校准。

### CLIP 提供语义线索，但不是精确手腕坐标

图像经过 CLIP ViT-L/14 编码。它可能告诉模型“手正在水槽附近”“左手抬起来了”，也能利用物体和场景暗示动作。论文没有把这一步实现成显式文字生成；这些语义解释是理解图像 embedding 的直觉。

30 Hz RGB 特征重复一次用于 60 Hz 动作条件，重复不会产生新的视觉信息。相邻动作帧虽然都能计算不同姿态，却可能共享同一图像描述。

更关键的是：CLIP 的全局语义特征不等于像素级关键点检测。知道“手举起来”仍不能可靠确定每个手指、腕部深度或精确接触位置，这也是作者后面承认的局限。

### 局部点云告诉模型地板与支撑物大概在哪里

对每帧，在头部下方一米处取中心，截取 $2\times2\times2$ 米立方体。局部网格只随头部绕重力轴旋转，不随低头动作把“地板”也倾斜。

它不是二值占据网格。附录使用 $10\times10\times10$ 个体素，每个体素中心 $\mathbf v_j$ 存到最近 SLAM 点的距离，并截断到 $0.1$ 米：

$$
a_j=\min\left(0.1,\min_{\mathbf s\in S}\|\mathbf v_j-\mathbf s\|_2\right).
$$

距离为 $0.03$ 米的体素记录 $0.03$；距离为 $0.4$ 米则只记 $0.1$。这个压缩告诉模型附近是否有可见表面，却不能可靠区分“这里真是空的”与“无纹理导致这里没重建出点”。

<!-- aria-figure: hmd2-voxel -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-voxel.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-voxel.svg" width="1100" height="500" alt="自制图 2：按人工稀疏点计算最近距离并在 0.1 m 截断，颜色只用于展示该数值。左侧为 2 m 立方体的示意投影，右侧为其中一个教学切片。" loading="lazy" /></a>
  <figcaption>自制图 2 · 按人工稀疏点计算最近距离并在 0.1 m 截断，颜色只用于展示该数值。左侧为 2 m 立方体的示意投影，右侧为其中一个教学切片。</figcaption>
</figure>
<!-- /aria-figure -->

点云自编码器预训练后输出 128 维特征。它压缩局部空间布局，提供坐姿、地面高度和附近支撑物的线索。但稀疏特征点通常偏爱桌角、纹理与边缘，光滑地板可能正是缺点最多的地方。

## 3. 扩散模型学的是什么：在观测条件下还原干净动作

### 先明确两种“时间”

动作的时间轴是四秒、240 帧的序列；扩散的时间轴是逐步加噪和去噪的步骤。为避免混淆，下面用 $n$ 表示动作帧，用 $s$ 表示扩散步。

将三种条件拼成

$$
c_n=[\mathbf p_n;E_I(I_n);E_S(V(S_n))].
$$

扩散噪声施加在动作 $x_0$ 上，不施加在条件 $c$ 上。按论文的累计噪声系数 $\alpha_s$，前向过程是

$$
x_s=\sqrt{\alpha_s}x_0+\sqrt{1-\alpha_s}\,\epsilon,
\qquad \epsilon\sim\mathcal N(0,I).
$$

取一维教学值 $x_0=0.8$、$\alpha_s=0.64$、$\epsilon=-0.5$，则 $x_s=0.8\times0.8+0.6\times(-0.5)=0.34$。这个数值是动作表示空间的分量，不是把人体关节物理地移动到 $0.34$ 米。

### 训练目标是干净动作，而不是默认的噪声预测

去噪网络使用时序 Transformer，输入 $(x_s,c,s)$，预测 $\hat x_0=D(x_s,c,s)$。原文使用干净动作重建的平方误差：

$$
\mathcal L=\mathbb E_{x_0,s,\epsilon}
\left[\|D(x_s,c,s)-x_0\|_2^2\right].
$$

监督来自同步 Xsens 动作；随机噪声与步数由训练程序产生。假设上面例子里网络预测 $0.7$，该分量误差为 $(0.7-0.8)^2=0.01$。同一个干净动作可在不同噪声强度下反复构成训练样本。

这篇工作没有靠额外的接触、碰撞或穿地损失来强行修补动作，而是通过动作分布与条件学习。**因此环境相容是学到的倾向，不是绝对保证。** 输出全零或所有帧一样，在变化丰富的真值动作上不会取得低损失。

<!-- aria-figure: hmd2-diffusion -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-diffusion.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-diffusion.svg" width="1100" height="500" alt="自制图 3：使用固定随机种子绘制概念曲线；标量例按正文的前向加噪公式计算。真实模型对整段关节旋转序列生成，训练预测干净动作。" loading="lazy" /></a>
  <figcaption>自制图 3 · 使用固定随机种子绘制概念曲线；标量例按正文的前向加噪公式计算。真实模型对整段关节旋转序列生成，训练预测干净动作。</figcaption>
</figure>
<!-- /aria-figure -->

生成时从噪声开始，网络反复预测干净动作，再根据反向扩散更新当前状态。论文推理默认使用 20 个跨步采样步骤。最终 6D 旋转参数需转换为合法旋转矩阵；加噪空间中的中间值不必本身都是合法的人体姿态。

## 4. 四秒模型如何生成十五分钟连续动作？

### 独立生成窗口，会在拼接处换一套身体

如果四秒片段各自采样，前一段最后还在蹲着，后一段第一帧可能已经站直。即使每段单看合理，长序列也会跳变。

HMD² 使用自回归 inpainting。窗口长 $T$，每次前进 $h$ 帧，与上一窗口重叠 $T-h$ 帧。在每一次反向扩散中，将预测的干净动作写成

$$
\hat x_0\leftarrow m\odot D(x_s,c,s)+(1-m)\odot\hat x_0^{\rm prev,shift}.
$$

掩码 $m$ 在重叠区为零，在新生成的末尾 $h$ 帧为一。上一窗口结果先左移 $h$ 帧，再填进重叠区。网络每轮看到的历史都一致，而不是最后生成完才把两段硬接上。

<!-- aria-figure: hmd2-4 -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-4.webp" width="797" height="450" alt="HMD² 原论文 Figure 4：每次反向扩散都用上一窗口覆盖重叠区，保持长序列衔接。" loading="lazy" /></a>
  <figcaption>HMD² 原论文 Figure 4 · 每次反向扩散都用上一窗口覆盖重叠区，保持长序列衔接。 <a href="https://arxiv.org/pdf/2409.13426v2#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

### “不依赖未来窗口”仍然有当前块的等待

默认高质量设置 $h=180$，对应约三秒一块；低延迟设置 $h=10$，对应约 $0.17$ 秒一块。论文写出的最早帧等待公式为 $(h-1)\Delta t$：在 60 Hz 下，$h=10$ 是 $9/60=0.15$ 秒，而 $10/60\approx0.167$ 秒是块时长。本文保留论文的“约 0.17 秒”称呼，同时区分这两个计数约定。

<!-- aria-figure: hmd2-window -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-window.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-window.svg" width="1100" height="500" alt="自制图 4：按真实帧数比例绘制 240 帧窗口。蓝色是重叠历史，金色是新增块；右侧数字是新增块时长，首帧最大前视间隔为 (h−1)/60。" loading="lazy" /></a>
  <figcaption>自制图 4 · 按真实帧数比例绘制 240 帧窗口。蓝色是重叠历史，金色是新增块；右侧数字是新增块时长，首帧最大前视间隔为 (h−1)/60。</figcaption>
</figure>
<!-- /aria-figure -->

较小 $h$ 给每个新动作更少的后续观测，也增加每单位输出帧的重复推理。低延迟并非免费；论文附录的小步长消融中，$h=1$ 的姿态与 FID 都明显恶化。这个趋势不是说“实时不可行”，而是单个模型的长上下文与输出响应速度有真实取舍。

## 5. 怎么评价“合理”，又怎么评价“准确”？

### 一个平均位置误差，不够评价生成系统

HMD² 同时看重三个维度。MPJPE 和 Hand PE 衡量重建准确性；FID 在动作自编码器的特征空间比较预测与真值分布；Diversity 看生成动作的多样性；Physicality 与脚滑相关；Floor Penetration 估算穿过支撑面的程度。

其中 Diversity 与 Physicality 的箭头指向右，意思是**接近真值统计更好**，不是无限大或无限小更好。一个把手臂乱甩的模型可能很“多样”，却不忠实于观测；一个完全不动的模型可能很平滑，却不像真实日常动作。

穿地指标也没有使用完整真实碰撞网格。作者用邻近 20 秒真值动作的最低关节高度作保守地面代理，所以床上躺卧、楼梯及多层环境下，它是一个有条件的误差度量。

### 主结果使用完整长序列，单位是厘米

Nymeria 过滤后划分为 202／3／56 小时的训练、验证、测试集，测试人物与地点未出现在训练中。测试共 224 段，平均约 15 分钟；没有切成短片段重置历史。随机方法每段运行八次，主表报告均值而非挑最好的一次。

| 方法，原论文 Table 1 | MPJPE，cm ↓ | Hand PE，cm ↓ | FID ↓ | Diversity，接近 16.13 | 穿地，cm ↓ |
| --- | ---: | ---: | ---: | ---: | ---: |
| EgoEgo | 16.61 | 34.64 | 35.69 | 20.15 | 2.43 |
| AvatarPoser，仅头部 | 10.64 | 21.51 | 27.61 | 12.99 | 4.21 |
| HMD²，180 帧步长 | 8.36 | 16.64 | 2.16 | 15.74 | 1.03 |
| HMD²，10 帧步长 | 9.19 | 17.67 | 5.00 | 15.23 | 1.19 |

AvatarPoser 在这里屏蔽了腕部设备输入，EgoEgo 使用 Aria 给出的头部运动，并重新在相应数据上训练。因此这是作者控制输入后的实验，不是把其他论文各自最好的数字直接放到一起。

<!-- aria-figure: hmd2-5 -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-5.webp" width="1655" height="751" alt="HMD² 原论文 Figure 5：跪坐转换和抬手动作的定性比较；观察回归均值、条件缺失与低延迟的影响。" loading="lazy" /></a>
  <figcaption>HMD² 原论文 Figure 5 · 跪坐转换和抬手动作的定性比较；观察回归均值、条件缺失与低延迟的影响。 <a href="https://arxiv.org/pdf/2409.13426v2#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 5 先看跪坐转换的身体衔接，再看第二段交替抬手。图像条件能让可见手臂跟随观测，单头部模型却可能仍把手放下。另一个阅读点是低延迟与高延迟之间的细微差异，它们并不是同一个运行模式。

## 6. 点云和 CLIP 并不是两个可随意替换的条件

| 消融，180 帧步长 | MPJPE，cm ↓ | Hand PE，cm ↓ | FID ↓ | 穿地，cm ↓ |
| --- | ---: | ---: | ---: | ---: |
| 无点云、无 CLIP | 9.28 | 19.47 | 6.75 | 3.29 |
| 有点云、无 CLIP | 8.97 | 20.38 | 3.68 | 0.99 |
| 无点云、有 CLIP | 8.57 | 16.32 | 6.17 | 2.15 |
| 两者都有 | 8.36 | 16.64 | 2.16 | 1.03 |

数据来自原论文 Table 2。点云显著改善穿地与整体空间相容，但手部误差未必下降；CLIP 改善可见手部线索，却无法单独恢复地面约束。完整模型在 MPJPE 与 FID 上最好，但并不是这张表每个格子的最小值。保留这个细节，才能理解“互补”而不是简单相加的意思。

<!-- aria-figure: hmd2-7 -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-7.webp" width="797" height="861" alt="HMD² 原论文 Figure 7：去掉点云或图像条件后，坐姿与手部运动出现不同错误。" loading="lazy" /></a>
  <figcaption>HMD² 原论文 Figure 7 · 去掉点云或图像条件后，坐姿与手部运动出现不同错误。 <a href="https://arxiv.org/pdf/2409.13426v2#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 7 中，坐姿与手臂失误发生在不同消融上。它为表格提供了具体动作解释，但某个成功样例还不能证明所有序列都存在同样因果关系。

附录也比较 DINOv2、VC-1 与 CLIP 特征。CLIP 的多数综合结果更好，其他编码器在 Physicality 上略有优势；这支持当前任务上的取舍，不构成 CLIP 是通用人体几何编码器的证据。

## 7. 多次生成究竟该在哪些地方不同？

<!-- aria-figure: hmd2-6 -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-6.webp" width="801" height="654" alt="HMD² 原论文 Figure 6：相同头部条件下手臂和腿的多种合理解。" loading="lazy" /></a>
  <figcaption>HMD² 原论文 Figure 6 · 相同头部条件下手臂和腿的多种合理解。 <a href="https://arxiv.org/pdf/2409.13426v2#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

当手不在视场中，多种手臂姿态可以合理存在；头部高度相近时，跪与蹲也可能难分。Figure 6 说明模型输出不是唯一确定解。

<!-- aria-figure: hmd2-8 -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-8.webp" width="1655" height="842" alt="HMD² 原论文 Figure 8：相同输入的四次采样：可见部分应服从观测，不可见部分保留变化。" loading="lazy" /></a>
  <figcaption>HMD² 原论文 Figure 8 · 相同输入的四次采样：可见部分应服从观测，不可见部分保留变化。 <a href="https://arxiv.org/pdf/2409.13426v2#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 8 进一步比较同一输入的四次采样。理想结果应在可见手臂上保持一致，在看不到的腿和手上保留变化。EgoEgo 也能多样生成，但缺少环境与图像条件时，变化可能不服从地面或可见肢体。这就是“条件多样性”的实际含义。

所以不能只挑八次生成里最接近真值的一次展示为系统精度。采样分布是否集中在合理区域，与某次偶然命中，是不同的评估问题。

## 8. 平均误差之外：困难动作在哪里？

<!-- aria-figure: hmd2-9 -->
<figure>
  <a href="/HomepageX/media/hmd2/hmd2-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/hmd2/hmd2-9.webp" width="1667" height="646" alt="HMD² 原论文 Figure 9：按动作场景排序的关节误差，展示平均值掩盖的困难尾部。" loading="lazy" /></a>
  <figcaption>HMD² 原论文 Figure 9 · 按动作场景排序的关节误差，展示平均值掩盖的困难尾部。 <a href="https://arxiv.org/pdf/2409.13426v2#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 9 把 20 类活动按 MPJPE 排序。大部分普通动作较容易，少数长尾动作难很多。附录中，高质量模型在多地形户外行走场景的 MPJPE 为 $5.75$ cm，瑜伽与拉伸场景为 $17.21$ cm；后者下半身误差达 $31.27$ cm。头的位置可能很准，但看不见的膝盖、腿和支撑关系仍然错得很远。

论文所谓“top 5% error”也需要解释：附录实际在**每段序列内计算第 95 百分位误差，再跨序列平均**，不是把所有帧混在一起取最差 5% 后算均值。这样能避免指标完全由几段最难瑜伽录像支配。

两种条件同时加入后，该尾部 MPJPE 从 $18.31$ 降到 $15.49$ cm，穿地代理从 $12.91$ 降到 $4.22$ cm。改善明显，残余误差也不小，特别是需要精确接触与肢体位置的应用。

## 9. 从论文走到实时眼镜，还缺哪几步？

首先是地图可用性。附录明确当前实现使用整段约十五分钟序列聚合的 SLAM 点。动作生成可以在线衔接，不代表完整系统从陌生房间开始、第一帧就有同样丰富的地图。真实因果运行需要地图预建或在环境中积累；地图稀疏时的行为应另测。

其次是计算。论文主文在 A100 上报告低延迟模式超过 70 FPS，假设条件特征已预计算或并行处理；附录将 CLIP 与点云编码也计入同设备后约为 61 FPS。这是强 GPU 上的吞吐，不是眼镜芯片实测性能，更不等同于总端到端延迟。

最后是接触与精确姿态。点云可能漏掉白墙和地板，静态地图不会自动更新被搬动的椅子，CLIP 不精确定位手腕，模型也没有人体形状感知的自穿插修正。这些失败指向具体补充信息：更好的场景表面、显式手部几何、接触约束或额外可穿戴观测。

在本专栏中，这正好引向 [EgoForce](/HomepageX/blog/3d-perception-and-project-aria/egoforce/)：HMD² 能判断“手抬起来”，而 EgoForce 要进一步恢复“手腕离相机多少米、手掌怎样转、手指怎样弯”。两者能力互补，但论文没有报告把它们接成联合系统后的实测结果。

## 参考资料

- [HMD²，arXiv v2，含附录](https://arxiv.org/abs/2409.13426v2)
- [官方项目与动作视频](https://hmdsquared.github.io/)
- [Nymeria：多模态第一人称人体运动数据](https://arxiv.org/abs/2406.09905)
