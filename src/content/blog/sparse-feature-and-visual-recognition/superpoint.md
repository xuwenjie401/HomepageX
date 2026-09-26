---
title: "读懂 SuperPoint：从画几何图形，到学会在真实世界里找对应点"
description: "沿着监督从哪里来这条线，理解 MagicPoint、Homographic Adaptation、65 通道检测头与联合训练，再回到实验和局限，看看下一步该改什么。"
date: 2026-09-26
tags: [论文精读, 计算机视觉, 局部特征, 自监督学习]
---

假设你拿着手机，对着书桌拍了两张照片。第二次拍摄时，你向右挪了一步，桌沿倾斜了一点，台灯还比刚才亮了。人很容易认出：两张照片里的书角，是同一个书角。

但如果让计算机回答“相机挪了多少”“这两张图能不能拼起来”，它首先需要一些足够可信的对应关系：第一张图的这个位置，确实对应第二张图的那个位置。

这就是局部特征的用武之地。SuperPoint 关心的不是识别“这是一本书”，而是找到一些值得反复认出的点，并给每个点一个可以比较的向量表示。

这篇文章想沿着一个问题往下走：**如果没有人告诉网络，真实照片里哪些点才算好点，它怎么学会这件事？** 架构和损失函数会在需要它们的时候出现。

