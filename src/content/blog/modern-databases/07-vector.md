---
title: "现代数据库 07｜向量数据库：把语义相似变成近邻检索"
description: "从 embedding 与距离计算出发，解释高维检索、精确近邻、ANN、HNSW 与 IVF；区分 FAISS 和 Milvus，并拆解过滤漏召回、模型升级和评估方法。"
date: 2026-09-29
tags: [数据库, 向量检索, ANN, HNSW]
---

用户想找“适合雨天带出去拍摄的设备”，资料里却只写着“防水相机”。[倒排索引](/HomepageX/blog/modern-databases/03-indexes/)按词项匹配，不一定能连接这两种表述。用户也可能上传图片，想找外观相似的物品；此时连查询词都没有。

向量检索先把对象变成可以比较的数值表示，再寻找相近表示。近邻算法早已存在；AI 表征模型和大规模检索需求让这套能力越来越常用，并非 AI 出现后才发明了向量或最近邻。

## 1. Embedding：把输入映射到一个可比较的空间

<!-- figure:vectors:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/vectors.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/vectors.svg" alt="查询与两个单位向量的夹角、余弦和欧氏距离对照；A 的余弦 0.8，对应距离约 0.632。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 1 · 查询与两个单位向量的夹角、余弦和欧氏距离对照；A 的余弦 0.8，对应距离约 0.632。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:vectors:end -->

embedding，嵌入，是模型把文本、图片等输入映射为固定维数向量的结果：

$$
f_\theta(x)=\mathbf v\in\mathbb R^d.
$$

$x$ 是输入，$\theta$ 是模型参数，$d$ 是维度。向量的某个分量通常不能直接命名为“防水程度”或“红色程度”；训练使整个表示对任务相关差异产生有用的几何关系。

图中二维点只帮助看见“相近”与“分离”，真实模型可能有数百乃至更多维。二维投影也可能扭曲高维邻居关系，不能用投影看起来接近就断言实际检索一定相似。

查询和库中对象必须处在可比较的空间：同模型、同版本、同预处理与归一化约定，或者来自经过联合对齐的不同编码器。任意文本模型向量与任意图片模型向量，即使维数相同，也不能直接做有意义的相似度比较。

## 2. 距离定义了“相似”的具体含义

### 2.1 欧氏距离、点积与余弦

$$
d_2(\mathbf q,\mathbf v)=\sqrt{\sum_{j=1}^{d}(q_j-v_j)^2},
\qquad
s_{\cos}(\mathbf q,\mathbf v)=\frac{\mathbf q^\mathsf T\mathbf v}{\|\mathbf q\|\|\mathbf v\|}.
$$

欧氏距离越小越近，余弦相似度越大越相似。点积则还受向量长度影响。零向量的余弦没有定义，必须在输入和编码流程中处理。

取查询 $\mathbf q=(1,0)$，候选 A 为 $(0.8,0.6)$，B 为 $(0,1)$。三者范数都是 1，余弦分别为 0.8 与 0，欧氏距离约为 0.632 与 1.414，因此 A 更近。

对单位向量：

$$
\|\mathbf q-\mathbf v\|^2=2-2\mathbf q^\mathsf T\mathbf v.
$$

所以此时最小欧氏距离、最大点积与最大余弦有相同排序。**这个等价依赖单位范数，不能无条件套用。** 检索的相似度还只是任务信号：外观像同一型号，不代表是同一个物理对象。

### 2.2 精确 nearest neighbor 是什么基线？

精确 top-k 要对约定候选全集计算距离，取最小的 k 项。最直接扫描工作量为 $O(Nd)$，选择 top-k 还需要额外处理；向量化、GPU、批处理与良好内存布局可以让它非常有竞争力。

一千万个 768 维 float32 向量，仅原始数值约占 $10^7\times768\times4=30.72$ GB，约 28.6 GiB。还没算编号、属性、副本和索引。由此可以估计内存与扫描成本，却不能仅凭字节数推算延迟。

## 3. 为什么高维让传统空间剪枝变弱？

<!-- figure:highdim:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/highdim.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/highdim.svg" alt="二维中心子盒保留 81% 面积，同规则在 100 维只保留约 0.0000266 的体积，数值由公式计算。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 2 · 二维中心子盒保留 81% 面积，同规则在 100 维只保留约 0.0000266 的体积，数值由公式计算。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:highdim:end -->

