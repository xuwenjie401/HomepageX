---
title: "Photoreal Reconstruction 精读：眼镜拍到的每一行，并不来自同一个瞬间"
description: "从滚动快门、VIBA 和曝光积分，到校正后的时间查找图与 Gaussian Splatting；理解第一人称照片级重建为何先要把相机建模正确。"
date: 2026-09-29
tags: [论文精读, 3D Perception, Project Aria, Gaussian Splatting, 场景重建]
draft: false
---

还是那间厨房。你戴着眼镜转头，画面里有桌腿、细密窗框、暗柜子和很亮的窗户。相机轨迹已经由 SLAM 算好，直接交给 Gaussian Splatting，为什么边缘仍然重影、细杆变粗，空中还飘着半透明碎片？

一个常见解释是三维表示不够强。但这里更基础的问题可能是：**渲染器假设整张图来自一个瞬间、一个位姿，而真实传感器逐行读出，并在曝光时间内积累光。** 输入与渲染模型不一致时，优化器会把相机误差“烤”进三维场景。

本文精读 Zhaoyang Lv 等的 *Photoreal Scene Reconstruction from an Egocentric Device*，SIGGRAPH 2025，固定使用 [arXiv v1](https://arxiv.org/abs/2506.04444v1)及附录。它就是本专栏所讨论的第一人称照片级重建工作，[官方代码名为 egocentric_splats](https://github.com/facebookresearch/egocentric_splats)。

## 训练资源、卡时与数据量

| 项目 | 这篇工作的资源口径 |
| --- | --- |
| 是否预训练 | 没有跨场景神经网络预训练；每段采集轨迹按场景优化 Gaussian 参数、颜色和相机/成像模型。 |
| 图像量 | 原图约 $2880\times2880$，校正到 $2400\times2400$；每第八张图留作验证，其余帧参与该场景优化。 |
| 计算量 | 默认 30K 次迭代，前 7.5K 次后启用滚动快门补偿；全部模型在单张 A6000 或 A100、$2400\times2400$ 分辨率上训练。论文没有给出墙钟时间；显存不足时改为逐次渲染只是调度方式，不等于减少总优化工作。 |

<!-- aria-figure: photoreal-1 -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-1.webp" width="1702" height="667" alt="Photoreal Reconstruction 原论文 Figure 1：暗且含噪的留出图像、普通重建、本文重建及提高渲染增益后的对照。" loading="lazy" /></a>
  <figcaption>Photoreal Reconstruction 原论文 Figure 1 · 暗且含噪的留出图像、普通重建、本文重建及提高渲染增益后的对照。 <a href="https://arxiv.org/pdf/2506.04444v1#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 1 依次展示含噪留出图像、普通重建、本文重建与提高渲染增益后的结果。右侧暗部更容易看清，不等于相机原来直接拍到了同样干净的图像；三维重建融合了多帧观测，并显式处理曝光与响应。

## 1. 为什么“有准确 SLAM”仍然不够？

### 设备定位精度与像素对齐精度不是一回事

SLAM 可以把你在房间里的位置估得足够准，使虚拟物体看起来稳定。但照片级重建要将多帧中窗框的同一个细边缘对齐到像素，要求更严格；RGB 传感器相对 SLAM 相机的外参、时间偏移、逐行读出与曝光都可能造成误差。

<!-- aria-figure: photoreal-2 -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-2.webp" width="821" height="497" alt="Photoreal Reconstruction 原论文 Figure 2：Aria 传感器布局；RGB、SLAM 相机和 IMU 的角色不同。" loading="lazy" /></a>
  <figcaption>Photoreal Reconstruction 原论文 Figure 2 · Aria 传感器布局；RGB、SLAM 相机和 IMU 的角色不同。 <a href="https://arxiv.org/pdf/2506.04444v1#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 2 显示 Aria 的 RGB 相机、全局快门 SLAM 相机和 IMU。它们同处一副眼镜，不意味着曝光机制、时间采样和标定误差都相同。不能把高频设备轨迹仅在 RGB 帧时间戳上取一次，就当作整帧所有像素的真实位姿。

### 一个小角度，在高分辨率图像里就是许多像素

在针孔近轴近似下，小旋转造成的横向像移约为 $\Delta u\approx f\Delta\theta$。取 $f=1200$ 像素、转头角速度 $100^\circ/\mathrm s$、整帧读出 $16$ ms：

$$
\Delta\theta=100\times0.016=1.6^\circ\approx0.0279\,\mathrm{rad},
\qquad \Delta u\approx33.5\,\mathrm{px}.
$$

这不是模型测量值，而是量级计算。若使用中间行位姿，前后行仍可能分别错十多个像素。对于一根只有几像素宽的细杆，这种误差足以改变它的重建形状。

<!-- aria-figure: photoreal-timing -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-timing.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-timing.svg" width="1100" height="500" alt="自制图 1：以 16 ms 读出、100°/s 转动和 1200 px 焦距计算跨行位移约 33.5 px。示意图夸大斜率便于阅读；实际位移随场景点位置与相机模型变化。" loading="lazy" /></a>
  <figcaption>自制图 1 · 以 16 ms 读出、100°/s 转动和 1200 px 焦距计算跨行位移约 33.5 px。示意图夸大斜率便于阅读；实际位移随场景点位置与相机模型变化。</figcaption>
</figure>
<!-- /aria-figure -->

<!-- aria-figure: photoreal-4 -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-4.webp" width="823" height="419" alt="Photoreal Reconstruction 原论文 Figure 4：读出期间的重投影运动及其时间分布，说明一帧一个位姿可能差很多像素。" loading="lazy" /></a>
  <figcaption>Photoreal Reconstruction 原论文 Figure 4 · 读出期间的重投影运动及其时间分布，说明一帧一个位姿可能差很多像素。 <a href="https://arxiv.org/pdf/2506.04444v1#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 4 的左图把读出期间的重投影变化画成向量，右图统计沿轨迹的误差分位数。论文所示帧中，约半数点的读出运动达到 30 像素量级。它说明这个问题在真实数据里也不可忽略，但不是说所有帧、所有像素都恰好移动 30 像素。

## 2. VIBA 修的不是场景外观，而是传感器与轨迹

### 从 VIO、闭环 SLAM 到联合调整

<!-- aria-figure: photoreal-3 -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-3.webp" width="823" height="521" alt="Photoreal Reconstruction 原论文 Figure 3：VIO、闭环 SLAM 与 VIBA；逐行曝光要求高频轨迹与准确时间标定。" loading="lazy" /></a>
  <figcaption>Photoreal Reconstruction 原论文 Figure 3 · VIO、闭环 SLAM 与 VIBA；逐行曝光要求高频轨迹与准确时间标定。 <a href="https://arxiv.org/pdf/2506.04444v1#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

系统先由视觉惯性里程计得到增量轨迹和在线标定，再由全局快门 SLAM 相机建立闭环与重定位。VIBA（Visual-Inertial Bundle Adjustment）进一步联合优化包含 RGB 在内的轨迹与传感器标定，同时维持闭环约束。

与只对一组静态照片运行普通 bundle adjustment 的设置相比，这里关注四件事：RGB 滚动快门模型、传感器时间偏移、IMU 频率上的轨迹／标定，以及长序列的一致性。论文使用 Project Aria MPS 提供的处理流程。

VIBA 并非这篇博客可写成某个新增神经网络损失的模块。本文论文把它作为重建前的状态估计基础，再实验证明使用它的收益；不要把后面的颜色重建损失称作“训练 VIBA”。

### 高频轨迹是一条可查询的时间函数

把轨迹写为 $T(t)=f_T(t)$，可以在任意像素对应的曝光时刻查询位姿。论文设备轨迹以约 1 kHz 输出，并用分段连续形式查询。1 kHz 的采样间隔是 1 ms，正好与高分辨率相机读出期间的细小运动相关。

这里“高频”不等于“每毫秒绝对无误差”。轨迹、外参和时间偏移必须一起准确，否则时间查得再密也只会密集地查询错误位姿。

## 3. 从普通 Gaussian Splatting 开始，错配在哪里？

### 高斯表示与前向渲染

Gaussian Splatting 用一组带空间均值、协方差、不透明度和颜色的高斯描述场景。三维高斯投到图像中后，按深度顺序进行透明度合成。教学性地写出一个像素的颜色：

$$
C(\mathbf u)=\sum_i \alpha_i(\mathbf u)\,\mathbf c_i
\prod_{j<i}\bigl(1-\alpha_j(\mathbf u)\bigr).
$$

$\alpha_i(\mathbf u)$ 包含这个高斯在该像素的覆盖；前方高斯会衰减后方贡献。论文把渲染器简写为 $\pi(\mathbf u,S,T)$，其中 $S$ 是场景、$T$ 是相机位姿。

若前方红色高斯透明度为 $0.5$，后方蓝色为 $0.8$，红色贡献 $0.5$，蓝色贡献 $(1-0.5)\times0.8=0.4$，还留 $0.1$ 背景透过率。这个公式回答空间遮挡，尚未回答快门何时收光。

### 一个错误的拍摄假设，会怎样改变高斯？

真实的窗框在不同图像行上于不同时间被看到，普通渲染器却用一个位姿解释整幅图。优化器可能拉长高斯、增加重叠高斯、产生漂浮结构来降低像素误差。这些参数对训练图有帮助，却会损坏新的视角。

因此本文的改进主要是把观测模型与真实相机对齐。高斯表示仍可采用现有 3D-GS 或 2D-GS，并不要求为每种镜头重写整个光栅化内核。

## 4. 滚动快门与运动模糊，是两个不同的时间效应

### 逐行时间：同一帧里，不同行从不同瞬间开始曝光

对原始传感器图像，第 $v$ 行的时间近似为

$$
t(\mathbf u)=t_0+\frac vH\Delta t_r,
$$

其中 $H$ 是图像高度，$\Delta t_r$ 是整帧读出时长，$t_0$ 是首行开始时刻。行号从零开始时，最后一行对应 $(H-1)/H$；这是原文采用的行比例约定。

### 曝光积分：每个像素还要在一段时间内收光

论文的物理成像模型为

$$
C(\mathbf u)=\phi\left(
\omega(\mathbf u)\int_0^{t_e}
\pi\bigl(\mathbf u,S,T(t(\mathbf u)+\tau)\bigr)\,d\tau
\right).
$$

$t_e$ 是曝光时间，$\omega$ 合并增益、镜头阴影及归一化因子，$\phi$ 是相机响应。时间积分必须在响应变换前：先累积线性光，再变成存储图像值。它不是先把每次曝光的 gamma 编码颜色平均。

<!-- aria-figure: photoreal-exposure -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-exposure.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-exposure.svg" width="1100" height="500" alt="自制图 2：采用指数为 1/2.2 的教学 gamma 响应，积分后编码为约 0.743，先编码再平均为约 0.616。色块按计算值绘制。" loading="lazy" /></a>
  <figcaption>自制图 2 · 采用指数为 1/2.2 的教学 gamma 响应，积分后编码为约 0.743，先编码再平均为约 0.616。色块按计算值绘制。</figcaption>
</figure>
<!-- /aria-figure -->

短曝光能减小单行运动模糊，但不会自动消除不同行之间的滚动快门形变；整帧仍要花约 16 ms 读出。反之，只修正每行开始位姿，也未必消除长曝光内的模糊。

以两个等权采样点的线性亮度 $0.04$ 和 $1$ 为例，先平均得到 $0.52$，经 $1/2.2$ 次幂约为 $0.743$。若先分别 gamma 编码再平均，得到约 $0.616$。两个顺序并不等价，这就是必须尊重成像过程的原因。

## 5. 最容易漏的一步：图像校正后，行号不再代表时间

### 一条输出行可能来自多条原始传感器行

为了复用现有光栅化器，作者把 Aria 图像校正到它支持的相机模型。但鱼眼去畸变会重新安排像素：输出像素 $\mathbf u'$ 对应原始位置 $g(\mathbf u')$。输出同一条水平线上的像素，可能来自不同原始行，曝光起始时间也就不同。