> 论文信息：Daniel DeTone、Tomasz Malisiewicz、Andrew Rabinovich，*SuperPoint: Self-Supervised Interest Point Detection and Description*，CVPR Workshops 2018。本文以 [arXiv v4 原文及附录](https://arxiv.org/abs/1712.07629v4)为主，结合[作者发布的推理实现](https://github.com/magicleap/SuperPointPretrainedNetwork)。

## 1. 出发点：我们需要的不是“看起来很特别”的点

先想想哪些位置适合建立对应关系。

一面没有纹理的白墙不太合适。你从墙上截下一个小块，附近几乎每个位置都长得一样，很难确定它究竟来自哪里。

一条笔直的桌沿也有问题。沿着垂直桌沿的方向，灰度变化很明显；沿着桌沿走，却可能一直相似。我们知道“这里有一条边”，但不容易确定“究竟是边上的哪个点”。

书本的拐角通常更好。向不同方向稍微移动，局部结构都会改变，位置比较容易锁定。不过，“容易锁定”还不够：换个视角后，它仍要能被检测出来；检测出来后，还要能和其他书角区分开。

<figure>
  <a href="/HomepageX/media/superpoint/patch-localization.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/patch-localization.svg" alt="三栏对比白墙、水平桌沿和书角：上排展示原始图块与移动后的图块，下排展示局部匹配误差。白墙误差近乎平坦，桌沿沿水平方向形成低误差谷，角点形成局部唯一的低误差中心。" width="1200" height="914" loading="lazy" /></a>
  <figcaption>自制图 1 · 平坦区域、边缘与角点的定位差异。蓝色实框是原始图块，橙色虚框是移动后的图块；下排是匹配误差形状的定性示意，不是网络输出或实验测量。点击可查看矢量大图。</figcaption>
</figure>

读这张图时，可以把下排的浅色区域理解为“移动到这里，图块仍然很像”。白墙的浅色区域铺成一片，很多位置都能解释同一个图块；桌沿的浅色区域拉成一条谷，沿着它走仍然无法确定位置；角点则把低误差区域收缩到一个局部中心。这是在解释**位置为什么容易或不容易确定**，还没有保证这个角点在另一张图里足够独特。

所以，一个局部特征系统要回答两个相关但不同的问题：

- **检测器：在哪里找？** 输出关键点位置和置信分数，追求重复性、定位准确度，以及有用的空间分布。
- **描述子：怎么认出它？** 把关键点附近的视觉信息编码为向量，让同一个物理位置在不同图像里的描述相近，让不同位置尽量可区分。

随后还需要匹配算法和几何验证。即使两个描述子很像，也可能只是两个重复的窗格；RANSAC 等方法会进一步检查，这些候选匹配是否能共同解释某个几何模型。

理解这个分工很重要：**SuperPoint 输出点和描述子，本身不直接输出两张图之间的最终匹配，也不直接估计相机位姿。** 它是几何视觉系统的特征前端。


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig1-correspondence.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig1-correspondence.webp" alt="原论文 Figure 1：两张图经过共享网络，输出兴趣点及描述子，随后建立跨图对应。" width="873" height="723" loading="lazy" /></a>
  <figcaption>原论文 Figure 1 · 从图像对提取兴趣点和描述子，再建立对应。 <a href="https://arxiv.org/pdf/1712.07629v4#page=1">原文第 1 页</a>。</figcaption>
</figure>

## 2. 第一个难题：网络的训练标签从哪里来？

我们可以让人标注眼睛、鼻尖、手腕，因为这些语义关键点有相对明确的定义。但一张街景里究竟应该标多少个“兴趣点”？窗框交点算，砖缝算不算？一个小斑点是否值得保留？图像缩小以后，答案还一样吗？

更麻烦的是，“好点”本来就与后续任务有关。单张图里看起来非常明显的反光，换个视角可能已经消失；一排重复窗户的角点很稳定，却可能很难匹配。很难通过一次人工标注，把这些要求同时表达出来。

一个直觉方案是：让 Harris、FAST 或 SIFT 给图像打标签，网络照着学。这可以形成可行的监督任务，但目标首先会变成模仿既有检测器，教师的偏好也容易被继承。

SuperPoint 选择从一个更容易控制的世界起步：**真实照片不好标，就先画一些角点位置完全已知的几何图形。** 再想办法把这份初步能力带到真实照片中。

<figure>
  <a href="/HomepageX/media/superpoint/learning-path.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/learning-path.svg" alt="自制训练路线图：合成图形训练 MagicPoint，真实图片经过几何聚合生成伪标签，再联合训练 SuperPoint；部署只需一次前向。" width="1000" height="720" loading="lazy" /></a>
  <figcaption>自制图 2 · 把论文的三个训练阶段与部署阶段分开。点击图片可查看大图。</figcaption>
</figure>

这条路线并非“完全没有监督”。合成图形有程序生成的真值，真实图像有检测器产生的伪标签，图像变换还提供已知的几何对应。它省去的是大规模真实图像兴趣点人工标注。

## 3. 第一步：让 MagicPoint 在一个简单世界里毕业

设想用程序画一个三角形。三个顶点的坐标在绘制时就已经知道，不需要任何人点击鼠标。类似地，可以画四边形、线段、棋盘格、立方体轮廓和星形，自动得到角点或端点标签。

这就是 Synthetic Shapes 的基本想法。通过随机改变几何形状、背景和成像扰动，程序可以持续生成训练样本。训练的任务很朴素：输入一张灰度图，预测哪里有兴趣点。


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig4-synthetic.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig4-synthetic.webp" alt="原论文 Figure 4：左侧展示多种合成形状，中间训练MagicPoint，右侧比较在合成样本中的角点检测结果。" width="1803" height="463" loading="lazy" /></a>
  <figcaption>原论文 Figure 4 · 合成数据预训练，以及与传统角点检测器的定性对比。 <a href="https://arxiv.org/pdf/1712.07629v4#page=4">原文第 4 页</a>。</figcaption>
</figure>

只训练检测分支得到的模型叫 **MagicPoint**。可以把它看成“已经掌握基础几何结构，但还没见过多少真实世界”的初始检测器。

为什么这样的起点有希望？真实图像虽然复杂，许多局部结构仍与边缘交汇、线段端点、明暗边界相关。学会这些模式并非毫无用处；而且合成数据能控制噪声，让网络不至于把每个随机亮斑都当成角点。

但问题很快出现：**在自己画出的世界里学得好，不等于能在真实照片里稳定工作。** 真实纹理、阴影、模糊和复杂背景，与干净的几何形状存在域差异。MagicPoint 有时漏掉了本来很有用的位置；同一个位置换一种投影后，检测响应也可能改变。

到这里，继续增加合成图形是一种选择，却不能保证覆盖真实世界。更自然的下一问是：有没有办法让大量没有标签的真实照片，自己提供训练信号？

<figure>
  <a href="/HomepageX/media/superpoint/paper-fig2-training.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig2-training.webp" alt="SuperPoint 原论文 Figure 2：兴趣点预训练、真实图像自标注，以及共享网络上的检测与描述联合训练。" width="1808" height="491" loading="lazy" /></a>
  <figcaption>原论文 Figure 2 · 三阶段训练总览。裁自 <a href="https://arxiv.org/pdf/1712.07629v4#page=2">DeTone 等，2018，第 2 页</a>。注意中间的伪标签生成和右侧的联合训练是两个环节。</figcaption>
</figure>

## 4. 转折点：没有人工标签，但我们知道图像怎么变了

拿一张真实风格的书桌图片，旋转、拉伸，再把一侧压窄。我们未必知道图里所有兴趣点的位置，却知道每个像素被送去了哪里。**这个由我们主动设定的坐标关系，就是监督的来源。** 先把这件事讲清楚，再回到训练。

### 从一张照片开始：单应变换究竟改变了什么？

把图像想成一张印着照片的平整纸片。你可以在桌面上平移它、旋转它，也可以斜着看它：原本矩形的边框变成四边形，靠近的一边显得宽，远处的一边显得窄。单应变换把这些二维投影统一在一个 $3\times3$ 矩阵 $H$ 中。

<figure>
  <a href="/HomepageX/media/superpoint/homography-photo.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/homography-photo.svg" alt="同一张书桌图像分别进行恒等、平移、旋转、仿射和透视变换，并展示透视变换有效区域。四个彩色标记按同一矩阵移动，网格直线仍为直线，透视变换中的平行线逐渐会聚。" width="1200" height="940" loading="lazy" /></a>
  <figcaption>自制图 3 · 一张生成的写实场景，五种精确的二维矩阵变换。彩点跟踪相同源坐标，灰色是没有源像素可采样的位置；右下给出透视变换的有效区域。</figcaption>
</figure>

先看前三格：平移只是改位置；绕图像中心旋转会让桌沿倾斜，但保留长度和角度。再看左下的仿射变换，它可以压扁、拉斜整张照片，**平行线依然平行**。中下的透视变换更进一步：不同位置的缩放幅度不同，原本平行的线可以会聚。

这些变化仍然有一条共同底线：直线变换后还是直线（不经过投影的奇异位置时）。一般的单应变换不保长度、角度、面积，也不保平行关系；它不是任意揉皱图像的弹性形变，更不会凭空生成被遮挡的内容。

### 为什么是九个数，却只有八个自由度？

普通二维坐标写成 $\mathbf p=(x,y)^\mathsf T$。为了把平移也纳入矩阵乘法，增加一维，写成齐次坐标 $\tilde{\mathbf p}=(x,y,1)^\mathsf T$：

$$
\begin{bmatrix}u\\v\\w\end{bmatrix}
=H\begin{bmatrix}x\\y\\1\end{bmatrix},\qquad
H=\begin{bmatrix}h_{11}&h_{12}&h_{13}\\h_{21}&h_{22}&h_{23}\\h_{31}&h_{32}&h_{33}\end{bmatrix},\qquad
\mathbf p'=\begin{bmatrix}u/w\\v/w\end{bmatrix}.
$$

关键不是“多了一个 1”，而是最后要**除以第三维**。齐次坐标 $(u,v,w)$ 和 $(cu,cv,cw)$ 表示同一个二维点。因此，只要 $c\ne0$，$H$ 和 $cH$ 就代表同一个变换：九个系数减去一个整体尺度，剩八个自由度。通常在 $h_{33}\ne0$ 时把它归一化成 1；合法单应矩阵本身还必须可逆。

把乘法展开，就能看见透视变化从哪里来：

$$
x'=\frac{h_{11}x+h_{12}y+h_{13}}{h_{31}x+h_{32}y+h_{33}},\qquad
y'=\frac{h_{21}x+h_{22}y+h_{23}}{h_{31}x+h_{32}y+h_{33}}.
$$

分子里的常数项负责平移，其余项可以旋转、缩放和错切。如果底行是 $(0,0,1)$，分母恒为 1，这就是仿射变换；当 $h_{31}$ 或 $h_{32}$ 非零，分母随位置改变，不同区域的缩放就不一样了。**透视感藏在这个随位置变化的分母里。**

以图中的 $640\times480$ 像素坐标为例，透视面板使用：

$$
H=\begin{bmatrix}1&0.12&20\\0.04&1&-10\\0.0006&-0.00025&1\end{bmatrix}.
$$

原图中心 $(320,240)$ 乘完矩阵得到 $(368.8,242.8,1.132)$，除以 $1.132$ 后才是新位置 $(325.80,214.49)$。如果忘了这一步，得到的就不是图中那次透视投影。这个数值例子也说明：矩阵系数依赖坐标单位；把像素坐标改成 $[-1,1]$ 的归一化坐标以后，不能直接沿用同一组系数。

### 移动一个点很容易，怎样移动整张图片？

点的前向变换是 $\mathbf p'=\pi(H\tilde{\mathbf p})$，其中 $\pi(u,v,w)=(u/w,v/w)$。但若把每个源像素向前“扔”进目标图，取整后可能多个像素落在同一格，另一些格却没人填。

图像变换通常倒过来做：逐个遍历目标像素，问它在原图里应该从哪里取颜色。

$$
I'(x',y')=I\!\left(\pi\!\left(H^{-1}\begin{bmatrix}x'\\y'\\1\end{bmatrix}\right)\right).
$$

右侧一般不是整数坐标，要用双线性或双三次插值；如果源坐标落在原图外，就是无效区域。上图灰色区域和右下的掩码来自这一步。**点坐标按 $H$ 向前走，生成目标图像时按 $H^{-1}$ 回原图采样**，两者并不矛盾。回到 Homographic Adaptation 时，我们还会用同样的坐标关系把响应图对齐。

### 对任意图像都能做，为什么又说它只适合平面？

这里要分开两件事。**把现有二维图像做一次数学变换**，对书桌照、街景照或人像都能执行，源像素之间的对应完全已知；但**用它模拟相机在真实三维世界里移动后的新照片**，就有条件了。

同一三维平面在两张照片里的投影可由一个 $H$ 联系；在理想针孔成像下，相机绕光心纯旋转也有全图单应关系。若相机发生平移，近处杯子与远处墙面移动幅度不同，就会出现视差；杯子后面还可能露出原图没有的桌面。一张全局矩阵无法同时解释这些变化。

所以，图中被“倾斜”的杯子只是原来的像素被拉伸，绝不是重新拍到了杯子的另一面。这个限制并不妨碍训练：我们主动生成图像对，是为了获得**准确但覆盖范围有限的几何监督**，而不是声称已经模拟了全部三维变化。


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig6-homographies.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig6-homographies.webp" alt="原论文 Figure 6：从中心裁剪开始，依次组合平移、尺度、旋转、对称透视扰动，得到随机单应裁剪。" width="873" height="214" loading="lazy" /></a>
  <figcaption>原论文 Figure 6 · 论文把平移、缩放、平面内旋转与透视扰动组合成随机单应变换。 <a href="https://arxiv.org/pdf/1712.07629v4#page=5">原文第 5 页</a>。</figcaption>
</figure>

这幅原图回答的是“训练时怎样采样合理的变换”。不是任意生成九个数：过大的透视、接近奇异的矩阵或几乎没有重叠的视图，都可能破坏可用的训练内容。

### 一个好检测器应该让点“跟着图像走”

如果原图的书角旋转后去了另一个位置，检测器也应在那里给出响应。用 $W_H$ 表示图像或响应图的几何重采样，希望有：

$$
f(W_H I)\approx W_H f(I).
$$

这叫几何等变性或协变性：先变换再检测，应当与先检测再变换位置相符。要求的是响应跟随结构移动，而不是检测器永远在屏幕上的同一坐标给出高分。

然而 MagicPoint 做不到完美等变。有些角点在原图中反应弱，旋转一点后却被认了出来。既然每次观察有偏差，能不能把同一张图的不同观察合起来？

## 5. Homographic Adaptation：换几个角度，再把意见对齐

这一步可以按四个动作理解：

1. **变换。** 对同一张真实图片采样多组合理的单应变换，得到多张变形图。
2. **检测。** 用同一个初始检测器处理每张图，输出兴趣点响应热力图。
3. **对齐。** 把每张响应图按对应的逆变换映回原图坐标。
4. **聚合。** 对齐后合并响应，再筛选出用来训练的兴趣点伪标签。

最不能省略的是第三步。旋转后的书角已经换了坐标，直接平均不同坐标系的热力图，会把一个本来尖锐的峰摊成模糊的一片。

<figure>
  <a href="/HomepageX/media/superpoint/paper-fig5-adaptation.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig5-adaptation.webp" alt="原论文 Figure 5：对字母 A 施加多组单应变换，分别预测，再逆变换热力图并聚合得到更多稳定兴趣点。" width="1812" height="512" loading="lazy" /></a>
  <figcaption>原论文 Figure 5 · Homographic Adaptation。裁自 <a href="https://arxiv.org/pdf/1712.07629v4#page=5">DeTone 等，2018，第 5 页</a>。图中 Unwarp Heatmaps 正是回到同一坐标系的步骤。</figcaption>
</figure>

<figure>
  <a href="/HomepageX/media/superpoint/align-before-average.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/align-before-average.svg" alt="自制对齐示意：同一个角点经过平移和旋转后位置不同，逆变换后绿色稳定响应重合，红色偶发响应仅出现一次。" width="1000" height="705" loading="lazy" /></a>
  <figcaption>自制图 4 · 为什么必须先对齐再聚合。颜色和点位用于解释机制，不是模型实际输出。</figcaption>
</figure>

把已映回原图的第 $i$ 张响应图记作 $R_i$，论文核心的平均操作就很直观了：

$$
\bar P(\mathbf p)=\frac1N\sum_{i=1}^{N}R_i(\mathbf p).
$$

换句话说，不再只问网络“看这一眼，你觉得哪里是角点”，而是问“在一批相关观察中，哪些位置获得了持续支持”。网络在某些变换下漏检的位置，有机会得到其他视图的补充；只在个别视图出现的偶发响应，则可能被平均削弱。

不过，这不是一个保证正确的多数投票定理。各个预测来自同一个模型，错误可能高度相关。如果它在所有视图下都忽略某种结构，聚合也不会凭空创造新知识；稳定出现的伪角点也可能被保留。

### 从公式到实现，还差“哪里真的看得见”

透视变换后，图像边缘可能被裁掉，还可能出现填充区域。某个原图像素在一次变换里不可见，不能把这次观测当成一次“检测为零”。否则边缘区域会因为可见次数少而系统性吃亏。

更适合实现的有效区域平均，可以写为：

$$
\bar P(\mathbf p)=\frac{\sum_i M_i(\mathbf p)R_i(\mathbf p)}{\sum_i M_i(\mathbf p)},\qquad\sum_i M_i(\mathbf p)>0.
$$

这里 $M_i$ 表示映回原图后的有效区域掩码。这是对论文平均公式的工程化展开；分母为零的位置应忽略。边界插值造成的假响应也值得处理，不能简单把黑色填充边界当作真实轮廓。

### 为什么它不只是普通的数据增强？

普通有监督增强，通常先有标签，再让图像与标签一起变换。这里恰好相反：真实图片最初没有兴趣点标签，先用多次预测与几何对齐**构造一个更好的监督目标**，再用它训练网络。

可以把这个过程理解成“较昂贵的多视图教师，教会一个便宜的单次预测学生”。这是帮助理解的类比，论文并没有因此变成另一个独立的知识蒸馏算法。

论文在伪标签生成中使用 100 次单应变换，并观察到继续增加次数的收益递减；随后还能用训练后的检测器重新生成标签，进行迭代适应。附录还区分了同尺度内与跨尺度聚合：同尺度更强调响应的一致性，而跨尺度时，小结构可能本来就会消失，不能不加区分地要求它在每个尺度都出现。[原文 §5、§6 与附录 C](https://arxiv.org/pdf/1712.07629v4#page=5)


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig7-iterations.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig7-iterations.webp" alt="原论文 Figure 7：三列真实场景在向下迭代的Homographic Adaptation过程中产生更多检测点。" width="866" height="609" loading="lazy" /></a>
  <figcaption>原论文 Figure 7 · 迭代适应在真实图像中逐渐补充检测点。 <a href="https://arxiv.org/pdf/1712.07629v4#page=6">原文第 6 页</a>。</figcaption>
</figure>

看每列从上到下的变化：检测器逐步覆盖了合成预训练阶段没有充分响应的结构。不过“点更多”不是终点，还要用重复性和匹配实验检查这些新增点是否有用。

**多次变换发生在生成训练监督的阶段。** 最终部署的 SuperPoint 可以用一次前向传播提取特征，不需要在每帧上重做这一整套流程。

## 6. 有了监督，怎样把网络做得又快又细？

到这里，才轮到架构发挥作用。我们需要处理整张图，又希望同时得到准确点位和可比较的描述子。如果对每个候选点都单独裁一个图块、重复跑一遍网络，周围的大量计算会重叠。

SuperPoint 用一个共享编码器处理整张灰度图，再分成检测和描述两个分支。这让两个任务复用大部分特征计算。

<figure>
  <a href="/HomepageX/media/superpoint/paper-fig3-network.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig3-network.webp" alt="原论文 Figure 3：共享编码器后分为检测头和描述头；检测头通过 Softmax 和重排恢复分辨率，描述头通过插值和 L2 归一化得到描述子。" width="862" height="420" loading="lazy" /></a>
  <figcaption>原论文 Figure 3 · 两个分支共享编码器。裁自 <a href="https://arxiv.org/pdf/1712.07629v4#page=3">DeTone 等，2018，第 3 页</a>。图中的 Bi-Cubic 是论文方案；作者发布的推理代码改用了双线性插值。</figcaption>
</figure>

编码器经过三次 $2\times2$ 池化，空间尺寸缩小为原来的 1/8。用一张高 480、宽 640 的灰度图举例，主要张量可以这样读；为便于直观理解，表里采用“高 × 宽 × 通道”，省略 batch 维。

| 位置 | 张量尺寸 | 每个位置表达什么 |
| --- | --- | --- |
| 输入 | $480\times640\times1$ | 灰度值 |
| 共享特征 | $60\times80\times128$ | 附近图像结构的特征 |
| 检测头原始输出 | $60\times80\times65$ | 一个 $8\times8$ cell 内的点位分类 |
| 重排后的检测热力图 | $480\times640$ | 每个像素的兴趣点分数 |
| 描述头粗网格 | $60\times80\times256$ | 每个网格位置的描述向量 |
| 最终稀疏特征 | $K$ 个坐标与 $K$ 个 256 维向量 | 用于后续匹配的点和描述子 |

这里的 cell 是输出编码里的空间分组，不是说网络只能看到那 $8\times8$ 个像素。连续卷积使每个输出的感受野覆盖更大的邻域。

### 65 个通道到底在预测什么？

网络缩小了八倍，怎样还能定位到原图像素？关键在于把局部坐标放到通道维里。

对一个 $8\times8$ cell，有 64 个候选像素位置，再加一个“这里没有兴趣点”的类别，也就是 dustbin。检测头因此输出 65 个 logits，在这个 cell 的通道维做 Softmax。

然后去掉 dustbin，把剩余 64 个概率按位置排回 $8\times8$ 区域；把所有 cell 拼起来，就恢复了原图尺寸的响应图。这是一种不需要学习参数的重排，不是通过转置卷积逐层生成高分辨率特征。

<figure>
  <a href="/HomepageX/media/superpoint/cell-decoder.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/cell-decoder.svg" alt="自制 65 通道解码图：64 个通道分别对应 8 乘 8 网格中的像素，另一个通道表示无兴趣点；Softmax 后移除无点通道并重排。" width="1000" height="687" loading="lazy" /></a>
  <figcaption>自制图 5 · 通道中藏着格内坐标。图中行、列和通道使用从 0 开始的编号。</figcaption>
</figure>

举个具体例子：cell 的坐标是“行 $a$、列 $b$”，通道 $k=8r+c$ 代表格内第 $r$ 行、第 $c$ 列，那么它对应原图的 $y=8a+r,\ x=8b+c$。

这也解释了三个容易误会的地方：

- 它不是每隔 8 像素才能检测一个点；格内位置由通道编码，热力图仍是逐像素的。
- 64 个位置在训练时参与同一个分类竞争，并非 64 个独立的二分类。若多个真值落入同一 cell，原论文训练时随机选一个作为目标；这会限制密集角点监督的表达。
- 单一训练标签不等于推理时硬性“每格只能有一个点”。阈值筛选可能留下同格内多个响应，再由 NMS 决定保留哪些。原始重排也没有自动产生亚像素坐标。

### 描述子为什么不用在每个像素都存一份？

描述分支在粗网格上生成 256 维向量。拿到最终关键点后，可以直接在对应的网格位置插值采样，再进行 $\ell_2$ 归一化。

归一化让向量长度为 1，于是点积就是余弦相似度，向量距离主要反映方向差异。对单位向量，还有 $\|\mathbf d-\mathbf d'\|_2^2=2-2\mathbf d^\mathsf T\mathbf d'$，所以按点积找最相似与按欧氏距离找最近，在排序上是一致的。

不必真的把整张图展开成 $480\times640\times256$ 的浮点张量。它单是 float32 数据就约占 300 MiB；粗网格同样的通道数只占约 4.69 MiB，再按 $K$ 个关键点取样更划算。这是基于张量尺寸的内存估算，不是运行时显存实测。

论文描述使用双三次插值，作者公开 demo 使用双线性插值，并说明这是速度与效果的折中。阅读实现时应保留这个区别，不能把某个实现细节当成论文唯一规定。[作者仓库说明](https://github.com/magicleap/SuperPointPretrainedNetwork#additional-notes)

## 7. 最后一个缺口：找到了点，怎么教它认出“同一个”？

现在检测器有了真实图像上的伪标签，描述分支还需要知道：哪两个位置应该相似，哪两个应该不同？仍然用同一个 $H$。把图像 $I$ 与伪标签 $Y$ 一起变换成 $I'$ 与 $Y'$，两张图通过**共享权重的同一个网络**。检测头学习标签中的位置，描述头学习矩阵给出的对应。

### 先把总账拆开：两份检测，一份描述

记检测头的 logits 为 $\mathcal X,\mathcal X'$，粗网格描述子为 $\mathcal D,\mathcal D'$，几何对应指示为 $S$。原论文 Eq. (1) 的总损失是：

$$
\mathcal L=\underbrace{\mathcal L_p(\mathcal X,Y)+\mathcal L_p(\mathcal X',Y')}_{\text{two detector losses}}
+\lambda\underbrace{\mathcal L_d(\mathcal D,\mathcal D',S)}_{\text{descriptor loss}}.
$$

两份检测损失分别检查“原图找得对不对”和“变换图找得对不对”；描述损失才把两张图联系起来，检查相应位置的向量是否接近。它们通过共享编码器共同更新表示，并没有把离散匹配、RANSAC 或最终位姿误差一起纳入优化。

<figure>
  <a href="/HomepageX/media/superpoint/loss-overview.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/loss-overview.svg" alt="联合训练的两路输入共享网络。两个检测头分别用伪标签计算65类交叉熵，两组描述子用H构造的正负对应计算间隔损失，最终合并为总损失。" width="1200" height="720" loading="lazy" /></a>
  <figcaption>自制图 6 · 三项损失的监督来源。蓝色路径学习“点在哪里”，绿色路径学习“哪个位置对应哪个位置”；矩阵提供对应标签，不是待训练参数。</figcaption>
</figure>

### 检测损失：65 个类别竞争一个目标

设粗网格有 $H_c$ 行、$W_c$ 列，总 cell 数 $C=H_cW_c$。一个 cell 的输出 $\mathbf x_{hw}\in\mathbb R^{65}$ 是未归一化分数，第 $k$ 类的概率和损失为：

$$
P_{hw}(k)=\frac{\exp(x_{hw,k})}{\sum_{j=1}^{65}\exp(x_{hw,j})},\qquad
\ell_p(\mathbf x_{hw};y_{hw})=-\log P_{hw}(y_{hw}).
$$

$$
\mathcal L_p(\mathcal X,Y)=\frac1C\sum_{h=1}^{H_c}\sum_{w=1}^{W_c}\ell_p(\mathbf x_{hw};y_{hw}).
$$

这里按论文用 $1,\ldots,65$ 编号，前 64 类表示格内像素，最后一类是 dustbin；第 6 节的解码图用从 0 开始的代码编号，二者只是编号约定不同。有标签点就选对应位置，无标签点就选 dustbin；同一 cell 有多个真值时，原论文随机挑一个作目标。

<figure>
  <a href="/HomepageX/media/superpoint/loss-detector.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/loss-detector.svg" alt="一个8乘8 cell中的目标角点映射到65类中的目标类别。训练把目标概率从0.10提高到0.80，交叉熵从2.303降至0.223；没有标签点的cell以dustbin为目标。" width="1200" height="570" loading="lazy" /></a>
  <figcaption>自制图 7 · 交叉熵只取目标类别的负对数，但 Softmax 让全部类别一起竞争。图中概率是用于代入公式的例子。</figcaption>
</figure>

例如正确格内位置只拿到 $0.10$ 概率，损失为 $-\log0.10\approx2.303$；提高到 $0.80$ 后，损失降为 $0.223$。因为总概率为 1，目标概率上升意味着其他类别的概率总和下降。对没有标签点的 cell，同样的规则会推动 dustbin 获得高概率。

所以“全部输出无点”并不能得到低损失：只要标签里有角点，对应 cell 就会惩罚 dustbin 占据概率。不过伪标签仍有盲区，教师漏标的有用结构会被当成背景；损失只能学习给定监督，不能自动知道漏掉了什么。

### 描述监督：先用几何造出正负配对表

这里不是只拿 NMS 后的关键点来训练。原论文在两张图的**所有粗网格 cell 两两组合**上计算描述损失：一张图有 $C$ 个 cell，就有 $C^2$ 个跨图候选对。

令第一张图的 cell 中心是 $\mathbf p_i$，第二张图的是 $\mathbf q_j$。将前者投影到第二张图，定义：

$$
s_{ij}=\begin{cases}
1,&\left\|\pi(H\tilde{\mathbf p}_i)-\mathbf q_j\right\|_2\le8,\\
0,&\text{otherwise}.
\end{cases}
$$

这里的 8 是输入图像坐标里的像素距离，与八倍下采样的粗网格有关；它不是最终匹配时允许的误差阈值。一个投影点可能距多个网格中心都不超过 8 像素，因此这张训练配对表也不必是严格的一对一匹配。

<figure>
  <a href="/HomepageX/media/superpoint/loss-correspondence.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/loss-correspondence.svg" alt="源网格中心经H投影到目标图，8像素半径内的目标中心标为正对应，其他中心标为负对应。右侧以二乘三配对矩阵展示一个源位置可能有多个正对应。" width="1200" height="610" loading="lazy" /></a>
  <figcaption>自制图 8 · 几何先决定标签，再让网络学习相似度。绿色圆内的中心是正对应，圆外是负对应；小矩阵展示两行源点、三列候选的教学例子。</figcaption>
</figure>

这一步不看当前描述子像不像。即使两个重复窗格外观相同，只要不满足几何距离条件，就可能被标作负对应。这也解释了后文的困难：几何标签可以要求它们不同，但局部纹理未必提供足够信息来做到。

### 描述子损失：该接近的拉近，太相似的负例推开

对归一化描述子 $\mathbf d_i,\mathbf d'_j$，点积 $a_{ij}=\mathbf d_i^\mathsf T\mathbf d'_j$ 是余弦相似度，范围为 $[-1,1]$。原论文 Eq. (6) 对一对向量的约束为：

$$
\ell_d(\mathbf d_i,\mathbf d'_j;s_{ij})=
\lambda_d s_{ij}\max(0,m_p-a_{ij})
+(1-s_{ij})\max(0,a_{ij}-m_n).
$$

这不是两种惩罚同时作用于同一对向量，而是由 $s_{ij}$ 选择分支。正对应只启用第一项，负对应只启用第二项：

- **正对应：** 相似度低于 $m_p$ 就罚，越接近目标越好。论文取 $m_p=1$，意味着希望归一化向量指向同一方向。
- **负对应：** 相似度高于 $m_n$ 才罚，降到阈值以下就停止。论文取 $m_n=0.2$，不要求所有负例都变成相反方向。

<figure>
  <a href="/HomepageX/media/superpoint/loss-hinge.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/loss-hinge.svg" alt="从负1到正1的余弦相似度横轴上，正例未加权损失是1减相似度，负例损失在0.2以前为零、之后线性增加。正例0.7对应未加权0.3；负例0.7对应0.5。" width="1200" height="580" loading="lazy" /></a>
  <figcaption>自制图 9 · 直接按论文间隔损失绘出的两条函数。左图暂不乘正例权重，方便比较形状；绿色箭头与橙色箭头指向各自降低损失的方向。</figcaption>
</figure>

具体代入：正对应若 $a=0.7$，未加权损失是 $1-0.7=0.3$；乘 $\lambda_d=250$ 后，这一对贡献 $75$。负对应若也有 $a=0.7$，损失是 $0.7-0.2=0.5$；若已经只有 $a=0.1$，损失就是零。

为什么正例还要乘 250？两两组合以后，负对应远多于正对应；不加权时，大量负项可能掩盖少量正项。$\lambda_d$ 增强的是**描述任务内部的正例信号**，不是给每个正例复制 250 个样本，也不是最终总损失的任务权重。

### 平均方式和两个系数，为什么都不能省？

原论文 Eq. (5) 对所有配对取平均，再与检测损失相加：

$$
\mathcal L_d=\frac1{C^2}\sum_{i=1}^{C}\sum_{j=1}^{C}\ell_d(\mathbf d_i,\mathbf d'_j;s_{ij}),
\qquad \lambda_d=250,\qquad \lambda=10^{-4}.
$$

检测损失平均的是 $C$ 个 cell；描述损失平均的是 $C^2$ 个候选对。先乘内部的 $\lambda_d$，再平均描述损失，最后才用外部 $\lambda$ 平衡检测和描述。**$\lambda_d$ 平衡正负配对，$\lambda$ 平衡两个任务。** 二者不可互换；改变负例采样、有效区域或归一化方式后，照抄系数也不一定保留相同的梯度比例。[原文 §3.4、§6](https://arxiv.org/pdf/1712.07629v4#page=3)

用最极端的情况检查直觉：如果所有描述子都输出同一个单位向量，所有点积都是 1。正项确实满意，但每个负对应都会产生 $1-0.2=0.8$ 的损失，所以“所有向量一样”不能把描述损失降到零。反过来，只顾把全部向量推远，又会被正项惩罚。训练就在这两类要求之间寻找有区分力、又能跨视图保持一致的表示。

至此，$H$ 在训练中的三份工作就连起来了：变换图像与标签、帮助聚合检测伪标签、生成描述子正负配对。它自身不是网络要预测的答案，却是整个自监督过程的坐标基础。

## 8. 从网络输出到一次真正的图像匹配

训练流程比较长，但实际使用可以收敛成一条短得多的链路。下图上半部分是每张图各自的特征提取，下半部分才把两张图的信息拿到一起，建立并验证对应关系。

<figure>
  <a href="/HomepageX/media/superpoint/inference-pipeline.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/inference-pipeline.svg" alt="SuperPoint 推理链路：两张图分别经过共享权重的网络，检测热力图经阈值、NMS、边界过滤和可选 Top-K 得到关键点；按关键点坐标从粗网格采样并归一化描述子。两组描述子经最近邻匹配形成候选，RANSAC 通过几何模型筛选内点。" width="1440" height="1010" loading="lazy" /></a>
  <figcaption>自制图 10 · 从图像对到几何一致的匹配。蓝色标出网络特征提取，绿色标出描述子采样与后续几何验证；绿色实线和橙色虚线分别示意候选中的内点与外点。图像、热力图、向量颜色及连线均为教学示意，不是模型实测。点击可查看矢量大图。</figcaption>
</figure>

这里有两条数据流需要一起看：检测热力图决定**去哪里采样**，粗网格描述子提供**在那里取出什么向量**。筛选后的关键点坐标因此会送入描述子采样步骤。两张图各自得到点与向量以后，匹配器才比较它们；最后用几何一致性检查候选对应，而不是把“向量相似”直接当作“匹配正确”。

NMS 的作用是避免一个角点周围密密麻麻地留下多个响应。它保留局部更强的响应，抑制邻近点。半径太小，点可能成团；半径太大，临近但不同的有效结构也可能被删掉。关键点数量更多，通常意味着匹配和几何验证也更贵，不代表效果必然更好。

候选匹配可以从最近邻开始，再配合双向一致性等策略。对平面场景可以估计单应矩阵；对一般三维场景，通常要按任务考虑基础矩阵、本质矩阵或带有 3D 地图的 PnP。选错几何模型，前端再好也救不了全部误差。

实际接入时，我会优先核对下面这些细节。它们是工程检查建议，并非论文新增模块：

- **尺寸与坐标。** 原始网络的输出网格与 8 倍下采样有关；输入尺寸不整除 8 时，要明确 padding 或 resize 策略，并把点坐标正确映回原图。
- **灰度与数值范围。** 对照所用权重的预处理，避免把不同的输入约定混在一起。
- **插值坐标约定。** 粗网格、图像坐标、归一化采样坐标及像素中心必须一致；检查所用框架的 `align_corners` 等参数，不要只凭公式看起来相似就判断正确。
- **边界和有效区域。** padding 边缘、单应变换的无效区域，不应该产生可用训练对应或可靠关键点。
- **评价整个链路。** 除了提点耗时，还看匹配内点数、空间覆盖、重投影误差和任务成功率。

尤其要避免把“网络跑一次很快”直接换成“完整 SLAM 系统一定达到某帧率”。两者中间还隔着很多工作。

## 9. 回到实验：到底是哪一部分变好了？

论文的实验值得拆成两个问题来看：点能不能重复找到，以及点和描述子组合起来能不能支持正确的几何估计。

### 先看合成预训练：学会了角点，也学会忽略什么？


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig9-dataset.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig9-dataset.webp" alt="原论文 Figure 9：数据集包括多边形、立方体、网格、线段、星形，以及椭圆和随机图像等无角点负样本。" width="840" height="329" loading="lazy" /></a>
  <figcaption>原论文 Figure 9 · Synthetic Shapes 的完整类别示例。 <a href="https://arxiv.org/pdf/1712.07629v4#page=11">原文第 11 页</a>。</figcaption>
</figure>

合成训练不只是“哪里有角点就画哪里”。附录的数据集中还加入椭圆和随机图像等无角点负样本，让检测器学习何时不应输出角点。它提供了可控的对照环境，却还没有解决真实照片的域差异。


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig10-categories.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig10-categories.webp" alt="原论文 Figure 10：四排柱状图比较不同形状类别下的平均精度与定位误差，并对照加入噪声前后的结果。" width="880" height="547" loading="lazy" /></a>
  <figcaption>原论文 Figure 10 · 按形状类别拆开的平均精度与定位误差，有噪声和无噪声分别展示。 <a href="https://arxiv.org/pdf/1712.07629v4#page=11">原文第 11 页</a>。</figcaption>
</figure>

上半看 AP（越高越好），下半看定位误差（越低越好）。按类别展开的意义是避免总体均值掩盖困难样本：随机纹理会让传统检测器产生很多响应，却并不对应目标角点。


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig11-noise-level.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig11-noise-level.webp" alt="原论文 Figure 11：两张曲线比较MagicPoint与传统方法在逐渐增加噪声时的平均精度和定位误差，下方示意输入从干净形状到随机噪声的变化。" width="884" height="400" loading="lazy" /></a>
  <figcaption>原论文 Figure 11 · 噪声强度变化下的平均精度、定位误差及输入示例。 <a href="https://arxiv.org/pdf/1712.07629v4#page=11">原文第 11 页</a>。</figcaption>
</figure>

图中的横轴并非某台相机的通用噪声标准：作者先在干净图像和带噪图像间插值，再逐渐走向随机噪声。MagicPoint 在相当范围内更稳定，但接近纯噪声时同样失去可检测的几何内容，不能把它读成“越吵也不受影响”。


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig12-noise-type.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig12-noise-type.webp" alt="原论文 Figure 12：上两排展示不同噪声类型的平均精度和定位误差，最下排给出各类扰动样例。" width="884" height="372" loading="lazy" /></a>
  <figcaption>原论文 Figure 12 · 把亮度、高斯噪声、运动模糊、散斑与阴影等扰动分开测试。 <a href="https://arxiv.org/pdf/1712.07629v4#page=11">原文第 11 页</a>。</figcaption>
</figure>

不同扰动影响并不相同，散斑噪声尤其容易让传统检测器困惑。这些图支持“合成训练能学到一定的噪声鲁棒性”，评价对象仍是 Synthetic Shapes，不能替代真实场景验证。

### 聚合次数越多，就一定越好吗？


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig14-adaptation-count.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig14-adaptation-count.webp" alt="原论文 Figure 14：上排改变Homographic Adaptation的单应数量并报告重复性，下排隔离尺度聚合的作用。" width="840" height="506" loading="lazy" /></a>
  <figcaption>原论文 Figure 14 · 单应采样数量与跨尺度聚合的消融。 <a href="https://arxiv.org/pdf/1712.07629v4#page=12">原文第 12 页</a>。</figcaption>
</figure>

这张图直接评估聚合后的检测响应，用于观察多次预测本身的收益；它不是训练完成的模型单次前向时的成绩。上排增加变换数量，重复性先提高，随后收益逐渐变小。论文通常使用 100 次变换，继续到 1000 次并没有带来同比例收益。下排则提醒我们，同尺度的多视图平均和跨尺度聚合承担不同作用；小结构缩小后消失，不应简单按“每个尺度必须同时看见”来处理。

### 先比较 MagicPoint 与 SuperPoint

在论文 Table 3 的 HPatches 检测重复性实验中，图像分辨率为 $240\times320$，每图检测 300 个点，正确对应容差为 3 像素。固定 NMS = 4 后，结果如下。

| 方法 | 光照变化场景的重复性 | 视角变化场景的重复性 |
| --- | ---: | ---: |
| MagicPoint | 0.575 | 0.322 |
| SuperPoint | **0.652** | 0.503 |
| Harris | 0.620 | **0.556** |

这组对比支持了一个具体判断：从合成预训练走到真实图像自训练后，检测重复性有明显改善。但同一张表也告诉我们，在这个视角变化设置下，Harris 仍然更高。不能把论文简化成“学习方法在所有情况下都超过传统方法”。[原文 Table 3](https://arxiv.org/pdf/1712.07629v4#page=7)

### 再看完整特征对几何估计的贡献

论文 Table 4 换了另一套设置：$480\times640$ 的图像，每图最多 1000 个点，先做描述子最近邻匹配，再用 RANSAC 估计单应矩阵。

这里的“正确率”不是正确匹配占所有匹配的比例。评估会比较估计 $H$ 与真值 $H$ 对图像四个角的投影，计算平均角点误差；误差低于阈值 $\varepsilon$ 的图像对才算成功。下表的数字，是成功图像对的比例。

| 方法 | $\varepsilon=1\,\mathrm{px}$ | $\varepsilon=3\,\mathrm{px}$ | $\varepsilon=5\,\mathrm{px}$ |
| --- | ---: | ---: | ---: |
| SuperPoint | 0.310 | **0.684** | **0.829** |
| LIFT | 0.284 | 0.598 | 0.717 |
| SIFT | **0.424** | 0.676 | 0.759 |
| ORB | 0.150 | 0.395 | 0.538 |

数据来自 [原论文 Table 4 和附录 A](https://arxiv.org/pdf/1712.07629v4#page=7)，没有混入第三方复现的成绩。

在 3 像素和 5 像素阈值下，SuperPoint 更高；在 1 像素的严格阈值下，SIFT 更高，而且 3 像素时两者差距很小。

我的理解是，这提醒我们把“形成足够多的可用对应”与“达到非常精细的几何精度”分开。原始 SuperPoint 没有显式的亚像素偏移输出，而局部定位、匹配分布和鲁棒估计都会影响最终误差。**仅凭这张表，不能把差异全部归因于其中一个因素**；但它确实不支持“所有精度门槛下都领先”的说法。

这两张表也不能直接横着拼：分辨率、点数和任务已经改变。今天复现时，还应记录 NMS、匹配策略、数据划分、RANSAC 阈值和随机性，再比较结果。

### 把成功率落回图片：哪些匹配真的成立？


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig8-matching.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig8-matching.webp" alt="原论文 Figure 8：六行图像对展示四种方法的正确连线及匹配点，第四行的大幅平面内旋转是SuperPoint的失败例子。" width="1810" height="1109" loading="lazy" /></a>
  <figcaption>原论文 Figure 8 · HPatches 匹配可视化，依次比较 SuperPoint、LIFT、SIFT 和 ORB。 <a href="https://arxiv.org/pdf/1712.07629v4#page=8">原文第 8 页</a>。</figcaption>
</figure>

绿色连线表示正确对应，绿点是匹配成功的点，红点是错误匹配，蓝点在共同可见区域之外。不能只数“线有多密”，还要看空间覆盖，以及这些点是否足以约束几何。

特别看第四行：SuperPoint 在大幅平面内旋转下表现很差，作者指出这是训练中没有覆盖的极端旋转。前面说“可以用单应变换训练”并不意味着模型自动对全部单应变化鲁棒，**采样了什么变换，仍然决定学到了什么范围。**


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig15-matching-extra.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig15-matching-extra.webp" alt="原论文 Figure 15：更多真实图像对比较SuperPoint、LIFT、SIFT、ORB的匹配分布，包含纹理、光照、视角和大旋转等变化。" width="1808" height="2165" loading="lazy" /></a>
  <figcaption>原论文 Figure 15 · 附录补充的 HPatches 匹配实例；列顺序与颜色含义同 Figure 8。 <a href="https://arxiv.org/pdf/1712.07629v4#page=13">原文第 13 页</a>。</figcaption>
</figure>

补充图让我们看到同一方法在不同内容上的波动。重复纹理、细小结构、可见区域与视角变化都会改变局部特征的价值；一张漂亮的匹配图不能代表整个测试集。

### 附录的另一个边界：感受野足够大吗？


<figure>
  <a href="/HomepageX/media/superpoint/paper-fig13-blob.webp" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/paper-fig13-blob.webp" alt="原论文 Figure 13：随着方块变大，左上角响应保持，而中心响应在超出有效感受范围后明显下降，下方展示三种尺寸的热力图。" width="789" height="721" loading="lazy" /></a>
  <figcaption>原论文 Figure 13 · 额外加入斑点中心标签后，MagicPoint 对不同大小方块的响应。 <a href="https://arxiv.org/pdf/1712.07629v4#page=12">原文第 12 页</a>。</figcaption>
</figure>

这项实验额外训练了 blob-center 监督，不是标准 SuperPoint 天生拥有的功能。方块宽度在 11–43 像素时，中心较可靠；43–71 像素时置信度变低；再大时中心难以检测。角点与“方块中心”的区别很直观：角点附近就能看到边缘交汇，而判断中心必须看到更大范围的完整形状。它把网络感受野的限制变成了可观察的现象。

## 10. 它留下的问题，怎样指向下一步改进？

SuperPoint 的妙处，是让一个没有真实人工角点标注的系统逐步获得可用的特征能力。它的边界，也来自建立这套能力时做出的取舍。

下面的“改进方向”是沿着这些边界作出的分析；涉及后续方法时，会单独给出来源，不把它们写成 SuperPoint 自带的功能。

### 问题一：单应变换教不会所有真实三维变化

二维变换容易生成精确对应，却难以模拟真实视差、遮挡、新区域显露，以及随视角变化的反射。再加更多 $H$，通常只是在同一类假设下看更多样本。

<figure>
  <a href="/HomepageX/media/superpoint/limitation-parallax.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/limitation-parallax.svg" alt="三幅图对比相机平移前、平移后和按墙面对齐后的场景：远处墙面与近处立柱位移不同，墙面对齐后立柱仍有残差，还出现原图中被遮挡的背景区域。" width="1200" height="715" loading="lazy" /></a>
  <figcaption>自制图 11 · 单应对齐的深度边界。墙面位移 −24、立柱位移 −65 像素是人工设定的教学例子；对齐墙面后，立柱仍残留 41 像素偏差。虚框标出原立柱位置，浅绿标出新显露背景，非模型实测。</figcaption>
</figure>

看右图，墙面的网格已经对齐，立柱却还停在虚框左侧。问题不是 $H$ 估得不够精细，而是这两个深度层需要不同的位移。浅绿色部分则提醒我们：即使知道坐标怎么移动，也不能从原图复制出一块原本被遮住的背景。

如果应用真正受这些因素限制，改进方向是引入带深度或相机姿态的真实图像对，并显式考虑可见性和遮挡。代价是数据与监督管线更复杂，还会引入深度或姿态本身的误差。这是从几何假设推导出的方向，不是本文完成过的消融实验。

### 问题二：反复找得到，不代表容易分得清

窗格是最好的反例。一整面楼上，每个窗角都能被稳定检测，但它们的局部外观可能几乎一样。只提高重复性，会把许多“稳定但有歧义”的点一并留下。

<figure>
  <a href="/HomepageX/media/superpoint/limitation-ambiguity.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/limitation-ambiguity.svg" alt="重复窗格示意：图像 A 中一个稳定窗角，连接到图像 B 中三个局部外观相似的候选。下方对比检测重复性与描述子匹配可靠性。" width="1200" height="703" loading="lazy" /></a>
  <figcaption>自制图 12 · 检测稳定与匹配唯一是两回事。绿色圈出查询点，橙色虚线表示多个可能候选；窗格与对应关系均为教学示意，不代表模型输出。</figcaption>
</figure>

蓝色角点可以一次次出现，橙色候选却仍不止一个。重复性回答“找没找到”，而可辨识度还要回答“能不能与其他点区分开”。如果局部纹理完全一样，单纯把检测分数提高，并不会让正确候选自动胜出。

一个自然的改进，是让系统另外估计描述子的可靠性，优先使用既稳定又有辨识度的位置。后续的 [R2D2（2019）](https://arxiv.org/abs/1906.06195)明确区分 repeatability 与 reliability，正好回应了这个问题。这里的启发是：检测分数不应被自动理解成“匹配一定正确的概率”。

### 问题三：孤立地比较两个向量，看不到整体关系

某个窗角究竟对应哪扇窗，仅靠局部描述有时无法消除歧义，但周围其他点的排列可能给出线索。

<figure>
  <a href="/HomepageX/media/superpoint/limitation-context.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/limitation-context.svg" alt="上下文辅助匹配：上排两个候选的局部图块都像查询点；下排加入周围节点后，候选一的关系获得支持，候选二的邻域不同，因而可以重新分配匹配置信度。" width="1200" height="690" loading="lazy" /></a>
  <figcaption>自制图 13 · 让邻域与跨图信息参与判断。橙色邻居表示一种可区分的周围线索。此图只解释上下文的作用，不是 SuperGlue 的具体架构，也不要求邻居距离在视角变化后保持不变。</figcaption>
</figure>

上排只看蓝点附近的小图块，两个候选都说得通。下排把周围线索带进来，候选之间才有了新的区分依据。这里的收益来自多利用了信息，不是人为规定“看起来像这个三角形就一定匹配”；证据不足时，系统仍应允许不匹配。

这把改进重点从提取特征推向了匹配阶段。[SuperGlue（2020）](https://psarlin.com/superglue/)利用图神经网络、注意力与最优传输，将两组局部特征的上下文纳入匹配，并允许拒绝不可匹配的点。它可以接在 SuperPoint 后面，改变的是如何分配对应关系，不能与 SuperPoint 的特征提取混为一谈。

### 问题四：如果第一步根本没有找到点呢？

在低纹理、运动模糊或某些强视角变化区域，两张图可能难以独立检测到同一批稳定点。无论后面的匹配器多强，它都不能直接匹配一个根本没被交给它的候选位置。

<figure>
  <a href="/HomepageX/media/superpoint/limitation-detector.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/limitation-detector.svg" alt="两条匹配路径对照：上排弱纹理区域没有检测点，稀疏匹配器缺少候选；下排通过粗网格特征交互产生对应，再在局部窗口细化坐标。" width="1200" height="756" loading="lazy" /></a>
  <figcaption>自制图 14 · 检测点集决定了稀疏匹配器能看到哪些候选。下排是受 LoFTR 思路启发的粗到细机制示意，不是其真实预测；弱纹理仍需上下文，不保证完全无信息或不可见区域可以匹配。</figcaption>
</figure>

上排虚框里的区域没有进入点集，后面只能在已有蓝点之间挑选。下排先保留粗网格上的特征位置，让两张图的信息参与候选判断，再做局部细化。变化发生在“候选从哪里来”这一层，而不只是给同一批稀疏点换一个更强的相似度函数。

[LoFTR（2021）](https://zju3dv.github.io/loftr/)代表了另一条路线：不先依赖稀疏兴趣点检测，而是在两图特征交互后进行从粗到细的匹配。这回应的是检测瓶颈，不是给 SuperPoint 简单加一个描述子头；计算方式、输出密度和使用成本也随之改变。

### 问题五：像素级输出，还可以更精确吗？

65 类编码恢复的是格内整数像素位置。它很简洁，但没有直接对局部峰值的位置做亚像素回归；粗网格上的描述子又依赖插值。若任务对精度敏感，可以考虑局部坐标细化、可微的亚像素估计，或更高分辨率的特征。

<figure>
  <a href="/HomepageX/media/superpoint/limitation-subpixel.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/superpoint/limitation-subpixel.svg" alt="亚像素定位三栏示意：整数像素点与连续位置存在偏移，单峰局部响应可用于细化峰位置，但两个峰等权平均可能落在中间的低响应区域。" width="1200" height="696" loading="lazy" /></a>
  <figcaption>自制图 15 · 更连续的坐标不自动等于更正确的坐标。示意真值、整数采样与响应曲线均为人工构造，不是 SuperPoint 原生输出或细化实验结果。</figcaption>
</figure>

左图把整数格点和连续位置的差别放大了；中图说明局部响应可以提供更细的位置线索。右图则是反例：两个等强峰的平均坐标恰好落在低谷。只让坐标带上小数，并没有解决“究竟应该选哪个峰”的问题。

不过，改动应该接受严格定位指标的检验。增加分辨率会提高计算和显存开销，对热力图做 soft-argmax 也不自动保证鲁棒性；相邻多个峰可能让平均位置落到两者之间。改进的目标需要说清楚：是更小的定位误差，还是更多可用匹配，还是更好的最终位姿？

## 11. 再走一遍这条思路

现在回头看，SuperPoint 最值得记住的并不是某个孤立的卷积层数，而是它怎样把一个难以直接标注的问题，拆成几个能获得监督的小问题。

真实兴趣点没有清晰、廉价的人工标签，于是先在程序可控的几何图形上学习。合成世界与真实世界存在差异，于是让真实照片在已知变换下接受多次观察，把对齐后的预测作为新的监督。只会找点还不能匹配，于是利用同一份已知几何关系，继续教描述子辨认对应位置。最后，共享计算和轻量解码让这些能力落到整图推理上。

它留给我的一个方法论是：**缺少人工标签时，先找任务中已经知道的约束。** 对这篇论文来说，这个约束就是“图像怎么变了，坐标应该怎样跟着变”。不过，约束能覆盖什么，也决定了模型尚未学会什么；单应关系很有用，却终究不是完整的真实世界。

如果带着这个问题去读下一篇局部特征论文，就更容易看出作者究竟在补哪块短板：改监督、改定位、改描述，还是改匹配。

## 参考资料

1. DeTone, Malisiewicz, Rabinovich. [SuperPoint: Self-Supervised Interest Point Detection and Description，arXiv v4](https://arxiv.org/abs/1712.07629v4)。本文公式、实验设置、图号以此版本为准；另见 [CVPR Workshops 2018 论文页面](https://openaccess.thecvf.com/content_cvpr_2018_workshops/w9/html/DeTone_SuperPoint_Self-Supervised_Interest_CVPR_2018_paper.html)。
2. [Magic Leap 作者推理代码与预训练权重](https://github.com/magicleap/SuperPointPretrainedNetwork)。用于核对部署流程及插值差异；该仓库没有发布完整训练与评测代码。
3. Revaud et al. [R2D2: Repeatable and Reliable Detector and Descriptor](https://arxiv.org/abs/1906.06195)，2019。
4. Sarlin et al. [SuperGlue: Learning Feature Matching with Graph Neural Networks](https://psarlin.com/superglue/)，CVPR 2020。
5. Sun et al. [LoFTR: Detector-Free Local Feature Matching with Transformers](https://zju3dv.github.io/loftr/)，CVPR 2021。
