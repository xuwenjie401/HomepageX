---
title: "现代数据库 09｜完整案例：设计一个复杂空间信息系统"
description: "把地点、区域、路径、物体、事件和历史状态落到统一身份、关系表、空间索引、版本区间、业务图与向量投影；逐步追踪五类查询及跨库一致性。"
date: 2026-09-29
tags: [数据库, 系统设计, 空间信息系统, 多模型]
---

现在设计一个面向园区、楼宇与设施管理的复杂空间信息系统。它要管理地点、区域、路径、物体、事件和历史状态，支持 XYZ 附近查询、属性与语义搜索、以图搜物、过去事件检索和对象关系管理。

我们不从某种传感器或定位算法出发。输入端已经提供需要入库的数据，这里的任务是定义：什么是事实、怎样保存、如何建立索引、一次查询怎样组合结果，以及部分服务延迟或失败时系统如何保持可解释。

前八篇的知识都将在这里出现，但不会因此强制部署八种产品。学习路线可以从[专题目录](/HomepageX/blog/modern-databases/)回看。

## 1. 先固定查询语义，再选择产品

### 1.1 四项会影响整个架构的约定

第一，所有数据属于租户，租户内对象有稳定 `object_id`。名称会重复、位置会变化，编号不随这些变化重建。

第二，XYZ 查询在一个明确的局部米制坐标系 `frame_id` 内执行。不同坐标系的数据必须先通过登记的变换进入共同坐标系，或分别查询后用定义好的共同距离比较。不能把不同楼宇的局部坐标直接混排。

第三，“附近对象”在本案例中默认指对象的**参考点**到查询点的三维欧氏距离。若要查询实体表面或体积的最近距离，应另存相应几何并更换精确距离函数；对象中心离得远，不代表它的边缘也远。

第四，事务性修改与精确空间／时间查询要求确定的结果语义；语义与图片搜索允许 ANN，但需要标识模型版本并测量过滤后的召回。搜索得分不是身份认证或事实真伪判定。

### 1.2 一个用于估算的工作负载

假设初期有 100 万对象、200 万图片、2000 万关系边，事件持续追加。这些是设计输入，非性能实测。两百万个 768 维 float32 图片向量约 6.144 GB，索引连接、ID、过滤字段、副本与内存管理还会增加占用。

如果平均每秒写 10 个事件，一年约 3.15 亿条。于是事件保留策略和时间分区，比当前对象表大小更可能率先决定长期成本。延迟目标应按不同查询分别约定，再用真实分布与并发压测确定容量。

## 2. 数据模型：统一身份，分开保存不同事实

<!-- figure:entities:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/entities.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/entities.svg" alt="六类对象的小表与园区几何对应：地点锚点、区域轮廓、路径折线和物体由事件与历史引用。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 1 · 六类对象的小表与园区几何对应：地点锚点、区域轮廓、路径折线和物体由事件与历史引用。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:entities:end -->

| 表或集合 | 核心字段 | 保存的事实 |
| --- | --- | --- |
| `entity` | tenant_id、object_id、kind、name、description、version、deleted | 所有实体的稳定身份与当前元数据 |
| `coordinate_frame` | tenant_id、frame_id、origin、axes、unit、transform_version | 坐标含义与变换版本 |
| `place` | object_id、frame_id、point | 地点的几何锚点 |
| `region` | object_id、frame_id、footprint、z_min、z_max | 本例采用平面多边形向上拉伸的区域 |
| `route` | object_id、frame_id、line | 有序三维折线路径 |
| `object_current` | object_id、frame_id、position、category、status、source_version | 当前可查物体参考点与常用过滤字段 |
| `object_state` | object_id、state_version、valid_period、system_period、position、status | 双时间历史状态 |
| `event` | event_id、object_id、occurred_at、recorded_at、kind、payload | 不可变事件或有版本的事件更正 |
| `relation_version` | edge_id、source、target、kind、valid_period、system_period | 业务关系及其历史有效性 |
| `asset` | asset_id、object_id、uri、digest、captured_at、source_version | 图片文件引用及来源 |
| `embedding` | object_id、asset_id、source_version、model_version、modality、vector | 可重建的文本或图像检索表示 |
| `outbox` | event_id、object_id、source_version、operation、payload | 已提交、待传播的源变化 |