在三维里可以直观看到一个盒子离查询球很远；高维时，多维约束常常不能同时提供强排除。以立方体里的中心子盒为例，每一维只保留 90% 的长度，体积比例就是 $0.9^d$：二维为 0.81，100 维仅约 0.0000266。这说明低维直觉会迅速失效，并不是一个具体 ANN 索引的性能曲线。

距离集中、数据分布、内在维度和模型训练都会影响实际难度。KD-tree 在低维有用，但高维可能触达大量分支；标量 B-tree 也无法把所有方向的语义距离压进一个全序。参见 [SciPy 的高维 KD-tree 说明](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.KDTree.html)。

关系数据库仍可以保存向量，并安装专门索引。困难属于高维访问方式，而不是 SQL 语言不能表达距离。

## 4. ANN：以有限搜索换取更低成本

ANN 是 approximate nearest neighbor，近似最近邻。算法只探索一部分候选，或压缩距离表示，因此可能漏掉真实 top-k 中的对象。它追求速度、内存和召回之间的合适折中，不是随机挑几个结果。

最基本的索引召回指标是：

$$
\mathrm{Recall@}k=\frac{|A_k\cap G_k|}{k}.
$$

$G_k$ 是同一候选全集、同一距离与同一并列策略下的精确 top-k，$A_k$ 是近似结果。若真实前五为 `{1,2,3,4,5}`，近似返回 `{1,2,3,8,9}`，召回为 0.6。这不等于“结果在业务上有 60% 正确”：索引复现向量排序，与向量排序能否满足人的需求，是两个指标。

## 5. HNSW：上层跨大步，底层保留多个探索方向

<!-- figure:hnsw:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/hnsw.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/hnsw.svg" alt="HNSW 示意图中上层只含 A、C、F，下降到完整底层后保留多个候选方向继续搜索。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 3 · HNSW 示意图中上层只含 A、C、F，下降到完整底层后保留多个候选方向继续搜索。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:hnsw:end -->

### 5.1 多层近邻图怎样帮助搜索？

HNSW 把向量作为节点，把选出的近邻作为边；越高层节点越稀疏。搜索从高层入口开始，朝更近节点移动，找到合适入口后降一层；在底层以候选队列保留多个方向，避免只走一条贪心路径。