直接把校正后的 $v'/H'$ 代入时间公式会出错。作者先为原图建立行比例图 $R(\mathbf u)=v/H$，再对它做与 RGB 相同的几何校正，得到 $R'(\mathbf u')$：

$$
t(\mathbf u')=t_0+R'(\mathbf u')\Delta t_r.
$$

<!-- aria-figure: photoreal-rowmap -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-rowmap.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-rowmap.svg" width="1100" height="500" alt="自制图 3：以确定的教学径向映射逐格计算原始行号；白色等时线由数值求根得到。映射系数 0.35 保存在脚本中，不代表 Aria 标定。" loading="lazy" /></a>
  <figcaption>自制图 3 · 以确定的教学径向映射逐格计算原始行号；白色等时线由数值求根得到。映射系数 0.35 保存在脚本中，不代表 Aria 标定。</figcaption>
</figure>
<!-- /aria-figure -->

这张教学图用一个确定的逆映射演示：源行号等值线在输出图中弯曲。它不是 Aria 标定参数的复刻；精确实现必须使用真实镜头模型。应一起校正的不止 RGB，还包括行比例图、镜头阴影图与有效像素掩码。

<!-- aria-figure: photoreal-9 -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-9.webp" width="825" height="414" alt="Photoreal Reconstruction 原论文 Figure 9：校正后的源行号图；相同输出行不再对应相同的曝光时刻。" loading="lazy" /></a>
  <figcaption>Photoreal Reconstruction 原论文 Figure 9 · 校正后的源行号图；相同输出行不再对应相同的曝光时刻。 <a href="https://arxiv.org/pdf/2506.04444v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 9 是原文实际的校正索引图：灰度表示源行号，黑色区域对应没有原始观测的像素，需要屏蔽。不要把黑色误认为它们都在首行曝光，也不要在那些无效位置监督颜色。

### 采样多个位姿，再按每个像素自己的时间取值

作者在一些选定时刻调用现有渲染器，生成一批图像，再用像素时间索引进行 gather，组装最终的滚动快门图像。这样把复杂相机时间模型放在现有光栅化器外面；反向梯度沿像素选取关系回到对应的渲染结果和高斯参数。

批量渲染会增加显存占用，附录提到显存受限时可改为迭代。它复用了渲染内核，但不是“零计算成本”地处理相机运动。

## 6. 采样多密才够：让像素运动决定，而不是固定拍脑袋

### 以可见稀疏点作运动锚点

作者用全局快门 SLAM 相机重建的静态点作为锚点，在不同候选时间位姿下重投影，估计时间区间内的像素位移。选择时间间隔时，使约一半重投影点的运动小于一像素；因此它是基于分布的近似条件，不保证每个像素都低于一像素。

准静态视角可能只需一个位姿；快速运动可能用 8–16 个采样。论文约 16 ms 读出的数据平均需要八个运动采样。物体深度、旋转速度与视场位置都会改变需要的密度。

<!-- aria-figure: photoreal-sampling -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-sampling.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-sampling.svg" width="1100" height="500" alt="自制图 4：匀速教学例，用不同数量的曝光时刻采样表达快慢运动的区别；图中的 2 与 9 是示意采样数，不是论文每帧固定配置。" loading="lazy" /></a>
  <figcaption>自制图 4 · 匀速教学例，用不同数量的曝光时刻采样表达快慢运动的区别；图中的 2 与 9 是示意采样数，不是论文每帧固定配置。</figcaption>
</figure>
<!-- /aria-figure -->

教学图中较快的运动使用更细的时间格采样，以控制离散近似误差；真实系统则依据重投影误差选间隔。远处点可能满足阈值，近处桌边仍移动得很快，因此不能把中位数条件说成严格全图误差上界。

复现时还需区分论文设置与发布代码默认值：核查的[提交 `516dfe23d1c7`](https://github.com/facebookresearch/egocentric_splats/blob/516dfe23d1c7dec54cea1696ff840f3790cfb95b/scene/cameras.py)把滚动快门最大采样数设为 8、每个时间段内的曝光采样上限设为 1。实现具有多曝光采样分支，但默认配置不等于已经密集积分了长曝光模糊；论文中的 8–16 也不应直接写成该版本的默认上限。

### 为什么论文还是建议短曝光？

理论上积分模型可以解释运动模糊，但实际人的采集轨迹不一定提供足够密集、清晰的互补观测。模糊已经抹掉高频纹理时，优化器未必能可靠找回。

作者在普通室内条件将曝光限制到最多 2 ms，让较高增益承担一部分亮度需求。这样减少运动模糊，代价是噪声增多；跨视图重建更容易消化一定程度的随机噪声，而不是逆转所有严重模糊。论文仍把极低照度视为未解决边界。

## 7. HDR 与损失：不只是把输出调亮

### 增益与暗角是观测条件，场景辐照度才是重建对象

若同一面白墙在不同帧因自动曝光变亮变暗，不能把所有变化都解释成墙本身发光不一致。曝光时间、增益与镜头阴影进入成像式后，模型可以用更一致的场景辐照度解释这些图像。

论文还在 gamma 压缩的空间参数化场景颜色，渲染时转换回线性辐照度，默认 gamma 为 2.2。这样处理高动态范围的优化数值尺度；它与传感器响应、显示端调亮有关，但不是完全同一个步骤。不能说“所有光线都在 gamma 空间物理相加”。

### 监督仍来自图像，只是前向渲染更忠实

论文沿用 vanilla 3D-GS 的颜色重建目标，而不是发明一套三维真值监督。用常见结构表示：

$$
\mathcal L_{\rm photo}
=(1-\lambda)\|\hat I-I\|_1
+\lambda\bigl(1-\operatorname{SSIM}(\hat I,I)\bigr).
$$

$\hat I$ 是经过时间采样、曝光与响应后的预测图像，$I$ 是有效区域内的实际图像。L1 关心逐像素颜色，SSIM 比较局部结构；具体归约和参数应遵循所用代码配置，不能把这里的符号形式当成独立复现配方。

两像素的观测为 $(0.2,0.8)$、预测为 $(0.3,0.6)$ 时，平均 L1 为 $(0.1+0.2)/2=0.15$。如果时间模型把同一条边缘错位到邻近像素，L1 和结构项都会惩罚；更重要的是梯度会驱使高斯改变。正确时间模型让梯度更可能修复场景本身，而非替传感器误差兜底。

所有颜色都预测成常数不能通过有纹理图像的监督，但只在训练视角拟合像素仍可能过拟合，因此需要留出视角验证。本文复现的是公式解释与示意，不是重跑 GPU 重建基准。

## 8. 实验协议：哪些视角没有参加训练？

作者采集六个室外和六个室内场景，录制约 10 FPS、8 MP JPEG 图像；按论文流程避免额外去噪、去模糊和局部色调映射。这里不是声称输入文件都是直接可读取的 RAW Bayer 数据，而是保留建模需要的响应、曝光和增益关系。

原图约 $2880\times2880$，校正到 $2400\times2400$；每第八张图留作验证，其余训练。默认 30K 次迭代，前 7.5K 次后启用滚动快门补偿。新视角主要来自同一采集轨迹的留出帧，并非任意远离采集区域的新视角。

<!-- aria-figure: photoreal-8 -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-8.webp" width="1702" height="994" alt="Photoreal Reconstruction 原论文 Figure 8：多种室内外场景的半稠密点云与 RGB 视角。" loading="lazy" /></a>
  <figcaption>Photoreal Reconstruction 原论文 Figure 8 · 多种室内外场景的半稠密点云与 RGB 视角。 <a href="https://arxiv.org/pdf/2506.04444v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 8 展示走廊、庭院、细结构和大窗等场景的点云覆盖。它提示读者：不同场景的观察密度、反光与遮挡难度差异很大，不能只拿小客厅的好结果概括全部录制。

### PSNR 的一分变化意味着什么？

归一化像素范围下

$$
\operatorname{PSNR}=10\log_{10}\frac1{\operatorname{MSE}}.
$$

若提升 1 dB，在相同数据与计算约定下，MSE 约乘以 $10^{-0.1}=0.794$，即下降约 20.6%。但平均 PSNR 的差异不能直接替换成所有像素都改善相同比例，也不能证明几何网格一定更准。

## 9. 消融：标定、运动采样、颜色表示各有证据

下表摘录原论文 Table 1 的 PSNR，单位 dB；所有行按同一场景与留出协议比较。

| 设置 | Bike shop | Sunroom | Micro kitchen | Livingroom |
| --- | ---: | ---: | ---: | ---: |
| Splatfacto | 26.98 | 22.82 | 23.05 | 27.41 |
| 3DGS-on-move | 27.07 | 23.33 | 23.35 | 27.62 |
| 完整方法 | 29.98 | 27.03 | 27.11 | 27.73 |
| 去掉 VIBA | 27.68 | 25.22 | 25.54 | 26.35 |
| 去掉运动采样 | 28.83 | 26.15 | 25.94 | 27.28 |
| 去掉场景 gamma | 29.04 | 21.76 | 24.48 | 27.33 |

完整方法与去 VIBA 的差异，检验更准确状态估计的价值；与去运动采样的差异，检验像素级时间模型；与去 gamma 的差异，检验颜色参数化。它们可能互相影响，不能把三列提升简单相加成必然总收益。

<!-- aria-figure: photoreal-6 -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-6.webp" width="1702" height="2029" alt="Photoreal Reconstruction 原论文 Figure 6：与 Splatfacto、3DGS-on-move 的跨场景视觉比较。" loading="lazy" /></a>
  <figcaption>Photoreal Reconstruction 原论文 Figure 6 · 与 Splatfacto、3DGS-on-move 的跨场景视觉比较。 <a href="https://arxiv.org/pdf/2506.04444v1#page=9" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 6 中看细杆、桌椅边缘与暗部漂浮物，配合对应场景的数字。Livingroom 的完整方法只比 Splatfacto 高 $0.32$ dB，明显小于更复杂场景的差距。论文也指出密集采集的小场景中基线已经接近，不应只挑收益最大的场景。

<!-- aria-figure: photoreal-7 -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-7.webp" width="1702" height="2029" alt="Photoreal Reconstruction 原论文 Figure 7：VIBA、运动采样和场景 gamma 的定性消融；关注文字、细杆与暗部。" loading="lazy" /></a>
  <figcaption>Photoreal Reconstruction 原论文 Figure 7 · VIBA、运动采样和场景 gamma 的定性消融；关注文字、细杆与暗部。 <a href="https://arxiv.org/pdf/2506.04444v1#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

Figure 7 将消融放在同样视角：不同模块可能让文字、结构边界与亮暗区域产生不同变化。锐利并不总等价于真实，应结合留出图像与几何指标。

### 换到 Quest 3，是有依据的迁移，但样本仍有限

<!-- aria-figure: photoreal-5 -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-5.webp" width="1702" height="497" alt="Photoreal Reconstruction 原论文 Figure 5：Quest 3 场景中使用与不使用 VIBA 的细节差异。" loading="lazy" /></a>
  <figcaption>Photoreal Reconstruction 原论文 Figure 5 · Quest 3 场景中使用与不使用 VIBA 的细节差异。 <a href="https://arxiv.org/pdf/2506.04444v1#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

作者对一个 Quest 3 录制使用相同处理思路。Table 3 的 PSNR 为完整方法 $29.54$、无 VIBA $27.27$、无运动采样 $28.85$。Figure 5 的细节支持收益，但一个序列不足以推出所有设备和环境都获得相同改善。

## 10. 看起来像照片，几何是否也变好了？

<!-- aria-figure: photoreal-10 -->
<figure>
  <a href="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/photoreal-egocentric-reconstruction/photoreal-10.webp" width="1702" height="1671" alt="Photoreal Reconstruction 原论文 Figure 10：DTC 上 3D-GS 与 2D-GS 的颜色、深度和法线重建。" loading="lazy" /></a>
  <figcaption>Photoreal Reconstruction 原论文 Figure 10 · DTC 上 3D-GS 与 2D-GS 的颜色、深度和法线重建。 <a href="https://arxiv.org/pdf/2506.04444v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /aria-figure -->

DTC 数据提供对齐的三维参考，作者用尺度不变深度 L1 与法线 L1 评价几何。原文 Table 2 中，3D-GS 的完整方法为 PSNR $29.83$、深度误差 $0.1505$、法线误差 $0.3078$；换成 2D-GS 后为 $29.54$、$0.1474$、$0.1509$。

所以外观 PSNR 略低，不代表几何更差；2D-GS 的法线指标明显更好。Figure 10 将颜色、深度与法线分开正是为了展示这种区别。这里深度是尺度不变损失，不应把 $0.1505$ 直接写成“15.05 厘米绝对深度误差”。

本文时间与响应模型能复用到不同高斯表示，说明改进位于观测模型这一层。但它也不能自动保证物理正确的表面：反射、透明材料与视角不足仍然可能让颜色拟合和真实几何分离。

## 11. 哪些问题仍然留给未来？

第一，动态人和物体并没有被静态场景模型充分解释。厨房里的手、被拿走的杯子、开关的门，都可能产生不一致观测。更准确的相机模型不能代替动态物体建模。

第二，低照度下即使缩短曝光、提高增益，也无法创造本来没有采到的光子。论文明确极低照度、较大运动与校准不足仍然困难。学习先验也许能补外观，但那又需要区分“恢复观测”与“生成猜测”。

第三，时间与标定是依赖条件。一个时间偏移错误会让整幅图的采样位姿错位；行比例图映射错误会把局部时间顺序打乱；错误曝光单位则会让辐照度尺度失真。渲染更精细之前，数据接口就必须先一致。

这五篇文章的共同线索到这里已经很清楚：BoxerNet 将语义框接到尺度几何，LAMP 先用定位分离观察者与目标运动，HMD² 用条件生成处理不可见身体，EgoForce 用射线约束手部位置，而本文继续把几何推进到每一个像素的曝光时刻。学习模型填补信息缺口，可靠标定与物理模型则帮助我们明确：哪些东西真的被看见，哪些仍是推断。

## 参考资料

- [Photoreal Scene Reconstruction，固定 arXiv v1](https://arxiv.org/abs/2506.04444v1)
- [Project Aria 官方项目与数据](https://www.projectaria.com/photoreal-reconstruction/)
- [egocentric_splats 作者实现](https://github.com/facebookresearch/egocentric_splats)