物体属于某个区域，可以是显式管理关系，也可以由几何计算得出；应分别命名，例如“归管理部门负责”与“空间上位于区域内”，避免把管理归属误当几何真值。地点与区域也可以作为图节点。

图中的每条关联都携带租户语义。外键使用 `(tenant_id, object_id)` 组合，避免一个租户的数据误指到另一个租户。单独检查 object_id 格式不等于租户隔离。

### 2.1 区域和路径的表达能力边界

本例区域是 footprint 多边形与高度区间 `[z_min,z_max)` 的组合，适合楼层或竖直棱柱区域。包含测试要同时检查二维区域与高度；复杂倾斜实体、曲面或地下空洞，需要真实三维几何，不能继续假装这个简化模型足够。

路径的几何折线不等于道路通行图。若要算可通行最短路线，还需要节点连接、方向、通行限制和代价；两条线几何交叉，也可能是立交桥，没有可通行连接。

## 3. 存储组合：一个事实源，几种可替换的查询投影

<!-- figure:architecture:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/architecture.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/architecture.svg" alt="关系、几何、历史和边在权威库内统一提交；对象存储保存图片，外部向量与图是可重建投影。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 2 · 关系、几何、历史和边在权威库内统一提交；对象存储保存图片，外部向量与图是可重建投影。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:architecture:end -->

起步采用 PostgreSQL + PostGIS：关系约束、事务、当前几何、历史区间与事件都在权威数据库中。向量可先用 pgvector；多跳关系先用边表和递归查询。图片本体放对象存储，数据库保存摘要、URI 和关联。