这里的图边是**索引内部的距离导航关系**，不是第 5 篇的业务知识关系。一个索引节点连到“相似图片”，不表示两个物体现实中“相邻”“属于”或“依赖”。原理来源为 [Malkov 与 Yashunin 的 HNSW 论文 v4](https://arxiv.org/abs/1603.09320v4)。

### 5.2 插入和查询分别付出什么？

插入时选择随机层高，搜索连接候选，再用邻居选择策略建立有限连接；已有邻居列表也可能被裁剪。保留方向较多样的边有利于导航，不是简单“只连距离最近的几个”就解释了全部构造。

常见参数中，`M` 控制连接规模相关预算，`efConstruction` 控制构建时探索宽度，`efSearch` 控制查询时保留的搜索候选规模。更大预算通常有助于召回，却增加构建、内存或查询成本；各实现的参数名和限制需核对。

HNSW 不能保证每个数据集都精确，也不能宣称最坏情况恒为对数复杂度。删除、频繁更新、内存容量与分布变化，会影响结构质量和维护策略。

## 6. IVF：先找粗分区，再搜分区里的细节

<!-- figure:ivf:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/ivf.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/ivf.svg" alt="查询点位于左侧粗中心分区边缘，最近数据点位于第二个分区；只探测一个倒排列表会漏召回。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 4 · 查询点位于左侧粗中心分区边缘，最近数据点位于第二个分区；只探测一个倒排列表会漏召回。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:ivf:end -->

IVF 把向量按粗量化中心分到倒排列表。构建时学习 `nlist` 个中心，把每个向量分配到一个列表；查询先比较中心，再选 `nprobe` 个列表，在其中计算距离。

若有一百万向量、1000 个列表、数据均匀，探测 10 个列表约检查一万向量，加上粗中心比较。真实列表可能极不均匀，不能把这个估计当固定上限。

图中查询点靠近两个分区边界，真正最近点位于第二个列表。只探测一个列表会漏掉它；增大 `nprobe` 可以扩大覆盖。IVF-Flat 在访问的列表内保留完整向量计算距离，近似主要来自未访问列表；IVF-PQ 还引入乘积量化压缩，从而增加距离近似误差。

若 IVF-Flat 探测所有列表，并在相同过滤、距离与候选集合下完整比较，就回到精确搜索。训练样本偏离线上分布时，应监控列表偏斜与召回，必要时重训重建。具体类型见 [FAISS 索引文档](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes)。

## 7. FAISS 与 Milvus：算法库和数据库服务是不同层

FAISS 提供高效向量索引、搜索和相关计算，是构建检索能力的库。应用仍需要解决对象元数据、并发更新、持久化流程、权限、服务接口和运维等问题。能把索引写成文件，不等于自动拥有完整数据库语义。

Milvus 是围绕向量与标量数据管理的数据库系统，提供集合、索引、查询与系统层能力；部署形式、支持的索引和一致性选项要按版本选择。PostgreSQL 加 pgvector 也是另一种路线，适合希望沿用关系数据与事务边界的系统。不能仅凭名称断言哪种在你的规模下更快。参阅 [Milvus 文档](https://milvus.io/docs/overview.md)与 [pgvector 项目说明](https://github.com/pgvector/pgvector)。

## 8. 过滤为什么可能把 top-k 变成空结果？

<!-- figure:filter:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/filter.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/filter.svg" alt="全局前五对象都不满足过滤而得到空结果；正确过滤集合仍含对象 6、7、8，可在其中排序。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 5 · 全局前五对象都不满足过滤而得到空结果；正确过滤集合仍含对象 6、7、8，可在其中排序。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:filter:end -->

假设查询只允许返回园区 A 的可用对象。全局 ANN 先取前 5 个，恰好都来自园区 B，后过滤得到空集；但园区 A 明明有很多相关物品。先取 top-k 再过滤，与在过滤后的集合中求 top-k，不是同一个运算。

选择包括：先过滤再精确算小候选集；让索引搜索时利用过滤条件；或者逐步扩展 ANN 候选再过滤。过滤可能改变图的可导航性，有的实现允许经过不满足条件的节点但不返回它们，不能简单把“不符合条件的节点全部禁止访问”当作正确算法。[Milvus 过滤搜索](https://milvus.io/docs/filtered-search.md)区分了不同过滤执行方式。

候选重排只会改变已召回候选的顺序，不能补回没有进入候选集的真实邻居。过采样能改善经验召回，但固定倍率不是完整性证明。强租户隔离与权限必须在输出前可靠验证；索引未及时更新的删除状态也需要检查。

## 9. 怎样做有意义的评估与升级？

<!-- figure:recall:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/recall.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/recall.svg" alt="精确前五与近似前五重合对象 1、2、3，按集合交集计算 Recall@5 为 0.6。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 6 · 精确前五与近似前五重合对象 1、2、3，按集合交集计算 Recall@5 为 0.6。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:recall:end -->

先固定代表性数据、查询集、嵌入版本、过滤分布和精确基线；再扫查询预算，记录 Recall@k、p50／p95 延迟、吞吐、内存、构建时间和更新可见延迟。冷热缓存、并发度、硬件与返回规模不同的数字不能直接比较。图中集合示例只计算召回，没有伪造性能基准。

模型升级时，新旧向量空间不应混算。可新建版本化索引，后台重算，双读比较，验证后切换；对象编号、源内容版本、模型版本和预处理版本都要能追踪。若对象文本已经更新但向量仍旧，系统应知道这一事实，而非悄悄拼成“最新答案”。

练习：精确前 10 中有 7 个被 ANN 找到，随后业务过滤删除 4 个，最终返回 6 个。这些数字分别属于索引召回和过滤后结果量；要评估过滤场景，应重新在同一过滤全集内建立真值，不能沿用全局前 10。

下一篇把这些能力装进工程架构：[多模型数据库：组合查询能力，也管理一致性成本](/HomepageX/blog/modern-databases/08-multi-model/)。
