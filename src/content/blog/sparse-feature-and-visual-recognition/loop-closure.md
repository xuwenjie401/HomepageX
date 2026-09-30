---
title: "检测到回环以后：从几何验证、位姿图到全局 BA，读懂 ORB-SLAM、VINS 与 OKVIS"
description: "用统一坐标约定推导视觉与惯性因子、Schur 消元、边缘化、Sim(3)/4DoF 回环、地图融合和异步校正，并逐项对照 ORB-SLAM2/3、VINS-Fusion、OKVIS/2/2-X。"
date: 2026-09-26
tags: [SLAM, 回环检测, 因子图, 束调整, 代码精读]
---

机器人绕着楼层走了一圈。检索模块说：“当前照片很像十分钟前的那一帧。”屏幕上的两段轨迹却差了两米，墙也被建成了两层。这时需要解决的远不止把两张图连起来：**它们是否真是同一地点？两段地图之间差了什么变换？哪些状态能动？历史信息还在不在？校正期间新来的帧怎么办？**

回环闭合是一整条数据关联与优化链路。VPR 或 BoW 只提供候选；几何验证才产生可用于优化的约束；位姿图把误差传播到历史；地图融合消除重复地标；BA 则重新利用图像测量调整相机和三维结构。不同系统保留历史信息的方式不同，因此闭环后的优化也不能用同一张“加一条边然后 BA”的图概括。

本文先建立统一数学语言，再沿三条路线阅读实现：ORB-SLAM2/3 的共视图与地图融合，VINS-Fusion 的局部估计器加全局位姿图，OKVIS 到 OKVIS2 的观测压缩与恢复。最后补充 OKVIS2-X 的稠密子地图及多传感器扩展。

> 论文版本与代码固定于文末。公式采用本文统一坐标约定；代码变量名可能使用相反变换方向。数值小例子与自制图是可复算教学示例，不是重跑论文的轨迹结果。

## 训练资源、卡时与数据量

这篇文章讨论的 ORB-SLAM2/3、VINS-Fusion、OKVIS/OKVIS2/OKVIS2-X 都是运行时建图与优化系统，没有一个统一的神经网络预训练阶段。因此没有可填的训练 GPU-hours 或训练图像量；数据量应按具体评测序列的帧数、关键帧数、观测数和地图点数记录。文中公式与小例子是可复算示意，不是重新训练或重跑基准所得。

<!-- vision-figure: loop-overview -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-overview.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-overview.svg" width="1100" height="470" alt="自制图 1：外观相似只产生候选；几何对应确认后才能添加约束，并把校正传播到地图。" loading="lazy" /></a>
  <figcaption>自制图 1 · 外观相似只产生候选；几何对应确认后才能添加约束，并把校正传播到地图。</figcaption>
</figure>
<!-- /vision-figure -->

## 1. 先分清五种经常被叫作 graph 的东西

### 1.1 地图的关联结构，与优化问题的结构不同

| 名称 | 节点 | 连线含义 | 能否直接作为优化残差 |
| --- | --- | --- | --- |
| 观测二部图 | 关键帧、地标 | 某帧观察到某地标 | 加上像素观测与投影模型后可以 |
| 共视图 | 关键帧 | 共享地标数量 | 数量本身不是相对位姿测量 |
| 生成树 | 关键帧 | 连通地图、维护父子关系 | 还需定义边上的测量 |
| 位姿图 | 位姿或相似变换 | 相对位姿约束 | 可以，但须给误差模型和权重 |
| 因子图 | 位姿、速度、偏置、地标等变量 | 残差因子连接它依赖的变量 | 图本身就是目标函数的结构 |

一个角点同时被四个关键帧看见，会在观测图上连出四条边，在共视图上诱导六对关键帧关系。若把六对关系都当成独立测量，信息已经可能被重复使用。因此“边多”不等于“统计信息更多”。

<!-- vision-figure: loop-graphs -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-graphs.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-graphs.svg" width="1100" height="470" alt="自制图 2：共享地标可以诱导相机间共视连接；共享点数本身不等于相对位姿测量及其信息矩阵。" loading="lazy" /></a>
  <figcaption>自制图 2 · 共享地标可以诱导相机间共视连接；共享点数本身不等于相对位姿测量及其信息矩阵。</figcaption>
</figure>
<!-- /vision-figure -->

### 1.2 BA、位姿图优化与坐标变换各自改变什么

BA 的典型变量包含相机位姿 $T_i$ 与地标 $\mathbf P_l$，残差来自像素；位姿图优化通常只改变 $T_i$，残差来自相对变换；对一段轨迹整体施加刚体变换，则只是在对齐坐标系，不改变这段内部的相对几何。

如果轨迹沿途逐步漂移，仅把全部历史乘同一个 $T$，无法同时消除各处误差。需要不同位置得到不同程度的校正，而这正是图优化的作用。

## 2. 统一坐标、状态与测量：后面的正负号由这里决定

### 2.1 本文始终使用“从右下标到左下标”

定义 $T_{AB}$ 将 B 坐标变到 A：

$$
\mathbf p_A=R_{AB}\mathbf p_B+\mathbf t_{AB},\qquad
T_{AB}=\begin{bmatrix}R_{AB}&\mathbf t_{AB}\\0&1\end{bmatrix}.
$$

世界系为 $W$，IMU 为 $B$，相机为 $C$。后文简写 $T\mathbf P$ 表示刚体变换对三维点的作用 $R\mathbf P+\mathbf t$；显式使用四维齐次列向量时再补齐次分量。位姿状态 $T_{WB_i}$ 把机体系点变到世界；外参 $T_{BC}$ 把相机变到机体，于是 $T_{WC_i}=T_{WB_i}T_{BC}$。相机看到地标时用反方向 $T_{C_iW}=T_{WC_i}^{-1}$。

在纯视觉部分，简写 $T_i=T_{WC_i}$。预测的相对变换

$$
T_{ij}=T_i^{-1}T_j
$$

把 j 相机中的点变到 i 相机。后面测量 $\widehat T_{ij}$ 也使用这个方向。若把它与“相机 i 到 j 的运动”口语混用，回环边很容易接反。

<!-- vision-figure: loop-frames -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-frames.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-frames.svg" width="1100" height="470" alt="自制图 3：变换复合遵循坐标路径。相机位姿的存储方向与投影时需要的方向相反，代码阅读必须先核对。" loading="lazy" /></a>
  <figcaption>自制图 3 · 变换复合遵循坐标路径。相机位姿的存储方向与投影时需要的方向相反，代码阅读必须先核对。</figcaption>
</figure>
<!-- /vision-figure -->

### 2.2 视觉残差用像素，权重用测量不确定性

地标在相机坐标中为 $\mathbf P_{il}=T_i^{-1}\mathbf P_l$，针孔投影是

$$
\pi(X,Y,Z)=\begin{bmatrix}f_xX/Z+c_x\\f_yY/Z+c_y\end{bmatrix}.
$$

像素测量为 $\mathbf z_{il}$，残差为

$$
\mathbf r^v_{il}=\mathbf z_{il}-\pi(T_i^{-1}\mathbf P_l),
\qquad
E_v=\sum_{(i,l)\in\mathcal O}\rho\left((\mathbf r^v_{il})^{\mathsf T}\Sigma_{il}^{-1}\mathbf r^v_{il}\right).
$$

$\Sigma$ 单位是像素平方，白化后的平方误差无量纲。金字塔较粗层的定位通常更不精确，因而应有不同权重。双目还可以把右图横坐标放入残差：

$$
\pi_s(X,Y,Z)=
\begin{bmatrix}f_xX/Z+c_x\\f_yY/Z+c_y\\f_xX/Z+c_x-f_xb/Z\end{bmatrix}.
$$

基线 $b$ 为米，使双目在合适视差条件下提供尺度。远点的视差小，深度不确定性仍会很大。

### 2.3 位姿为什么要在局部切空间更新

旋转矩阵的九个数并不独立。采用小量 $\delta\boldsymbol\xi\in\mathbb R^6$ 更新，例如世界到相机变换的左扰动 $T_{CW}'=\operatorname{Exp}(\delta\boldsymbol\xi^\wedge)T_{CW}$。若 $\delta\boldsymbol\xi=(\delta\mathbf t,\delta\boldsymbol\theta)$，则