当压测表明需要独立资源时，向量投影可交给 Milvus，复杂关系投影可交给图服务。权威身份、版本和业务写入继续有明确所有者；图服务与向量服务分别维护可重建的访问结构。产品职责可参考 [pgvector](https://github.com/pgvector/pgvector)、[Milvus 概述](https://milvus.io/docs/overview.md)与 [PostGIS 数据管理](https://postgis.net/docs/using_postgis_dbmanagement.html)。

图片上传采用分阶段流程：先写不可变对象并取得摘要，校验存在后提交数据库引用与 Outbox；事务失败产生的孤立文件由延后清理任务回收。对象存储上传和数据库事务没有天然原子提交，不能画一条实线就当问题不存在。

## 4. 一组实际有用途的索引

| 数据 | 索引或组织 | 直接服务的查询 |
| --- | --- | --- |
| 身份与精确属性 | 主键、`(tenant_id, category, status, object_id)` B-tree | 定点读取和高选择性过滤 |
| 当前 XYZ | 按租户／坐标空间组织，n-D GiST | 三维半径候选 |
| 区域与路径 | 几何 GiST，必要时 n-D 配置 | 相交、包含、距离粗筛 |
| 历史状态 | 对象键、有效与系统时间范围 GiST | 历史截面、重叠 |
| 事件 | `(tenant_id, occurred_at, event_id)`、`(tenant_id, object_id, occurred_at)` | 时间窗口、对象事件序列 |
| 关系 | `(tenant_id, source, kind)` 与反向索引 | 出边与入边展开 |
| 描述与标签 | 全文／标签倒排 | 精确词项和布尔检索 |
| 图像与语义表示 | HNSW 或 IVF，或小集合精确扫描 | 向量 top-k |

高频事件按发生时间范围分区，迟到事件允许写入仍保留的旧分区。若已超过保留窗口，要明确归档或拒收／补录政策。历史状态不能只查“当前时间所在分区”，因为很早开始的区间仍可能有效。

下面展示 XYZ 查询的核心表约束与索引。`geometry(PointZ)` 限定有三维坐标；这里不声明全球 SRID，统一以 `frame_id` 区分并约束局部米制坐标。生产环境可登记合适的真实空间参考，但不能冒用经纬度 SRID。

```sql
CREATE TABLE object_current (
  tenant_id BIGINT NOT NULL,
  object_id BIGINT NOT NULL,
  frame_id BIGINT NOT NULL,
  position geometry(PointZ) NOT NULL,
  category TEXT NOT NULL,
  status TEXT NOT NULL,
  source_version BIGINT NOT NULL,
  PRIMARY KEY (tenant_id, object_id),
  FOREIGN KEY (tenant_id, object_id)
    REFERENCES entity(tenant_id, object_id),
  FOREIGN KEY (tenant_id, frame_id)
    REFERENCES coordinate_frame(tenant_id, frame_id)
);
CREATE INDEX current_frame
  ON object_current(tenant_id, frame_id);
CREATE INDEX current_xyz
  ON object_current USING gist(position gist_geometry_ops_nd);
```

这两个索引不保证优化器总会联合使用，也不自动把不同局部空间分离成不同树。租户或坐标空间混杂严重时，可按负载划分分区或设计合适的复合访问方式，查看实际计划再决定。

## 5. 查询一：根据 XYZ 找附近对象

### 5.1 精确半径查询

输入是租户、坐标空间、查询点、半径、权限上下文和属性条件。执行顺序是：筛选租户／空间与有效对象，利用三维包围盒粗筛，计算真实三维距离，按距离及对象编号稳定排序。

```sql
SELECT c.object_id,
       ST_3DDistance(c.position, :q) AS distance_m
FROM object_current c
JOIN entity e USING (tenant_id, object_id)
WHERE c.tenant_id = :tenant AND c.frame_id = :frame
  AND NOT e.deleted AND c.status = 'available'
  AND ST_3DDWithin(c.position, :q, :radius_m)
ORDER BY distance_m, c.object_id;
```

冒号表示应用绑定参数，`:q` 已按同一 frame 构造。权限过滤应通过可靠的查询条件、RLS 或权限连接落实在候选语义中。`ST_3DDWithin` 同时包含索引友好的包围盒检查和距离判断；细节见[函数文档](https://postgis.net/docs/ST_3DDWithin.html)。

### 5.2 没给半径，只要求最近 k 个怎么办？

在同一只读快照中从业务合理半径开始查询；有效候选少于 k 就扩大半径。若半径内已经有 k 个符合所有过滤条件的对象，那么第 k 名距离不超过半径，所有半径外对象都更远，可以停止。若总数不足 k，应在覆盖目标空间后返回实际数量。

同样的保证不适用于“二维 KNN 取 100 个，再三维排序”。[第 4 篇的楼层反例](/HomepageX/blog/modern-databases/04-spatial/)已经说明：真正三维近邻可能根本没进入那 100 个。

## 6. 查询二与三：语义属性搜索、根据图片搜索

<!-- figure:hybrid:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/hybrid.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/hybrid.svg" alt="左侧全局前五经空间过滤为空；右侧在区域候选 6、7、8 中评分得到对象 8 最相似。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 3 · 左侧全局前五经空间过滤为空；右侧在区域候选 6、7、8 中评分得到对象 8 最相似。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:hybrid:end -->

### 6.1 精确属性与自然语言分别处理

“类别等于灭火器”“制造商编号等于 37”是结构化过滤，使用关系或标量索引；“可在雨天使用的便携设备”是语义请求，可使用文本向量，同时用全文倒排保留关键词、型号等字面信号。不能把一个可精确判断的条件完全交给相似度猜测。

若带空间条件后只剩 300 个候选，就读取同版本的候选向量并精确计算；若候选很大，则使用带过滤的 ANN 或逐步扩大检索预算。最后回查主库，验证租户、权限、删除与源版本，并按定义的分数排序。

图中的失败路径是“全局前 5 → 空间过滤 → 空结果”；改进路径是“空间候选全集 → 在集合内求相似结果”。两者的查询语义不同。ANN 的完整性用过滤后的精确真值评估，不能拿全局 Recall@k 代替。

### 6.2 图片查询先解决表示空间与对象聚合

上传图经过固定预处理和图像编码器，得到查询向量。若同时支持文字找图片，应使用经过对齐的多模态编码空间；不能拿不相关模型的文本向量与图像向量直接比较。

每个对象可能有多张图片。向量索引返回的是图片候选，再映射为对象。本例定义对象得分为其可见有效图片中的最大相似度。图片多的对象因此有更多匹配机会，需要在评估中检查数量偏差，必要时限制图片预算或采用其他聚合规则。

图片 top-k 去重后不保证还有 k 个对象；逐步扩大候选，并按对象得分重排。若来自 ANN，扩大到某个固定倍率仍不保证对象级精确 top-k。精确模式可以对过滤后所有有效图片完整评分，再按对象聚合。

### 6.3 混合排序不要随意相加不同单位

米、余弦相似度和文本评分不在同一尺度。可以先把空间距离作为硬约束，再按语义得分排；若确需多路融合，可用经验证的归一化、学习排序或按名次融合。每一种融合都改变业务偏好，应该用查询样本评估，而不是随手指定一个“看着合理”的加权公式。

## 7. 查询四：过去某时间发生了什么？

<!-- figure:history-query:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/history-query.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/history-query.svg" alt="设备在 14:05 事件发生时位于区域内，18:00 已移出；连接当前位置会漏掉真实历史事件。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 4 · 设备在 14:05 事件发生时位于区域内，18:00 已移出；连接当前位置会漏掉真实历史事件。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:history-query:end -->

问“昨天 14 到 15 点发生的事件”，先按 `occurred_at >= :a AND occurred_at < :b` 查事件，按事件编号打破并列。问“截至昨晚我们知道哪些事件”，还需要限制记录／认知时间；若允许更正或撤销事件，需查询当时有效的事件版本，不能只加一个时间上界就忽略更正。

若还问“那些事件发生时在某区域内”，不能把事件连接到 `object_current`。应该用事件发生时间落入历史状态的有效区间，再按指定的系统认知时间选出版本，最后测试**历史位置**与区域几何。区域自身若会调整，也需要选择同一历史语义下的区域版本。

图中设备现在已经移出区域，用当前位置会错过它曾经在区域内发生的事件。时间筛选与空间筛选必须作用在相同语义的状态上。

## 8. 查询五：管理关系，并回答影响链路

新增一条“设备 A 依赖供电柜 B”的关系，先验证两端存在、同租户、关系类型允许，并写入有效区间和源版本。若业务禁止某类环，应采用能协调并发的检查策略；两个并发事务分别插入 A→B、B→A，单独读旧图检查可能都通过。

当前两三跳查询先用带类型与方向索引的边表；复杂可变路径再评估图投影。遍历前固定有效时刻与系统认知时刻，只在该切片上展开边。需要“过去依赖谁”，就不能使用只保存当前关系的投影。

权限继承类查询还要区分“边能否参与推理”与“节点能否向用户展示”，避免错误过滤中间节点改变合法结果。最大深度、环处理、路径数量上限、超时和不完整结果标志，应成为 API 契约的一部分。

## 9. 写入协议：让不同索引最终描述同一个版本

一次对象修改在权威库事务中完成：递增对象版本，更新当前投影，关闭并插入相应历史系统版本，保存关系或媒体关联变更，写入 Outbox。提交后再由消费者更新外部图、全文和向量投影。

向量任务可能很慢，甚至模型服务暂不可用。任务键应包含对象／素材身份、源版本、模型与预处理版本。生成完成后再次核对源版本；如果内容已变化，应废弃旧结果或存入明确的旧版本空间，不能覆盖新版本。

本案例外部投影采用完整快照或可恢复到完整快照的事件，并以源版本拒绝乱序旧消息。删除使用版本墓碑，直到所有相关投影与重建流程都能正确识别它。具体机制回看 [Outbox 与同步篇](/HomepageX/blog/modern-databases/08-multi-model/)。

### 9.1 读到自己刚写的对象，需要什么策略？

普通检索可允许约定延迟，但响应应提供源版本或索引新鲜度。需要读己之写时，客户端携带写入返回的版本令牌；服务等待相关投影覆盖该源版本，或者回退到主库与新内容的精确处理。超时就明确失败或返回约定的降级模式，不能假装已同步。

向量服务自身的强一致读取，只约束它已经接受的数据；不能让尚未从主库传播的内容凭空出现。因此必须跟踪端到端源变更，而非只看外部服务的内部一致性开关。

## 10. 故障、验证与扩展路径

<!-- figure:evolution:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/evolution.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/evolution.svg" alt="表格将三种实际瓶颈对应到向量隔离、图投影、事件归档，并列出各自新增的一致性与恢复成本。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 5 · 表格将三种实际瓶颈对应到向量隔离、图投影、事件归档，并列出各自新增的一致性与恢复成本。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:evolution:end -->

| 场景 | 预期处理 | 验证重点 |
| --- | --- | --- |
| 同 XY、不同楼层 | 用 XYZ 真距离排序 | 三维与二维结果应有预期差别 |
| 区域包围盒命中缺口 | 精确几何排除 | 索引结果不能直接当最终答案 |
| 对象移动后查询旧事件 | 使用历史位置 | 当前位置不能污染历史结果 |
| 删除后收到旧向量结果 | 版本拒绝与主库复核 | 对象不能复活 |
| 向量服务不可用 | 小候选精确回退或明确检索不可用 | 不伪造空结果代表“没有对象” |
| 图投影重建 | 从权威边快照衔接变更流 | 快照与增量无缺口、可去重 |
| 高选择性过滤 | 测量过滤全集内 Recall@k | 不能只测试无过滤 ANN |

当前阶段先验证模型与查询正确性，再用真实数据分布压测。索引维护与备份恢复也要纳入容量预算。备份需覆盖权威库和媒体清单；派生索引可重建，但应测量重建耗时与所需算力。不能只备份向量文件，却丢失模型版本和源对象映射。

当向量计算影响短事务时，先隔离资源或拆出向量投影；当可变路径成为独立瓶颈时，再拆图服务；当事件增长主导存储时，优化分区、归档与分析布局。每一步都有对应证据，也有新增一致性成本。

## 11. 用一条完整请求检查架构是否闭合

“找这个三维位置 20 米内、当前可用、与上传图片相似的对象，并显示昨天下午发生的相关事件及依赖关系。”

先固定租户、frame、当前读取版本和历史查询认知时刻；空间与属性条件产生对象候选；图片向量在候选内搜索并按对象聚合；主库复核身份、权限与版本；事件按发生时间窗口读取；依赖关系按所请求的时间切片展开。当前位置用于当前附近查询，历史事件的位置与关系按明确的历史语义解释，响应不能把两种时间截面混为一谈。

这个系统需要的不是一座“什么都擅长”的索引，而是相互配合的访问路径，以及一个能说明每条结果来自哪个事实版本的协议。关系组织身份与约束，空间缩小几何候选，时间保留变化，图追踪业务关系，向量提供相似排序。至此，九篇文章中的概念共同回答了数据库最重要的工程问题：**针对要问的问题，把数据组织到能正确、可控地回答它的位置。**