$$
\frac{\partial\mathbf P_C'}{\partial\delta\boldsymbol\xi}
=\begin{bmatrix}I&-[\mathbf P_C]_\times\end{bmatrix},
$$

$$
J_\pi=\begin{bmatrix}
f_x/Z&0&-f_xX/Z^2\\
0&f_y/Z&-f_yY/Z^2
\end{bmatrix},
\qquad
J_{pose}=-J_\pi\begin{bmatrix}I&-[\mathbf P_C]_\times\end{bmatrix}.
$$

负号来自本文“观测减预测”的残差定义。换成右扰动、相机到世界位姿或“预测减观测”，Jacobian 会改变；公式不应离开定义单独复制。

## 3. 没有回环时，系统到底在优化什么

### 3.1 Tracking：先固定地图，只求当前相机

跟踪阶段通常用运动模型或 IMU 传播给初值，关联当前图像与局部地图，再最小化当前帧的视觉误差。这是 motion-only 优化：地图点暂时固定，只更新当前位姿。它的规模小，能频繁运行。

若对应点全部集中在远方、直线或近共面区域，某些运动方向约束就弱。内点数 100 并不自动比空间分布良好的 40 点更可靠。学习特征能改善关联，却不能取消几何退化。

### 3.2 Local BA：让局部相机和地标一起动

新关键帧加入后，局部建图进行三角化、重复点融合、坏点剔除及局部 BA。设局部变量相机集合为 $\mathcal K_L$，观测这些局部点的外围相机为 $\mathcal K_F$，则

$$
\min_{\{T_i:i\in\mathcal K_L\},\{\mathbf P_l:l\in\mathcal P_L\}}
\sum_{i\in\mathcal K_L\cup\mathcal K_F}\sum_{l:(i,l)\in\mathcal O}
\rho(\|\mathbf r^v_{il}\|_{\Sigma^{-1}}^2),
$$

其中 $\mathcal K_F$ 固定。外围相机提供边界，避免整个局部地图自由漂移；但边界若已经有历史误差，局部 BA 也无法主动移动远处所有关键帧。

<!-- vision-figure: loop-local-ba -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-local-ba.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-local-ba.svg" width="1100" height="470" alt="自制图 4：局部 BA 的观测不只来自活动相机，也来自看到这些地标的固定外围相机。" loading="lazy" /></a>
  <figcaption>自制图 4 · 局部 BA 的观测不只来自活动相机，也来自看到这些地标的固定外围相机。</figcaption>
</figure>
<!-- /vision-figure -->

### 3.3 视觉惯性状态比一条轨迹复杂得多

VIO 每时刻常用状态

$$
\mathbf x_i=(R_{WB_i},\mathbf p_i,\mathbf v_i,\mathbf b_i^g,\mathbf b_i^a),
$$

局部增量共 15 维。还可能估计相机外参、时间偏移以及以首观测帧锚定的逆深度 $\lambda_l$。逆深度地标写成

$$
\widetilde{\mathbf P}_l=T_{WB_a}T_{BC}
\begin{bmatrix}\lambda_l^{-1}\mathbf b_l\\1\end{bmatrix},
$$

其中 $\widetilde{\mathbf P}_l$ 为齐次世界点，$\mathbf b_l$ 为选定归一化方式的相机射线；若第三分量为 1，$\lambda$ 对应轴向深度的倒数。首帧 a 被删除时，必须处理锚定关系和已有先验，不能只删除变量数组的一行。

### 3.4 IMU 预积分把高频测量压成相邻状态之间的约束

假设 $\mathbf g_W$ 为世界重力，预积分量 $\widehat{\Delta R}_{ij},\widehat{\Delta v}_{ij},\widehat{\Delta p}_{ij}$ 在 i 机体系表达，并已对偏置进行一阶校正。主要残差为

$$
\begin{aligned}
\mathbf r_R&=\operatorname{Log}\left(\widehat{\Delta R}_{ij}^{\mathsf T}R_i^{\mathsf T}R_j\right),\\
\mathbf r_v&=R_i^{\mathsf T}(\mathbf v_j-\mathbf v_i-\mathbf g_W\Delta t)-\widehat{\Delta v}_{ij},\\
\mathbf r_p&=R_i^{\mathsf T}(\mathbf p_j-\mathbf p_i-\mathbf v_i\Delta t-\tfrac12\mathbf g_W\Delta t^2)-\widehat{\Delta p}_{ij},\\
\mathbf r_{bg}&=\mathbf b_j^g-\mathbf b_i^g,\qquad
\mathbf r_{ba}=\mathbf b_j^a-\mathbf b_i^a.
\end{aligned}
$$

将它们堆成 $\mathbf r^I_{ij}$ 并使用传播得到的协方差 $\Sigma^I_{ij}$。例如

$$
\Delta v(\mathbf b)\approx\widehat{\Delta v}+J_{vg}\delta\mathbf b^g+J_{va}\delta\mathbf b^a.
$$

因此偏置不是一个附带的常数：视觉校正运动后，也可能要求偏置和速度改变。若回环模块只优化位置和 yaw，它就没有直接执行这些变量的联合重估。

<!-- vision-figure: loop-imu -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-imu.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-imu.svg" width="1100" height="470" alt="自制图 5：惯性因子的依赖关系示意；圆为位姿，方为速度/偏置，金色小方块代表联合惯性残差。" loading="lazy" /></a>
  <figcaption>自制图 5 · 惯性因子的依赖关系示意；圆为位姿，方为速度/偏置，金色小方块代表联合惯性残差。</figcaption>
</figure>
<!-- /vision-figure -->

一般局部目标可概括为

$$
E(\mathcal X)=E_{prior}+\sum E_{visual}+\sum E_{IMU},
$$

其中先验来自固定参考系或边缘化。不同系统的状态组织、参数化与鲁棒化细节不同，上式是共同结构。

## 4. BA 为什么能算得动：Schur 消元与边缘化的区别

### 4.1 先线性化，再解一个稀疏系统

令所有白化残差堆成 $\mathbf r$，局部线性化 $\mathbf r(\mathbf x\boxplus\delta)\approx\mathbf r+J\delta$。Gauss–Newton 系统是

$$
H\delta=-\mathbf g,\qquad H=J^{\mathsf T}J,\quad\mathbf g=J^{\mathsf T}\mathbf r.
$$

LM 在左侧加阻尼 $\lambda D$。鲁棒核通常通过迭代重加权影响 $H$ 与 $\mathbf g$；不是简单求完最小二乘以后再删除几个点。

把变量分成相机 c 和地标 p：

$$
\begin{bmatrix}H_{cc}&H_{cp}\\H_{pc}&H_{pp}\end{bmatrix}
\begin{bmatrix}\delta_c\\\delta_p\end{bmatrix}
=-\begin{bmatrix}\mathbf g_c\\\mathbf g_p\end{bmatrix}.
$$

同一视觉残差只涉及一个地标，所以在没有额外点间约束时 $H_{pp}$ 按地标分块。先消去地标：

$$
\underbrace{(H_{cc}-H_{cp}H_{pp}^{-1}H_{pc})}_{S}\delta_c
=-\mathbf g_c+H_{cp}H_{pp}^{-1}\mathbf g_p,
$$

再回代 $\delta_p=-H_{pp}^{-1}(\mathbf g_p+H_{pc}\delta_c)$。

<!-- vision-figure: loop-schur -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-schur.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-schur.svg" width="1100" height="470" alt="自制图 6：左图为块稀疏性示意，右侧数值来自正文手算例子；消元后仍保留原始非线性观测用于下一次迭代。" loading="lazy" /></a>
  <figcaption>自制图 6 · 左图为块稀疏性示意，右侧数值来自正文手算例子；消元后仍保留原始非线性观测用于下一次迭代。</figcaption>
</figure>
<!-- /vision-figure -->

### 4.2 一个可以手算的消元例子

设 $H_{cc}=\begin{bmatrix}4&1\\1&3\end{bmatrix}$，$H_{cp}=\begin{bmatrix}1\\2\end{bmatrix}$，$H_{pp}=2$，$\mathbf g_c=(1,-1)^{\mathsf T}$，$g_p=2$。则

$$
S=\begin{bmatrix}3.5&0\\0&1\end{bmatrix},\qquad
-\mathbf g_c+H_{cp}H_{pp}^{-1}g_p=\begin{bmatrix}0\\3\end{bmatrix}.
$$

所以 $\delta_c=(0,3)^{\mathsf T}$，回代 $\delta_p=-4$。直接解原来的三维系统得到同一结果。这里 Schur 消元只是当前一次线性求解的代数技巧，点的原始测量仍在，下次可以重新线性化。

### 4.3 边缘化是把过去的非线性问题冻结为局部近似

滑窗满了，需要移走旧变量 $m$、保留 $r$。对当前线性化系统做同样的消元得到

$$
H_{prior}=H_{rr}-H_{rm}H_{mm}^{+}H_{mr},\qquad
\mathbf g_{prior}=\mathbf g_r-H_{rm}H_{mm}^{+}\mathbf g_m.
$$

加号表示在零空间存在时使用合适阈值的伪逆。通过特征分解 $H_{prior}=V\Lambda V^{\mathsf T}$，可构造

$$
A=\Lambda^{1/2}V^{\mathsf T},\qquad
\mathbf b=\Lambda^{-1/2}V^{\mathsf T}\mathbf g_{prior},
$$

只保留有效特征方向，令先验残差为 $A(\mathbf x_r\boxminus\bar{\mathbf x}_r)+\mathbf b$。

关键在 $\bar{\mathbf x}_r$：它是产生该先验时的线性化点。旧图像测量若已丢弃，就无法在大幅闭环校正后任意重新线性化它们。**边缘化后的二次先验不是原始非线性历史的无损存档。**

<!-- vision-figure: loop-marginalization -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-marginalization.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-marginalization.svg" width="1100" height="470" alt="自制图 7：金色因子表示旧信息形成的先验；把状态移出窗口与只在一次线性求解中消元是不同操作。" loading="lazy" /></a>
  <figcaption>自制图 7 · 金色因子表示旧信息形成的先验；把状态移出窗口与只在一次线性求解中消元是不同操作。</figcaption>
</figure>
<!-- /vision-figure -->

这也是为什么外部位姿图可以把历史轨迹拉回，却不自动等价于把所有历史图像与 IMU 重新联合优化一遍。OKVIS2 后面专门设计了观测归档与恢复，正是在处理这个问题。

## 5. 检索结果如何变成可信的几何约束

### 5.1 VPR/BoW 分数不带米和弧度

候选分数衡量外观相似度。重复走廊、相似楼层、同一建筑的不同立面，都可能产生高分。时间排除、候选组一致性和共视关系能减少误报，但最终要找到真实几何对应。

根据已有地图信息，验证问题可能是：

- 2D–2D：用本质矩阵验证标定相机间关系，平移通常只有方向，没有尺度。
- 2D–3D：用 PnP 在已有地标坐标系定位当前相机，得到有地图尺度的位姿。
- 3D–3D：两边均有地图点，可估计 $SE(3)$ 或带尺度的 $Sim(3)$ 对齐。

这些是不同输入条件，不是三个可以随意替换的函数名。特别是单目回环，不能把本质矩阵分解出来的单位平移直接作为米制位姿图边。

<!-- vision-figure: loop-geometry -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-geometry.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-geometry.svg" width="1100" height="470" alt="自制图 8：不同维度的对应决定几何问题：本质矩阵通常不提供米制平移，PnP 依赖已有地图尺度。" loading="lazy" /></a>
  <figcaption>自制图 8 · 不同维度的对应决定几何问题：本质矩阵通常不提供米制平移，PnP 依赖已有地图尺度。</figcaption>
</figure>
<!-- /vision-figure -->

### 5.2 RANSAC 之后仍要检查支持范围

从最小集采样、估计模型、统计内点，再非线性精化是基本过程。若内点率为 $w$、最小样本数为 s，要以概率 p 至少取得一次全内点样本，理想独立模型给出

$$
N\ge\frac{\log(1-p)}{\log(1-w^s)}.
$$

但实际匹配会相关、重复结构会产生一整组几何上自洽的错误，所以只把 p 设得很高不够。还应看覆盖范围、视差、正深度、重投影分布、与邻近关键帧的一致性。光照鲁棒匹配器能提供更多候选，但也可能把同类窗户串成高置信错误。

### 5.3 单目为什么需要 Sim(3)

单目局部重建存在尺度自由度，沿程也可能积累尺度漂移。相似变换

$$
S(\mathbf p)=sR\mathbf p+\mathbf t,\qquad s>0
$$

有七个自由度。两组对应点可用于估计

$$
\min_{s,R,\mathbf t}\sum_l\|\mathbf P_l^A-(sR\mathbf P_l^B+\mathbf t)\|^2.
$$

实际 ORB 系统还会通过双向图像重投影和投影搜索增强对应，而不只盯着两组三维点的欧氏距离，因为两边的深度估计本身含噪声。

双目/RGB-D 已有尺度时通常固定 $s=1$。惯性系统在完成尺度与重力初始化后，保留全局平移和 yaw 的规范自由度；这解释了某些闭环阶段采用 4DoF，但不表示所有惯性优化只需要四个状态参数。

## 6. 位姿图如何把闭合误差分给整条路径

### 6.1 一个通用 SE(3) 残差

沿用 $T_i=T_{WC_i}$，对测量 $\widehat T_{ij}$ 定义

$$
\mathbf e_{ij}=\operatorname{Log}\left(\widehat T_{ij}^{-1}T_i^{-1}T_j\right),
\qquad
E_{PG}=\sum_{(i,j)\in\mathcal E}\rho(\mathbf e_{ij}^{\mathsf T}\Omega_{ij}\mathbf e_{ij}).
$$

换成 $S_i\in Sim(3)$ 时，残差是七维并包含 log scale。平移和旋转分量的单位不同；$\Omega$ 表示它们的权重及相关性，不能从一个 VPR 相似度凭空推导出完整协方差。

全部位姿同时左乘一个刚体变换，不改变相对测量。因此必须固定一个参考节点或施加相应规范约束。单目 BA 还存在尺度规范；视觉惯性在充分激励后通常剩四维规范。数值阻尼能让矩阵暂时可逆，却不等于问题获得了真实绝对定位信息。

### 6.2 为什么误差不总是平均分配

考虑一维链条，起点固定。第 k 条里程计边位移误差修正为 $\delta_k$，方差为 $\sigma_k^2$，闭环要求总修正 $\sum_k\delta_k=-d$。求

$$
\min_{\delta}\sum_k\frac{\delta_k^2}{\sigma_k^2}
\quad\text{s.t.}\quad\sum_k\delta_k=-d
$$

得到

$$
\delta_k=-d\frac{\sigma_k^2}{\sum_j\sigma_j^2}.
$$

若三条边方差为 $(1,1,4)$、总误差为 6 米，修正是 $(-1,-1,-4)$ 米。不确定性最大的第三段承担最多变化；只有各边权重相同时才平均分。真实三维图还存在环、旋转耦合与鲁棒核，分配更加复杂。

<!-- vision-figure: loop-error-spread -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-error-spread.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-error-spread.svg" width="1100" height="470" alt="自制图 9：按正文约束最小二乘精确计算的误差分配。相等权重才对应平均摊开。" loading="lazy" /></a>
  <figcaption>自制图 9 · 按正文约束最小二乘精确计算的误差分配。相等权重才对应平均摊开。</figcaption>
</figure>
<!-- /vision-figure -->

### 6.3 假回环会怎样破坏图

错误边若权重大，优化器会认真地弯曲整张地图去满足它。鲁棒核可以抑制大残差，但某些假回环在当前初始化下并不显得异常，或者多个错误边互相支持。因而几何验证是第一道防线，鲁棒估计是补充。

例如 Huber 核在平方范数 s 上可写为

$$
\rho(s)=\begin{cases}s,&s\le\delta^2,\\2\delta\sqrt{s}-\delta^2,&s>\delta^2.\end{cases}
$$

它让大误差增长从二次变成线性，并不会给出“这条边是真的”的判决。工程上应记录被接受的回环对应及残差变化，必要时能定位和撤销错误关联。

<!-- vision-figure: loop-false-edge -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-false-edge.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-false-edge.svg" width="1100" height="470" alt="自制图 10：右图按公式计算 Huber 与平方损失。鲁棒核减缓大残差增长，不保证识别所有自洽的假回环。" loading="lazy" /></a>
  <figcaption>自制图 10 · 右图按公式计算 Huber 与平方损失。鲁棒核减缓大残差增长，不保证识别所有自洽的假回环。</figcaption>
</figure>
<!-- /vision-figure -->

## 7. ORB-SLAM2：先把重复地图接起来，再全局细化

### 7.1 平时的图如何维护

ORB-SLAM2 的 Tracking、Local Mapping 和 Loop Closing 各有职责。关键帧保存特征、地图点观测及 BoW 表示；地图点保存观测它的关键帧。共享观测更新共视权重，关键帧还有生成树父子关系和长期保留的回环边。

<!-- vision-figure: orbslam2-2 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam2-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam2-2.webp" width="1729" height="680" alt="ORB-SLAM2 原论文 Figure 2：Tracking、Local Mapping、Loop Closing 三线程与闭环后的 GBA。局部跟踪和后台全局优化具有不同变量范围。" loading="lazy" /></a>
  <figcaption>ORB-SLAM2 原论文 Figure 2 · Tracking、Local Mapping、Loop Closing 三线程与闭环后的 GBA。局部跟踪和后台全局优化具有不同变量范围。 <a href="https://arxiv.org/pdf/1610.06475v2#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Local Mapping 三角化新点、投影融合重复点、剔除不可靠地标和冗余关键帧，并运行 Local BA。这里的关键帧剔除主要是地图维护，不能与 VINS 的“把旧状态连同测量压成一个边缘化先验”混为一谈。

Essential Graph 是用于全局传播的稀疏图，包含生成树、已有回环边和强共视连接。固定代码中强共视阈值为 100 个共享点；这不表示共视图只记录 100 点以上的关系，也不表示所有边的信息矩阵都等于共享点数。

<!-- vision-figure: loop-essential -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-essential.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-essential.svg" width="1100" height="470" alt="自制图 11：稀疏全局传播图的教学示意；红为回环，绿为额外强共视连接，父子树保证基本连通。" loading="lazy" /></a>
  <figcaption>自制图 11 · 稀疏全局传播图的教学示意；红为回环，绿为额外强共视连接，父子树保证基本连通。</figcaption>
</figure>
<!-- /vision-figure -->

### 7.2 候选先通过时间与共视一致性，再估计 Sim(3)

回环线程从 BoW 数据库取候选，排除直接相连的局部邻居，检查候选组在连续查询中的一致性。随后进行描述匹配、Sim(3) RANSAC、非线性优化与更广范围的投影匹配。只有足够几何支持才进入 `CorrectLoop()`。

这种顺序的目的，是避免把“当前帧和另一个局部邻居相似”误当成消除长程漂移的回环，也避免单帧偶然外观相似触发地图大改。具体阈值属于实现与数据条件，不能作为普适概率保证。

### 7.3 局部校正如何同时移动相机与地图点

闭环后，系统先暂停 Local Mapping，防止校正期间不断插入关键帧；若旧 GBA 仍在运行，标记停止并更新优化代次。当前关键帧取得回环校正位姿，其共视邻居通过原有相对位姿传播校正。

这一节临时采用代码方向 $S_{iW}$（世界到关键帧 i）以便对应实现。旧地图点 $\mathbf P_W$ 应先用旧位姿送到参考帧，再用新位姿送回世界：

$$
\mathbf P_W'=\left(S_{iW}^{new}\right)^{-1}S_{iW}^{old}\mathbf P_W.
$$

于是 $S_{iW}^{new}\mathbf P_W'=S_{iW}^{old}\mathbf P_W$，参考帧里的投影保持一致。只改相机不改点，会瞬间破坏所有重投影；同一个点被多帧看见时，还必须避免重复校正。

<!-- vision-figure: loop-map-correction -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-map-correction.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-map-correction.svg" width="1100" height="470" alt="自制图 12：保持参考关键帧中的点坐标，从而保持其投影；同一点应避免被多个邻居重复校正。" loading="lazy" /></a>
  <figcaption>自制图 12 · 保持参考关键帧中的点坐标，从而保持其投影；同一点应避免被多个邻居重复校正。</figcaption>
</figure>
<!-- /vision-figure -->

代码把 $Sim(3)$ 相机变换 $sR\mathbf P+\mathbf t$ 存回 $SE(3)$ 位姿时使用 $[R,\mathbf t/s]$，因为透视投影不受整个相机坐标向量乘共同正尺度影响：

$$
\pi(sR\mathbf P+\mathbf t)=\pi(R\mathbf P+\mathbf t/s).
$$

这条公式只说明投影等价，不意味着可以随意丢掉世界地图的尺度校正。

### 7.4 融合地标才真正让两个世界共享观测

重访同一窗角时，系统可能已经建立两个地标 $P_a,P_b$。它们在图上看起来都合理，却属于两段不同历史。`SearchAndFuse()` 将回环邻域的地标投到当前邻域，确认重复后合并观测，并更新共视连接。

<!-- vision-figure: loop-fusion -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-fusion.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-fusion.svg" width="1100" height="470" alt="自制图 13：地标融合改变观测关联结构；它使两段历史的像素真正约束同一个三维变量。" loading="lazy" /></a>
  <figcaption>自制图 13 · 地标融合改变观测关联结构；它使两段历史的像素真正约束同一个三维变量。</figcaption>
</figure>
<!-- /vision-figure -->

合并后，同一三维变量被两段轨迹的像素观测共同约束。新的共视边进入 `LoopConnections`，为全局传播提供额外联系。若只添加一条位姿边、保留全部重复地标，轨迹可能闭合，地图仍会存在两层墙。

### 7.5 Essential Graph 优化使用什么边

`OptimizeEssentialGraph()` 为关键帧建立 Sim(3) 顶点，固定回环参考关键帧；单双目差别通过是否固定尺度控制。新回环联系使用校正关系，常规生成树、历史回环和强共视边尽量保留闭环前的相对几何。

固定代码中的信息矩阵为单位阵，而非从完整 BA Hessian 严格边缘化得到的协方差。这是一种高效的系统近似，解释了为什么 Essential Graph 优化不能被称为“与全部历史像素 BA 完全等价”。

求完后，所有关键帧及其参考地标按校正结果更新。此时全局误差已快速摊开，Tracking 可以继续使用一致得多的地图。

### 7.6 GBA 在后台继续做什么

ORB-SLAM2 随后启动全局 BA，以所有保留关键帧与地图点的重投影误差细化结构。与位姿图阶段不同，这时地标成为独立优化变量，像素观测重新参与。

但 GBA 运行时新关键帧仍会出现。固定实现保存参与该次优化的标记，通过生成树把未直接优化的新关键帧沿父子相对关系传播到新地图；点也根据是否取得 BA 结果或其参考关键帧进行处理。又一次回环可能使旧 GBA 过时，因此有停止标志、结果代次检查和地图更新锁。

<!-- vision-figure: loop-async -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-async.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-async.svg" width="1100" height="470" alt="自制图 14：横轴为时间；优化使用一个历史快照，提交时还要更新未参与该次优化的新关键帧与地图点。" loading="lazy" /></a>
  <figcaption>自制图 14 · 横轴为时间；优化使用一个历史快照，提交时还要更新未参与该次优化的新关键帧与地图点。</figcaption>
</figure>
<!-- /vision-figure -->

算法论文中一句“最后执行 GBA”，落到在线系统里就是一个快照、一套版本判断和一次一致性提交。若忽略这些，优化数学完全正确也可能覆盖新状态，造成地图跳变或线程竞态。

### 7.7 怎样读 ORB-SLAM2 的结果图

<!-- vision-figure: orbslam2-1 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam2-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam2-1.webp" width="861" height="1477" alt="ORB-SLAM2 原论文 Figure 1：双目与 RGB-D 轨迹和地图示例。地图复用、重定位与闭环在同一系统中协作。" loading="lazy" /></a>
  <figcaption>ORB-SLAM2 原论文 Figure 1 · 双目与 RGB-D 轨迹和地图示例。地图复用、重定位与闭环在同一系统中协作。 <a href="https://arxiv.org/pdf/1610.06475v2#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: orbslam2-3 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam2-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam2-3.webp" width="862" height="299" alt="ORB-SLAM2 原论文 Figure 3：KITTI 01 的近点和远点。远点对旋转较有用，对平移约束弱，说明内点数量不能代替几何分布检查。" loading="lazy" /></a>
  <figcaption>ORB-SLAM2 原论文 Figure 3 · KITTI 01 的近点和远点。远点对旋转较有用，对平移约束弱，说明内点数量不能代替几何分布检查。 <a href="https://arxiv.org/pdf/1610.06475v2#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: orbslam2-4 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam2-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam2-4.webp" width="861" height="629" alt="ORB-SLAM2 原论文 Figure 4：KITTI 多条序列的轨迹对照。黑色估计与红色真值的局部差异应结合各序列运动条件阅读。" loading="lazy" /></a>
  <figcaption>ORB-SLAM2 原论文 Figure 4 · KITTI 多条序列的轨迹对照。黑色估计与红色真值的局部差异应结合各序列运动条件阅读。 <a href="https://arxiv.org/pdf/1610.06475v2#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: orbslam2-5 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam2-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam2-5.webp" width="862" height="352" alt="ORB-SLAM2 原论文 Figure 5：KITTI 08 的单目尺度漂移与双目结果。尺度可观性来自传感器信息，不是仅靠更强回环检索。" loading="lazy" /></a>
  <figcaption>ORB-SLAM2 原论文 Figure 5 · KITTI 08 的单目尺度漂移与双目结果。尺度可观性来自传感器信息，不是仅靠更强回环检索。 <a href="https://arxiv.org/pdf/1610.06475v2#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: orbslam2-6 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam2-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam2-6.webp" width="861" height="635" alt="ORB-SLAM2 原论文 Figure 6：EuRoC 的不同运动序列。轨迹形状是定性证据，准确度还需结合表中统一误差度量。" loading="lazy" /></a>
  <figcaption>ORB-SLAM2 原论文 Figure 6 · EuRoC 的不同运动序列。轨迹形状是定性证据，准确度还需结合表中统一误差度量。 <a href="https://arxiv.org/pdf/1610.06475v2#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: orbslam2-7 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam2-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam2-7.webp" width="1729" height="1220" alt="ORB-SLAM2 原论文 Figure 7：以关键帧位姿和 RGB-D 深度生成的稠密点云。输出的清晰度依赖位姿与深度，ORB-SLAM2 的优化地图本身仍是稀疏地标。" loading="lazy" /></a>
  <figcaption>ORB-SLAM2 原论文 Figure 7 · 以关键帧位姿和 RGB-D 深度生成的稠密点云。输出的清晰度依赖位姿与深度，ORB-SLAM2 的优化地图本身仍是稀疏地标。 <a href="https://arxiv.org/pdf/1610.06475v2#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

这些原图分别展示系统结构之外的建图、轨迹和实验结果，具体阅读目标见各图注。轨迹在视觉上重合只能提供定性支持；应同时查看论文的 ATE/RPE 定义、是否允许尺度对齐、传感器类型、是否使用闭环后最终轨迹。某条序列的低误差不能独立证明回环检测从未误报，或某一个优化步骤贡献了全部收益。

## 8. ORB-SLAM3：有了惯性和 Atlas，闭环多了哪些约束

### 8.1 惯性初始化之前和之后不能一视同仁

ORB-SLAM3 在视觉地图基础上估计速度、偏置、尺度和重力，并通过后续惯性优化进一步稳定。激励不足时，尺度与加速度偏置可能强耦合；不能因为接上了 IMU 就假定从第一帧起尺度已经可靠。

<!-- vision-figure: orbslam3-1 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam3-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam3-1.webp" width="844" height="738" alt="ORB-SLAM3 原论文 Figure 1：ORB-SLAM3 的 Atlas、多传感器跟踪与地点识别结构。跨地图关联引出地图合并而非普通单图回环。" loading="lazy" /></a>
  <figcaption>ORB-SLAM3 原论文 Figure 1 · ORB-SLAM3 的 Atlas、多传感器跟踪与地点识别结构。跨地图关联引出地图合并而非普通单图回环。 <a href="https://arxiv.org/pdf/2007.11898v2#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: orbslam3-2 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam3-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam3-2.webp" width="1653" height="387" alt="ORB-SLAM3 原论文 Figure 2：视觉、惯性与初始化阶段的不同因子图。注意速度、偏置、尺度和重力的变量范围随优化阶段变化。" loading="lazy" /></a>
  <figcaption>ORB-SLAM3 原论文 Figure 2 · 视觉、惯性与初始化阶段的不同因子图。注意速度、偏置、尺度和重力的变量范围随优化阶段变化。 <a href="https://arxiv.org/pdf/2007.11898v2#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

初始化后，惯性提供重力方向，尺度也具物理意义。因此闭环校正应主要处理全局位置和 yaw 漂移，避免任意改变 roll/pitch、破坏重力一致性。固定实现中，`CorrectLoop()` 对已完成 IMU 初始化的惯性地图调用 `OptimizeEssentialGraph4DoF()`；否则走常规 Essential Graph 路径，并根据传感器与初始化状态处理尺度。

**4DoF 指这个位姿图校正阶段的自由度，不是 Local Inertial BA 或 Full Inertial BA 的变量总数。** 后两者仍然处理完整姿态、速度、偏置与地标。

### 8.2 地图内回环与跨地图合并是两件事

跟踪失败后，Atlas 可以保留旧地图、创建新地图。当地点识别找到匹配区域时：若双方在同一地图内，是 loop closure；若属于不同地图，是 map merging。

跨地图时各自世界坐标不同。先估计地图间 Sim(3)/受约束变换，选择合并区域，把当前地图的局部窗口移到目标坐标系，融合重复点；在交界处进行 welding BA，将两边观测真正连接起来；再把校正传播到剩余地图。

<!-- vision-figure: orbslam3-3 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam3-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam3-3.webp" width="861" height="1118" alt="ORB-SLAM3 原论文 Figure 3：welding BA 在两张地图接缝处联合使用视觉、IMU 和偏置随机游走约束。外围固定状态提供边界。" loading="lazy" /></a>
  <figcaption>ORB-SLAM3 原论文 Figure 3 · welding BA 在两张地图接缝处联合使用视觉、IMU 和偏置随机游走约束。外围固定状态提供边界。 <a href="https://arxiv.org/pdf/2007.11898v2#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: loop-atlas -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-atlas.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-atlas.svg" width="1100" height="470" alt="自制图 15：金色窗口示意两张地图接缝处参与联合优化的状态；外围状态作为边界，随后传播校正。" loading="lazy" /></a>
  <figcaption>自制图 15 · 金色窗口示意两张地图接缝处参与联合优化的状态；外围状态作为边界，随后传播校正。</figcaption>
</figure>
<!-- /vision-figure -->

这里“焊接”是具体的优化范围选择：让合并边界两侧的一组关键帧和地标共同优化，外部状态作为边界。它不同于简单拼接两个点云文件，也不同于只把新地图根节点挂到旧地图生成树上。

### 8.3 为什么大惯性地图不一定每次运行全局 BA

固定 `LoopClosing.cc` 中，闭环后只在“尚未完成 IMU 初始化”，或“地图少于 200 个关键帧且 Atlas 只有一个地图”等条件下启动 GBA。已初始化的惯性路径进入 `FullInertialBA()`，纯视觉路径使用视觉 GBA。

这体现实际系统的时间预算：先通过地图融合和 Essential Graph 获得可用全局一致性，再按规模决定是否进行更昂贵的联合优化。不能把 ORB-SLAM2 的“每次闭环后启动 GBA”直接套到 ORB-SLAM3 所有运行模式。

### 8.4 识别能力的改进为什么影响后端

ORB-SLAM3 强调在候选公共区域内先获得几何验证，再通过共视邻域与时间连续性增强确认，支持更快发现可复用地图。后端能否融合，首先取决于是否找到了足够可靠的公共区域；优化器本身不会创造数据关联。

<!-- vision-figure: orbslam3-4 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam3-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam3-4.webp" width="862" height="592" alt="ORB-SLAM3 原论文 Figure 4：EuRoC 每序列十次运行的 ATE 分布。多次执行体现系统随机性，不能只摘最好一次代表稳定性能。" loading="lazy" /></a>
  <figcaption>ORB-SLAM3 原论文 Figure 4 · EuRoC 每序列十次运行的 ATE 分布。多次执行体现系统随机性，不能只摘最好一次代表稳定性能。 <a href="https://arxiv.org/pdf/2007.11898v2#page=11" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: orbslam3-5 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam3-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam3-5.webp" width="1630" height="685" alt="ORB-SLAM3 原论文 Figure 5：TUM-VI 多会话立体惯性地图的不同视角。历史会话增加了约束，不能直接与无历史单次运行视作同条件。" loading="lazy" /></a>
  <figcaption>ORB-SLAM3 原论文 Figure 5 · TUM-VI 多会话立体惯性地图的不同视角。历史会话增加了约束，不能直接与无历史单次运行视作同条件。 <a href="https://arxiv.org/pdf/2007.11898v2#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: orbslam3-6 -->
<figure>
  <a href="/HomepageX/media/loop-closure/orbslam3-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/orbslam3-6.webp" width="862" height="893" alt="ORB-SLAM3 原论文 Figure 6：先处理一条历史轨迹再处理户外轨迹的多会话改善。地图复用帮助抑制长程漂移，仍依赖可靠公共区域。" loading="lazy" /></a>
  <figcaption>ORB-SLAM3 原论文 Figure 6 · 先处理一条历史轨迹再处理户外轨迹的多会话改善。地图复用帮助抑制长程漂移，仍依赖可靠公共区域。 <a href="https://arxiv.org/pdf/2007.11898v2#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

实验中的多次访问与地图复用应结合地图是否已存在来读。单次运行精度、多会话复用精度和最终全局优化精度不是同一种设置。把它们混成一列排名，会掩盖系统多用到的历史信息。

## 9. VINS-Fusion：局部 VIO 与全局回环图保持不同职责

### 9.1 滑窗里保留什么，移走什么

局部估计器维护位姿、速度、IMU 偏置、特征逆深度及可选标定参数，在视觉、IMU 和边缘化先验上优化。关键帧策略依据视差等条件决定移走最旧帧还是次新帧：前者主要保留较长几何基线，后者避免无效帧占满窗口并维持惯性连接。

固定代码的 `MARGIN_OLD` 会构建新的边缘化信息；`MARGIN_SECOND_NEW` 有专门的先验处理与 IMU 测量合并路径，并不是对两种情况调用一个完全相同的“删除帧”操作。

<!-- vision-figure: vinsmono-2 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-2.webp" width="1685" height="717" alt="VINS-Mono 原论文 Figure 2：VINS-Mono 的完整流水线，作为 VINS-Fusion 同源设计的背景。具体独立回环节点行为仍以 Fusion 代码为准。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 2 · VINS-Mono 的完整流水线，作为 VINS-Fusion 同源设计的背景。具体独立回环节点行为仍以 Fusion 代码为准。 <a href="https://arxiv.org/pdf/1708.03852v1#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: vinsmono-3 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-3.webp" width="1729" height="432" alt="VINS-Mono 原论文 Figure 3：带重定位的局部视觉惯性窗口。不同颜色表示历史、窗口与新测量依赖，不能缩成只有位置的图。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 3 · 带重定位的局部视觉惯性窗口。不同颜色表示历史、窗口与新测量依赖，不能缩成只有位置的图。 <a href="https://arxiv.org/pdf/1708.03852v1#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: vinsmono-7 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-7.webp" width="861" height="465" alt="VINS-Mono 原论文 Figure 7：关键帧与非关键帧对应的两种滑窗维护路径。边缘化旧帧与移除次新非关键帧涉及不同测量处理。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 7 · 关键帧与非关键帧对应的两种滑窗维护路径。边缘化旧帧与移除次新非关键帧涉及不同测量处理。 <a href="https://arxiv.org/pdf/1708.03852v1#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 3 显示局部活动状态、历史闭环状态和观测点；Figure 7 则区分关键帧与非关键帧离窗时的处理。黄色惯性连接与红色视觉关联的去留不同，正对应“移走哪个状态”不能只按队列顺序决定。

<!-- vision-figure: vinsmono-4 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-4.webp" width="862" height="322" alt="VINS-Mono 原论文 Figure 4：视觉惯性初始化中的对齐。尺度、重力、速度与偏置尚未稳定时，闭环允许的变换不能直接套成熟阶段。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 4 · 视觉惯性初始化中的对齐。尺度、重力、速度与偏置尚未稳定时，闭环允许的变换不能直接套成熟阶段。 <a href="https://arxiv.org/pdf/1708.03852v1#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: vinsmono-5 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-5.webp" width="862" height="351" alt="VINS-Mono 原论文 Figure 5：重力大小已知时的二维切空间。约束重力方向与固定完整相机姿态是不同事情。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 5 · 重力大小已知时的二维切空间。约束重力方向与固定完整相机姿态是不同事情。 <a href="https://arxiv.org/pdf/1708.03852v1#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 4 将无尺度视觉 SfM 与惯性预积分对齐；Figure 5 在固定重力模长的球面上用两个切向增量修正重力方向。先解决尺度、重力和速度的初始化，才有后面的四自由度全局漂移模型。

这里用 VINS-Mono 论文解释同源的滑窗与四自由度思想，具体 VINS-Fusion 行为以 `vins_estimator` 和 `loop_fusion` 代码为准。VINS-Fusion 支持的传感器组合更多，不能仅凭 VINS-Mono 的论文图替代代码核对。

### 9.2 回环数据库保留的是另一种历史

`loop_fusion` 接收关键帧位姿、图像与特征/三维点信息，建立独立数据库和位姿图。候选通过 BRIEF 匹配及 PnP RANSAC 验证，计算历史帧与当前帧之间的相对变换。固定代码还检查相对 yaw 与平移幅度，这些门限针对其应用设置，不能概括成任意运动平台的合理回环范围。

局部窗口里某个状态已经边缘化，不妨碍全局位姿图仍保留对应关键帧节点；但这不表示全局模块保留了局部估计器的全部历史像素和 IMU 因子。

<!-- vision-figure: loop-vins-two-graphs -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-vins-two-graphs.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-vins-two-graphs.svg" width="1100" height="470" alt="自制图 16：两种历史结构同时存在；独立 loop_fusion 的位姿图校正并不重建局部窗口已经丢弃的全部非线性测量。" loading="lazy" /></a>
  <figcaption>自制图 16 · 两种历史结构同时存在；独立 loop_fusion 的位姿图校正并不重建局部窗口已经丢弃的全部非线性测量。</figcaption>
</figure>
<!-- /vision-figure -->

### 9.3 有 IMU 时的四自由度误差

将每个关键帧参数写成 $(\mathbf p_i,\psi_i)$，roll/pitch 取自 VIO。设

$$
R_i=R_z(\psi_i)R_y(\theta_i^{VIO})R_x(\phi_i^{VIO}).
$$

对相对平移测量 $\widehat{\mathbf t}_{ij}$ 和 yaw 差 $\widehat\psi_{ij}$，可写

$$
\mathbf e_{ij}^{4D}=\begin{bmatrix}
R_i^{\mathsf T}(\mathbf p_j-\mathbf p_i)-\widehat{\mathbf t}_{ij}\\
\operatorname{wrap}(\psi_j-\psi_i-\widehat\psi_{ij})
\end{bmatrix}.
$$

注意平移误差在 i 的机体系中表达，不能直接拿世界坐标位移相减。固定实现的角度工具以度为单位，普通边与回环边的角度权重处理不同：`FourDOFWeightError` 将 yaw 残差额外除以 10，而普通 `FourDOFError` 没有这一项。本文公式统一表达结构；复现数字权重时必须回到代码单位。

`optimize4DoF()` 在同一序列内连接每个关键帧前面的最多四帧，而不只是前一帧，并添加已接受回环边。顺序边保留 VIO 相对估计，回环边使用鲁棒损失。它们通常不携带由完整滑窗边缘化得到的精确联合协方差，因此这是工程上的全局约束图。

### 9.4 无 IMU 的路径是 6DoF

`setIMUFlag()` 明确选择：有 IMU 启动 `optimize4DoF()`，无 IMU 启动 `optimize6DoF()`。后者优化四元数与平移，使用相对旋转和平移残差。

因此“VINS-Fusion 回环永远只优化四自由度”不成立。无 IMU 路径通常配合具有尺度的双目 VO；代码存在 6DoF 图，不代表它自动解决无尺度单目 VO 的 Sim(3) 漂移问题。

### 9.5 优化后如何修正新的输出

在最后已优化关键帧 k，4DoF 路径计算 yaw 漂移旋转 $R_d$ 与平移

$$
\mathbf t_d=\mathbf p_k^{PG}-R_d\mathbf p_k^{VIO}.
$$

之后到来的或尚未直接优化的位姿先用

$$
\mathbf p_t^{out}=R_d\mathbf p_t^{VIO}+\mathbf t_d,
\qquad R_t^{out}=R_dR_t^{VIO}
$$

进行全局对齐。6DoF 路径则使用相应完整旋转校正。这是 map 与局部 odometry 坐标关系的更新，不等价于把历史所有像素重新 BA 一遍。

VINS-Fusion 的独立 `loop_fusion` 回环图没有在该路径里联合优化全部历史三维地标、速度和偏置。若需求是高一致性稠密地图，还需明确各局部地图/点云如何根据关键帧校正更新，不能只发布一条修正轨迹就认为地图已经融合。

### 9.6 VINS-Mono 的紧耦合重定位，与独立回环图应区分

<!-- vision-figure: vinsmono-6 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-6.webp" width="763" height="321" alt="VINS-Mono 原论文 Figure 6：单位球上的视觉残差。鱼眼等模型可以用射线几何表达误差，不能无条件套针孔像素 Jacobian。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 6 · 单位球上的视觉残差。鱼眼等模型可以用射线几何表达误差，不能无条件套针孔像素 Jacobian。 <a href="https://arxiv.org/pdf/1708.03852v1#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 6 用单位球面切空间描述视觉误差，避免把所有镜头模型都硬套到同一平面针孔坐标。误差形式必须与相机投影模型及噪声尺度一致。

<!-- vision-figure: vinsmono-8 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-8.webp" width="862" height="301" alt="VINS-Mono 原论文 Figure 8：为相机频率输出进行的 motion-only 优化。只改当前运动状态与局部联合 BA 的成本和作用不同。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 8 · 为相机频率输出进行的 motion-only 优化。只改当前运动状态与局部联合 BA 的成本和作用不同。 <a href="https://arxiv.org/pdf/1708.03852v1#page=9" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: vinsmono-9 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-9.webp" width="862" height="1145" alt="VINS-Mono 原论文 Figure 9：重定位与四自由度全局图优化的分工。把当前窗口对齐旧地图与把全历史误差摊开是两个阶段。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 9 · 重定位与四自由度全局图优化的分工。把当前窗口对齐旧地图与把全历史误差摊开是两个阶段。 <a href="https://arxiv.org/pdf/1708.03852v1#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: vinsmono-10 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-10.webp" width="861" height="956" alt="VINS-Mono 原论文 Figure 10：回环特征检索中的逐级外点去除。描述匹配只是几何验证的起点，PnP 后支持范围也要检查。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 10 · 回环特征检索中的逐级外点去除。描述匹配只是几何验证的起点，PnP 后支持范围也要检查。 <a href="https://arxiv.org/pdf/1708.03852v1#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 8 将历史关键帧固定，利用新旧共同观测约束活动窗口；Figure 9 再把局部重定位与全局位姿图分开。Figure 10 从 BRIEF 候选经过 2D–2D、3D–2D 检查，逐步消除外点。原文 tightly coupled relocalization 不能直接等同于 VINS-Fusion 独立 `loop_fusion` 节点的全部代码路径。

### 9.7 实验中要区分局部精度、闭环校正与失效恢复

<!-- vision-figure: vinsmono-11 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-11.webp" width="799" height="542" alt="VINS-Mono 原论文 Figure 11：MH03 的轨迹比较。闭环版本应与未闭环版本分别标注，观察较长时段的漂移。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 11 · MH03 的轨迹比较。闭环版本应与未闭环版本分别标注，观察较长时段的漂移。 <a href="https://arxiv.org/pdf/1708.03852v1#page=12" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: vinsmono-12 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-12.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-12.webp" width="583" height="895" alt="VINS-Mono 原论文 Figure 12：MH03 的分轴误差与随路程变化。闭环消除的是累计偏差，不表示每一时刻的局部误差都变小。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 12 · MH03 的分轴误差与随路程变化。闭环消除的是累计偏差，不表示每一时刻的局部误差都变小。 <a href="https://arxiv.org/pdf/1708.03852v1#page=12" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

MH_03 的轨迹与分轴误差共同说明，视觉上相近的轨迹仍可能有可测漂移。该论文实验用最初一段输出进行对齐，再评估后续输出；不能把整条轨迹最优对齐后的 ATE 与它直接混比。

<!-- vision-figure: vinsmono-13 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-13.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-13.webp" width="738" height="554" alt="VINS-Mono 原论文 Figure 13：MH05 的困难运动轨迹。局部跟踪稳健性和全局回环分别决定能否持续估计及最终一致性。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 13 · MH05 的困难运动轨迹。局部跟踪稳健性和全局回环分别决定能否持续估计及最终一致性。 <a href="https://arxiv.org/pdf/1708.03852v1#page=12" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: vinsmono-14 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-14.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-14.webp" width="786" height="485" alt="VINS-Mono 原论文 Figure 14：MH05 的平移与旋转误差。回环前后变化帮助理解四自由度全局校正针对的漂移。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 14 · MH05 的平移与旋转误差。回环前后变化帮助理解四自由度全局校正针对的漂移。 <a href="https://arxiv.org/pdf/1708.03852v1#page=12" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

MH_05 的结果同时画出平移和旋转误差。回环更明显地改善长期位置，并不代表它必然降低每一个时刻的每一项姿态误差。

<!-- vision-figure: vinsmono-15 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-15.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-15.webp" width="862" height="465" alt="VINS-Mono 原论文 Figure 15：室内实验相机与 IMU 装置。传感器视野、同步和采样频率是比较结果的必要条件。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 15 · 室内实验相机与 IMU 装置。传感器视野、同步和采样频率是比较结果的必要条件。 <a href="https://arxiv.org/pdf/1708.03852v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: vinsmono-16 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-16.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-16.webp" width="799" height="628" alt="VINS-Mono 原论文 Figure 16：低纹理、光照变化与运动模糊的室内样例。失败来源应与对应的轨迹片段联系起来。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 16 · 低纹理、光照变化与运动模糊的室内样例。失败来源应与对应的轨迹片段联系起来。 <a href="https://arxiv.org/pdf/1708.03852v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: vinsmono-17 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-17.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-17.webp" width="858" height="965" alt="VINS-Mono 原论文 Figure 17：室内轨迹中 OKVIS 与不同 VINS 设置。比较前要确认是否启用回环，避免把系统职责差异归于局部估计器。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 17 · 室内轨迹中 OKVIS 与不同 VINS 设置。比较前要确认是否启用回环，避免把系统职责差异归于局部估计器。 <a href="https://arxiv.org/pdf/1708.03852v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

室内实验先展示传感器和困难画面，再给出闭环前后的轨迹。低纹理、反光与动态行人可能先破坏跟踪；闭环只能校正已获得的可靠关联，不能保证前端永不失效。

<!-- vision-figure: vinsmono-18 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-18.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-18.webp" width="862" height="516" alt="VINS-Mono 原论文 Figure 18：室内外混合路径与回环连接的地理示意。红线显示约束位置，不代表沿途每一点都取得绝对位置真值。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 18 · 室内外混合路径与回环连接的地理示意。红线显示约束位置，不代表沿途每一点都取得绝对位置真值。 <a href="https://arxiv.org/pdf/1708.03852v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: vinsmono-19 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-19.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-19.webp" width="862" height="782" alt="VINS-Mono 原论文 Figure 19：同一混合路径上无回环与有回环的差异。楼梯和无纹理区域暴露前端困难，闭环修正仍要求先存活到重访时刻。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 19 · 同一混合路径上无回环与有回环的差异。楼梯和无纹理区域暴露前端困难，闭环修正仍要求先存活到重访时刻。 <a href="https://arxiv.org/pdf/1708.03852v1#page=14" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

较长室外路线还涉及跟踪丢失与重定位。卫星底图上的视觉重合是定性参考，精确误差应来自可校准的真值与对齐协议，而非目测地图轮廓。

<!-- vision-figure: vinsmono-1 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-1.webp" width="861" height="1020" alt="VINS-Mono 原论文 Figure 1：长距离步行轨迹及地理叠加。回环把远时刻的估计连接起来，但地图叠图不替代精确测量真值。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 1 · 长距离步行轨迹及地理叠加。回环把远时刻的估计连接起来，但地图叠图不替代精确测量真值。 <a href="https://arxiv.org/pdf/1708.03852v1#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: vinsmono-20 -->
<figure>
  <a href="/HomepageX/media/loop-closure/vinsmono-20.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/vinsmono-20.webp" width="1729" height="807" alt="VINS-Mono 原论文 Figure 20：更大尺度路线上的闭环分布。它展示系统覆盖范围，精确误差仍需独立地面真值。" loading="lazy" /></a>
  <figcaption>VINS-Mono 原论文 Figure 20 · 更大尺度路线上的闭环分布。它展示系统覆盖范围，精确误差仍需独立地面真值。 <a href="https://arxiv.org/pdf/1708.03852v1#page=15" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 1 与 Figure 20 展示更大范围的系统应用。它们说明维护历史数据库和全局图的价值，但不能仅凭闭合轨迹断言每段局部速度、偏置和所有三维地标都已全局最优。

## 10. OKVIS → OKVIS2：压缩历史，还要能重新打开历史

### 10.1 原始 OKVIS 的重点是有界窗口内的紧耦合估计

原始 OKVIS 把多相机重投影与 IMU 约束放进同一个优化问题，并用关键帧选择、边缘化控制复杂度。与只按最近时间截断相比，保留有视差、重叠有价值的关键帧能更好地约束结构。

<!-- vision-figure: okvis-1 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-1.webp" width="836" height="531" alt="OKVIS 原论文 Figure 1：原始 OKVIS 的同步双目/IMU 硬件与楼梯轨迹。紧耦合估计的传感器条件在图中明确给出。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 1 · 原始 OKVIS 的同步双目/IMU 硬件与楼梯轨迹。紧耦合估计的传感器条件在图中明确给出。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=1" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis-2 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-2.webp" width="836" height="308" alt="OKVIS 原论文 Figure 2：纯视觉与视觉惯性的状态、测量图比较。IMU 把相邻运动状态联系起来并引入速度和偏置。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 2 · 纯视觉与视觉惯性的状态、测量图比较。IMU 把相邻运动状态联系起来并引入速度和偏置。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

2013 RSS 论文与 2015 IJRR 版本奠定这条路线，但不能因为题目里出现 SLAM，就把后来 OKVIS2 的长期地点识别、观测恢复和闭环线程都倒推给原始系统。OKVIS2 明确把可扩展地图管理与回环作为新增重点。

<!-- vision-figure: okvis-3 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-3.webp" width="688" height="359" alt="OKVIS 原论文 Figure 3：相机、IMU 与世界的坐标系。外参方向必须与重投影和惯性方程统一。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 3 · 相机、IMU 与世界的坐标系。外参方向必须与重投影和惯性方程统一。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis-4 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-4.webp" width="480" height="132" alt="OKVIS 原论文 Figure 4：相机帧之间的多次 IMU 测量组成一个惯性项。预积分降低优化时重复处理高频数据的成本。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 4 · 相机帧之间的多次 IMU 测量组成一个惯性项。预积分降低优化时重复处理高频数据的成本。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

RSS 原文 Figure 3 明确相机、IMU 与世界坐标系，Figure 4 强调两帧相机测量之间通常有多次 IMU 采样。联合优化必须处理外参和时间跨度，否则把两种测量简单加在同一个目标里也不会自动紧耦合正确。

<!-- vision-figure: okvis-5 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-5.webp" width="732" height="295" alt="OKVIS 原论文 Figure 5：保留用于匹配和优化的帧。关键帧选择考虑空间约束，而非只按固定时间截取。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 5 · 保留用于匹配和优化的帧。关键帧选择考虑空间约束，而非只按固定时间截取。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis-6 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-6.webp" width="837" height="348" alt="OKVIS 原论文 Figure 6：最初窗口的边缘化结构。移走旧状态后，剩余变量之间出现新的先验关联。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 6 · 最初窗口的边缘化结构。移走旧状态后，剩余变量之间出现新的先验关联。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 5–6 同时保留时间窗口与关键帧窗口：近期状态负责惯性连续性，关键帧负责保留有价值的视觉基线。不是每个状态都采用同样的保留寿命。

<!-- vision-figure: okvis-7 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-7.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-7.webp" width="837" height="369" alt="OKVIS 原论文 Figure 7：关键帧与时间窗口共同维护。普通帧离开时间窗口时，需要处理与其相连的惯性及视觉信息。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 7 · 关键帧与时间窗口共同维护。普通帧离开时间窗口时，需要处理与其相连的惯性及视觉信息。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis-8 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-8.webp" width="787" height="328" alt="OKVIS 原论文 Figure 8：具体边缘化步骤中的状态依赖。新先验是已线性化历史信息的摘要，不是可任意重新线性化的原图。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 8 · 具体边缘化步骤中的状态依赖。新先验是已线性化历史信息的摘要，不是可任意重新线性化的原图。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 7 的非关键帧退出与 Figure 8 的最旧关键帧退出，处理的视觉观测不同。前者会丢弃一些视觉测量以控制稀疏性；后者要把关键帧及相关地标信息压入先验。粉色先验因子体现的是一次线性化后的历史摘要，不是还能任意重新打开的完整图像记录。

<!-- vision-figure: okvis-9 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-9.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-9.webp" width="837" height="589" alt="OKVIS 原论文 Figure 9：相同关键点测量下与 Vicon 真值的误差比较，包含均值和分位范围。固定关联有助于隔离估计器差异。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 9 · 相同关键点测量下与 Vicon 真值的误差比较，包含均值和分位范围。固定关联有助于隔离估计器差异。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis-10 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-10.webp" width="795" height="548" alt="OKVIS 原论文 Figure 10：车辆轨迹与 Applanix 真值。不同运动模式改变尺度与偏置的可观性。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 10 · 车辆轨迹与 Applanix 真值。不同运动模式改变尺度与偏置的可观性。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis-11 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-11.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-11.webp" width="836" height="439" alt="OKVIS 原论文 Figure 11：六自由度地面真值下的误差统计。坐标与误差条需保留，不能只按轨迹外观判断。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 11 · 六自由度地面真值下的误差统计。坐标与误差条需保留，不能只按轨迹外观判断。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis-12 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis-12.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis-12.webp" width="1678" height="367" alt="OKVIS 原论文 Figure 12：建筑路径与平面图的人工对齐。提供定性结构参考，人工平面对齐不能替代全程高精度三维真值。" loading="lazy" /></a>
  <figcaption>OKVIS 原论文 Figure 12 · 建筑路径与平面图的人工对齐。提供定性结构参考，人工平面对齐不能替代全程高精度三维真值。 <a href="https://www.roboticsproceedings.org/rss09/p37.pdf#page=8" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

RSS 实验由有真值的短程运动、汽车长程轨迹到室内地图逐层展开。紧耦合相对纯视觉和松耦合的收益，与“显式闭环使整条地图重优化”的收益要分开：原文说明没有强制执行回环闭合，这些结果主要验证局部视觉惯性估计。

### 10.2 OKVIS2 的目标函数里同时有三种测量

<!-- vision-figure: okvis2-1 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2-1.webp" width="841" height="532" alt="OKVIS2 原论文 Figure 1：实时估计器维护有界混合图，全图估计器在回环后异步优化。两个图需要同步而非互相独立输出。" loading="lazy" /></a>
  <figcaption>OKVIS2 原论文 Figure 1 · 实时估计器维护有界混合图，全图估计器在回环后异步优化。两个图需要同步而非互相独立输出。 <a href="https://arxiv.org/pdf/2202.09199v1#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis2-2 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2-2.webp" width="841" height="722" alt="OKVIS2 原论文 Figure 2：从完整视觉惯性图，到压缩位姿节点，再到回环恢复观测。虚线区分固定参数与活动变量。" loading="lazy" /></a>
  <figcaption>OKVIS2 原论文 Figure 2 · 从完整视觉惯性图，到压缩位姿节点，再到回环恢复观测。虚线区分固定参数与活动变量。 <a href="https://arxiv.org/pdf/2202.09199v1#page=4" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

实时估计器联合使用视觉重投影、IMU 和压缩后的相对位姿因子：

$$
E_{RT}=\sum E_{visual}+\sum E_{IMU}+\sum E_{posegraph}+E_{anchor}.
$$

最近的非关键帧和一组有用关键帧保留完整观测；离当前视野较远的关键帧逐渐转成位姿图节点；更旧的一部分状态固定，保证每帧计算有界。这样活动优化范围可以比“全部保留视觉点”的窗口更长。

原论文 Figure 2 的实线/虚线和不同节点形状很关键：固定参数仍然在图里提供边界，转换成位姿图节点也不等于历史数据永久销毁。回环时部分历史观测会被重新激活。

### 10.3 压缩一对关键帧的共同观测，信息矩阵怎么来

考虑两帧 r,c 及共同地标，把地标先表达到 r 的机体系，以相对位姿 p 为状态。它们的重投影目标在当前点线性化，正规方程写成

$$
\begin{bmatrix}H_{pp}&H_{pl}\\H_{lp}&H_{ll}\end{bmatrix}
\begin{bmatrix}\delta p\\\delta l\end{bmatrix}
=\begin{bmatrix}b_p\\b_l\end{bmatrix}.
$$

这里为了对照论文，右端使用 $b=-g$。消去地标得到

$$
H^*=H_{pp}-H_{pl}H_{ll}^{+}H_{lp},\qquad
b^*=b_p-H_{pl}H_{ll}^{+}b_l.
$$

在选定线性化点 $\widetilde p$ 附近，用

$$
\mathbf e_{rc}=\mathbf e_0+(p\boxminus\widetilde p),\qquad
W_{rc}=H^*,\qquad
\mathbf e_0=-(H^*)^+b^*
$$

构成相对位姿代价 $\tfrac12\mathbf e_{rc}^{\mathsf T}W_{rc}\mathbf e_{rc}$。在参考点上，局部 Jacobian 近似单位阵，其正规方程复现被压缩视觉信息的二阶近似。

<!-- vision-figure: loop-okvis-compress -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-okvis-compress.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-okvis-compress.svg" width="1100" height="470" alt="自制图 17：Schur 消去地标后形成相对位姿因子；信息矩阵携带方向相关约束，但成对压缩仍可能重复计算共享观测。" loading="lazy" /></a>
  <figcaption>自制图 17 · Schur 消去地标后形成相对位姿因子；信息矩阵携带方向相关约束，但成对压缩仍可能重复计算共享观测。</figcaption>
</figure>
<!-- /vision-figure -->

与“取当前相对位姿，随手给单位权重”相比，这里的信息矩阵反映共同观测对不同运动方向的约束强弱。但它仍是局部近似，不是保留所有非线性视觉信息的精确等价。

### 10.4 为什么用最大生成树挑选连接

如果一个待转换关键帧与十个历史帧都共视，全部建立两两压缩边会让图过密。OKVIS2 在一组候选节点上，以共同观测数量为权计算 Maximum Spanning Tree，再建立与待转换节点相关的树边。

<!-- vision-figure: okvis2-3 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2-3.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2-3.webp" width="842" height="940" alt="OKVIS2 原论文 Figure 3：最大生成树选择待压缩节点的连接。权重来自共同观测数，以较稀疏结构保留有用关系。" loading="lazy" /></a>
  <figcaption>OKVIS2 原论文 Figure 3 · 最大生成树选择待压缩节点的连接。权重来自共同观测数，以较稀疏结构保留有用关系。 <a href="https://arxiv.org/pdf/2202.09199v1#page=5" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

这与 ORB 维护地图父子连通性的生成树不是同一个使用目的。这里的树用于选择压缩约束，控制复杂度并偏向有较多共享观测的连接。

原论文明确承认：当同一地标被多帧观察并参与多条成对压缩边时，会重复使用部分观测，带来设计上的不一致性。不能把“用了 Schur complement”自动理解成统计上严格无损、无重复计数。作者论点是这种近似仍比随意单位权重更有信息，而非完全消除了相关性问题。

### 10.5 检测回环后，先重定位，再恢复观测

DBoW2 找到候选 l，3D–2D RANSAC 通过后，系统将当前活动状态和地标对齐到匹配历史帧。接着，把与 l 相关的压缩边“打开”：根据归档信息重新激活历史地标及重投影观测，并为当前帧建立新观测，必要时合并地标。

<!-- vision-figure: loop-okvis-revive -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-okvis-revive.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-okvis-revive.svg" width="1100" height="470" alt="自制图 18：压缩因子和原始数据归档承担不同职责；回环恢复的是保存下来的观测，不是从 Hessian 唯一反演出来的图像。" loading="lazy" /></a>
  <figcaption>自制图 18 · 压缩因子和原始数据归档承担不同职责；回环恢复的是保存下来的观测，不是从 Hessian 唯一反演出来的图像。</figcaption>
</figure>
<!-- /vision-figure -->

恢复的前提是原始关联与观测另有保存。仅持有一个 $6\times6$ 信息矩阵，不可能唯一恢复当年数百个像素、各自坐标和三维点。这个细节决定了实现的数据结构与内存需求。

被恢复的历史帧通常很旧，在实时图中可能仍固定；它们首先帮助当前窗口重定位。随后闭环后台优化会改变活动范围，使环内历史状态可以一起调整。

### 10.6 全图后台优化仍带 IMU，不只是一个纯位姿图

作者先用旋转平均和位置误差分配给闭环提供较一致的初值，再在后台复制的因子图上优化环内状态。图中保留 IMU 因子，因此重力方向与惯性运动一致性继续参与，而不仅是用几条 SE(3) 弹簧拉轨迹。

优化完成后，把状态和地标同步回实时估计器，并对后台计算期间新增的状态进行对齐。固定代码使用 `realtimeGraph_`、`fullGraph_` 以及待补入的状态和地标记录协调两个图。最终还要限制被恢复的历史关键帧数量，把不再需要完整视觉观测的部分重新压缩。

这套流程把“实时能算得动”和“重访时能利用旧观测”连接起来。它也说明 OKVIS2 的全图优化并不必然是一次保留全部历史视觉点的传统 Full BA：图里可以混合恢复的视觉因子、IMU 因子和压缩相对位姿因子。

### 10.7 原图里的失败、精度与因果性

<!-- vision-figure: okvis2-4 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2-4.webp" width="841" height="844" alt="OKVIS2 原论文 Figure 4：天空分割与使用的特征，保留误分类样例。语义筛点也会有假阳性和假阴性，不能作为完美静态掩码。" loading="lazy" /></a>
  <figcaption>OKVIS2 原论文 Figure 4 · 天空分割与使用的特征，保留误分类样例。语义筛点也会有假阳性和假阴性，不能作为完美静态掩码。 <a href="https://arxiv.org/pdf/2202.09199v1#page=6" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 4 展示分割掩码会犯错：天空或树木过滤有助于排除无穷远和不稳定特征，但错分也可能删掉有效结构。语义模块引入的是有误差的新证据，不能当成完美的静态场景标签。

<!-- vision-figure: okvis2-5 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2-5.webp" width="841" height="679" alt="OKVIS2 原论文 Figure 5：EuRoC MH05 不同子轨迹长度的相对误差分布。随距离变化的统计比一条最终 ATE 更能显示漂移性质。" loading="lazy" /></a>
  <figcaption>OKVIS2 原论文 Figure 5 · EuRoC MH05 不同子轨迹长度的相对误差分布。随距离变化的统计比一条最终 ATE 更能显示漂移性质。 <a href="https://arxiv.org/pdf/2202.09199v1#page=7" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 5 按行进距离统计位置、倾角与方位误差，并保留离散程度。应先比较同种在线/最终轨迹设置，再判断闭环收益；均值下降不代表最困难尾部误差也消失。

论文区分因果在线轨迹与最终经过闭环调整的非因果轨迹：前者是在当时能输出的估计，后者可以利用未来才看到的回环。机器人控制首先面对前者，离线建图可能更关心后者，两者都值得报告。

后台优化不阻塞每帧估计，并不等于没有计算成本。核对原文运行时间表时，应把前端、实时优化、后台闭环和总 CPU 资源分开；很长的闭环仍可能花较长时间。误差突然下降也可能对应全局坐标校正，不能被误读成局部运动估计突然无噪声。

## 11. OKVIS2-X：闭环之后，稠密地图如何跟着动

[OKVIS2-X，2025](https://arxiv.org/abs/2510.04612v1) 在 OKVIS2 基础上加入测量或学习深度、LiDAR、GNSS，以及稠密体积占据子地图。它不是把更多传感器仅用于可视化，而是把地图对齐等测量加入估计器。

### 11.1 子地图局部坐标避免每次重写全部体素

设子地图 a 的局部点为 $\mathbf q_a$，锚定位姿为 $T_{Wa}$，则 $\mathbf q_W=T_{Wa}\mathbf q_a$。闭环先改变 $T_{Wa}$，局部体素仍留在自己的坐标中。这样可以让大规模稠密地图随关键帧校正移动，而不要求每次把所有历史深度重新融合一遍。

<!-- vision-figure: okvis2x-1 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2x-1.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2x-1.webp" width="861" height="983" alt="OKVIS2-X 原论文 Figure 1：同一环境用 LiDAR 与学习深度构建的体积子地图。颜色区分子地图，黑色表示轨迹。" loading="lazy" /></a>
  <figcaption>OKVIS2-X 原论文 Figure 1 · 同一环境用 LiDAR 与学习深度构建的体积子地图。颜色区分子地图，黑色表示轨迹。 <a href="https://arxiv.org/pdf/2510.04612v1#page=2" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: loop-submaps -->
<figure>
  <a href="/HomepageX/media/loop-closure/loop-submaps.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/loop-submaps.svg" width="1100" height="470" alt="自制图 19：刚性移动子地图降低全局校正成本；若子地图内部已发生明显形变，只修改锚定位姿仍不够。" loading="lazy" /></a>
  <figcaption>自制图 19 · 刚性移动子地图降低全局校正成本；若子地图内部已发生明显形变，只修改锚定位姿仍不够。</figcaption>
</figure>
<!-- /vision-figure -->

但一个子地图内部若已经积累显著非刚性误差，仅移动锚点不能消除内部变形。子地图大小、创建频率、重叠区域和对齐约束决定这个近似的质量。

### 11.2 地图对齐和 GNSS 给后端增加什么

地图对齐约束让不同子地图或实时扫描与地图的几何结构互相约束。以常见的点到局部隐式表面距离为直觉，可写教学形式

$$
r_{ab}(\mathbf q_b)=d_a(T_{Wa}^{-1}T_{Wb}\mathbf q_b),
$$

其中 $d_a$ 是子地图 a 的表面距离函数。实际 OKVIS2-X 的占据表示、残差和不确定性处理应按原文实现，这个简化式只解释“约束依赖两个地图位姿”，不是逐项复刻其全部因子。

GNSS 天线有杆臂 $\mathbf l_B$，预测世界位置为 $\mathbf p_i+R_i\mathbf l_B$，还需估计/维护 SLAM 世界与全球坐标的对齐。GNSS 提供绝对位置约束，和外观回环的相对约束作用不同；短期退化、遮挡、多路径和初始化可观性仍需处理。

<!-- vision-figure: okvis2x-2 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2x-2.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2x-2.webp" width="1729" height="1000" alt="OKVIS2-X 原论文 Figure 2：多传感器系统结构，灰色为原 OKVIS2 模块、白色为新增部分。密集地图与估计器通过约束交换信息。" loading="lazy" /></a>
  <figcaption>OKVIS2-X 原论文 Figure 2 · 多传感器系统结构，灰色为原 OKVIS2 模块、白色为新增部分。密集地图与估计器通过约束交换信息。 <a href="https://arxiv.org/pdf/2510.04612v1#page=3" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis2x-4 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2x-4.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2x-4.webp" width="862" height="839" alt="OKVIS2-X 原论文 Figure 4：多传感器扩展下的实时与回环图维护。观测压缩和恢复沿用 OKVIS2 思路，并引入额外状态/测量。" loading="lazy" /></a>
  <figcaption>OKVIS2-X 原论文 Figure 4 · 多传感器扩展下的实时与回环图维护。观测压缩和恢复沿用 OKVIS2 思路，并引入额外状态/测量。 <a href="https://arxiv.org/pdf/2510.04612v1#page=9" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis2x-5 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2x-5.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2x-5.webp" width="862" height="266" alt="OKVIS2-X 原论文 Figure 5：实时 frame-to-map 与跨子地图 map-to-map 因子。稠密几何不只被显示，也进入位姿估计。" loading="lazy" /></a>
  <figcaption>OKVIS2-X 原论文 Figure 5 · 实时 frame-to-map 与跨子地图 map-to-map 因子。稠密几何不只被显示，也进入位姿估计。 <a href="https://arxiv.org/pdf/2510.04612v1#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 2 给出传感器与双图估计器的关系；Figure 4 在既有图中增加在线外参等变量；Figure 5 则明确 frame-to-map 与 map-to-map 因子。它们的连接对象不同，不能都压缩成一条“回环边”。

<!-- vision-figure: okvis2x-6 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2x-6.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2x-6.webp" width="861" height="289" alt="OKVIS2-X 原论文 Figure 6：GNSS 测量时刻与相机时刻不重合时，用 IMU 传播得到中间状态评估全局残差。" loading="lazy" /></a>
  <figcaption>OKVIS2-X 原论文 Figure 6 · GNSS 测量时刻与相机时刻不重合时，用 IMU 传播得到中间状态评估全局残差。 <a href="https://arxiv.org/pdf/2510.04612v1#page=10" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 6 说明全局传感器时间戳可能落在相邻图状态之间，需要通过惯性传播把测量关联到正确时刻。忽略时间对应会把运动误差误解释成外参或地图误差。

### 11.3 多传感器收益要连同退化与成本检查

<!-- vision-figure: okvis2x-8 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2x-8.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2x-8.webp" width="861" height="594" alt="OKVIS2-X 原论文 Figure 8：暗室中视觉退化而 LiDAR 提供补充的失败案例。多传感器价值取决于失效模式是否互补。" loading="lazy" /></a>
  <figcaption>OKVIS2-X 原论文 Figure 8 · 暗室中视觉退化而 LiDAR 提供补充的失败案例。多传感器价值取决于失效模式是否互补。 <a href="https://arxiv.org/pdf/2510.04612v1#page=13" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis2x-10 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2x-10.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2x-10.webp" width="1729" height="373" alt="OKVIS2-X 原论文 Figure 10：Campus1 的因果轨迹、GNSS 可用/不可用区与子地图。视觉深度配置在 GNSS 缺失区仍可明显漂移。" loading="lazy" /></a>
  <figcaption>OKVIS2-X 原论文 Figure 10 · Campus1 的因果轨迹、GNSS 可用/不可用区与子地图。视觉深度配置在 GNSS 缺失区仍可明显漂移。 <a href="https://arxiv.org/pdf/2510.04612v1#page=16" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 8 故意让相机失效，检查其他几何约束能否继续维持位置；Figure 10 展示更大区域地图中的全局对齐。传感器增加并不保证绝对定位始终可靠，仍需考虑可用性、初始化与测量权重。

<!-- vision-figure: okvis2x-12 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2x-12.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2x-12.webp" width="1729" height="571" alt="OKVIS2-X 原论文 Figure 12：不同配置的多线程耗时拆分。并行线程柱高不能直接相加当作每帧延迟。" loading="lazy" /></a>
  <figcaption>OKVIS2-X 原论文 Figure 12 · 不同配置的多线程耗时拆分。并行线程柱高不能直接相加当作每帧延迟。 <a href="https://arxiv.org/pdf/2510.04612v1#page=18" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->
<!-- vision-figure: okvis2x-13 -->
<figure>
  <a href="/HomepageX/media/loop-closure/okvis2x-13.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/loop-closure/okvis2x-13.webp" width="862" height="982" alt="OKVIS2-X 原论文 Figure 13：关键帧数、IMU 帧数、地图因子数与体素分辨率的参数研究。精度与实时图耗时必须一起取舍。" loading="lazy" /></a>
  <figcaption>OKVIS2-X 原论文 Figure 13 · 关键帧数、IMU 帧数、地图因子数与体素分辨率的参数研究。精度与实时图耗时必须一起取舍。 <a href="https://arxiv.org/pdf/2510.04612v1#page=18" target="_blank" rel="noopener">原文</a></figcaption>
</figure>
<!-- /vision-figure -->

Figure 12 拆开系统模块的运行时间，Figure 13 检查地图范围和关键帧数量相关设置对误差的影响。大地图、更多保留状态和更密几何约束都需要计算预算；应在目标硬件上验证实时轨迹，而不只看离线最终地图。

对回环篇最重要的延伸，是地图输出与状态估计的同步：轨迹、稀疏地标、子地图锚点、地图对齐因子必须使用一致版本。否则轨迹闭合了，规划器看到的障碍地图却仍停留在旧坐标。

## 12. 四类后端的差异，放到同一张表里

| 系统 | 平时保留的优化信息 | 闭环主要传播 | 视觉地标是否参与后续细化 | 惯性如何参与 |
| --- | --- | --- | --- | --- |
| ORB-SLAM2 | 关键帧、地图点、共视/生成树结构，Local BA | Sim(3) Essential Graph；有尺度时固定尺度 | 融合重复点，后台视觉 GBA | 无 IMU |
| ORB-SLAM3 | Atlas、视觉或视觉惯性局部优化 | 同地图闭环 / 跨地图焊接与传播；已初始化惯性图有 4DoF 路径 | 融合、局部焊接 BA；按条件 GBA | 局部/全局惯性 BA 保留速度偏置等 |
| VINS-Fusion | 有界 VIO/VO 窗口与边缘化先验；独立历史位姿图 | 有 IMU 4DoF、无 IMU 6DoF；输出漂移变换 | 独立 loop_fusion 不是全历史地标 BA | VIO 先提供姿态与尺度，回环图自身不重算全部 IMU 因子 |
| OKVIS2 | 实时混合图：视觉、IMU、压缩相对位姿；历史观测归档 | 恢复观测，后台混合全图优化，同步实时图 | 恢复部分旧点/观测并合并，参与联合优化 | 后台闭环仍保留 IMU 因子 |
| OKVIS2-X | 以上思路加子地图、多传感器因子 | 全局校正同时约束稠密子地图 | 稀疏与稠密几何共同服务系统 | 继续紧耦合，可加入 GNSS/LiDAR/深度 |

不能只问“有没有 BA”。更有区分力的问题是：BA 优化哪些变量，使用哪些原始测量，哪些状态固定，哪些信息被压缩，什么时候重新线性化，以及结果怎样写回在线地图。

## 13. 接入新的 VPR 或特征方法时，哪些接口必须想清楚

### 13.1 检索模块只替换候选来源

将 DBoW2 换成 NetVLAD、SALAD 或其他 VPR，可以改善外观变化下的候选召回。它不自动替换局部匹配、PnP/Sim(3) 验证、地图点融合，也不直接生成信息矩阵。

例如检索到了夜间对应的白天关键帧，若地图中没有可重识别的静态局部地标，仍然无法形成稳定几何约束。应分别报告候选召回率、几何验证成功率、错误接受率和最终轨迹收益。

### 13.2 学习匹配器的分数不能直接当优化精度

LightGlue 给出的匹配分数与几何量测协方差不同。一个高分匹配可能落在重复结构上，也可能受下采样定位误差影响。要把它用于优化权重，应做校准或建立明确误差模型，并保留几何外点处理。

同样，RoMa 产生很多稠密匹配时，附近像素往往高度相关。把十万个邻近匹配都按独立一像素噪声计入 Hessian，会让系统严重过度自信。空间抽样、覆盖检查和不确定性建模比盲目增加数量更有意义。

### 13.3 一份能定位问题的闭环日志

调试时至少能追踪：候选帧 ID 和地图 ID；接受/拒绝原因；匹配数与几何内点分布；相对变换方向和尺度；闭环前后残差；受影响关键帧及地标数量；优化代次和同步时间；在线轨迹与最终轨迹版本。

如果闭环后轨迹突然翻转，先查变换方向与四元数约定；如果尺度突变，查传感器模式与惯性初始化；如果轨迹正确而点云错层，查地图点/子地图的同步；如果下一次局部优化把校正拉回去，查先验参考系与图间校正关系。每一种症状对应的是不同接口，不能都归结为“BA 没收敛”。

## 14. 把一次闭环按变量走完

回到开头两层墙的例子。检索首先给出旧关键帧候选；局部匹配把当前角点与旧地标联系起来；几何验证估计双方关系并剔除不一致对应。此时系统才拥有一条能够改变地图的约束。

接下来，根据系统保存的历史信息选择优化路线：ORB 系列对齐当前邻域、融合地标、在 Essential Graph 上传播并按条件 BA；VINS-Fusion 在独立位姿图上优化历史关键帧并更新全局漂移变换；OKVIS2 恢复部分历史观测，在混合图中联合利用视觉与惯性，再同步在线状态。稠密子地图系统还要更新地图锚点和几何关联。

因此一条正确回环的价值，不只是“终点碰到了起点”。它使原来相互分离的历史证据开始约束同一组物理状态。整个系统能改善到什么程度，取决于这些证据还保留多少、怎样近似、允许哪些变量重新调整。

## 论文与代码入口

- [ORB-SLAM2 论文 v2](https://arxiv.org/abs/1610.06475v2)；[LoopClosing.cc](https://github.com/raulmur/ORB_SLAM2/blob/f2e6f51cdc8d067655d90a78c06261378e07e8f3/src/LoopClosing.cc)、[Optimizer.cc](https://github.com/raulmur/ORB_SLAM2/blob/f2e6f51cdc8d067655d90a78c06261378e07e8f3/src/Optimizer.cc)。
- [ORB-SLAM3 论文 v2](https://arxiv.org/abs/2007.11898v2)；[LoopClosing.cc](https://github.com/UZ-SLAMLab/ORB_SLAM3/blob/4452a3c4ab75b1cde34e5505a36ec3f9edcdc4c4/src/LoopClosing.cc)。
- [VINS-Mono 论文 v1](https://arxiv.org/abs/1708.03852v1)；VINS-Fusion 的 [pose_graph.cpp](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion/blob/be55a937a57436548ddfb1bd324bc1e9a9e828e0/loop_fusion/src/pose_graph.cpp)、[pose_graph.h](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion/blob/be55a937a57436548ddfb1bd324bc1e9a9e828e0/loop_fusion/src/pose_graph.h)、[estimator.cpp](https://github.com/HKUST-Aerial-Robotics/VINS-Fusion/blob/be55a937a57436548ddfb1bd324bc1e9a9e828e0/vins_estimator/src/estimator/estimator.cpp)。
- [OKVIS，RSS 2013](https://www.roboticsproceedings.org/rss09/p37.pdf)、[IJRR 2015 作者机构记录](https://www.research-collection.ethz.ch/items/97c8848c-586b-4f7f-9a4a-e8a0fa41be81)。
- [OKVIS2 论文 v1](https://arxiv.org/abs/2202.09199v1)；[ViSlamBackend.cpp](https://github.com/ethz-mrl/okvis2/blob/a2ea00688cd10988aae7bd52ab7935ce9a657ec0/okvis_ceres/src/ViSlamBackend.cpp)。
- [OKVIS2-X 论文 v1](https://arxiv.org/abs/2510.04612v1)、[官方仓库](https://github.com/ethz-mrl/OKVIS2-X)。
