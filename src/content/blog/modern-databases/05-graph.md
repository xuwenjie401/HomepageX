---
title: "现代数据库 05｜图数据库：当问题变成沿着关系继续找"
description: "用设备依赖与故障影响分析理解节点、边、属性、邻接表和遍历；对照关系表连接，解释图数据库、知识图谱以及路径爆炸的边界。"
date: 2026-09-29
tags: [数据库, 图数据库, 图遍历, 知识图谱]
---

设备清单现在多了关系：设备依赖供电柜，供电柜连接配电站，另一些设备又依赖前一台设备。问题从“设备 7 的名称是什么”变成“供电柜停机，会影响哪些下游设备，影响经过什么链路”。

[空间数据库](/HomepageX/blog/modern-databases/04-spatial/)关心几何距离；这里的“相邻”由明确的业务关系决定，两个距离很远的对象，也可能只有一条关系之隔。图数据库围绕这种邻接与多跳查询组织数据。

## 1. 节点、边、属性：不要先把所有东西画成圆

<!-- figure:graph:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/graph.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/graph.svg" alt="设备 A 依赖供电柜 B，B 依赖配电站 C；节点功率与边有效时间分别是不同对象的属性。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 1 · 设备 A 依赖供电柜 B，B 依赖配电站 C；节点功率与边有效时间分别是不同对象的属性。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:graph:end -->

node，节点，表示有身份的实体，例如设备 A。edge，边，表示两个实体之间的一次有类型、可有方向的关系，例如 `A DEPENDS_ON B`。property，属性，保存实体或关系上的数据，例如设备类型、额定功率、依赖开始时间。

图中约定箭头为“依赖方 → 被依赖方”。问 A 依赖谁，要顺箭头走；问 B 坏了影响谁，要沿入边反向找。没有明确方向语义，图画得再漂亮也会查反。

属性图通常允许边拥有属性，同一对节点也可能有多条不同关系。是否允许重复边、如何标识边、哪些属性必须存在，应由模型约束决定。可对照 [Neo4j 图概念](https://neo4j.com/docs/getting-started/appendix/graphdb-concepts/)。

## 2. 图并没有发明关系：关系表本来也能存边

### 2.1 同一张图，两种表示

<!-- figure:join-graph:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/join-graph.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/join-graph.svg" alt="四条 source-target 边记录与菱形邻接图表示同一关系，可通过边表索引或图邻接访问遍历。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 2 · 四条 source-target 边记录与菱形邻接图表示同一关系，可通过边表索引或图邻接访问遍历。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:join-graph:end -->

完全可以用关系表：

```sql
CREATE TABLE edges (
  edge_id INTEGER PRIMARY KEY,
  source_id INTEGER NOT NULL REFERENCES items(item_id),
  target_id INTEGER NOT NULL REFERENCES items(item_id),
  kind TEXT NOT NULL
);
CREATE INDEX edges_from ON edges(source_id, kind, target_id);
CREATE INDEX edges_to ON edges(target_id, kind, source_id);
```

按 `source_id` 取邻居，就是一次带索引的选择；两跳可以自连接两次。图数据库的价值不能建立在“关系数据库每跳都必须扫描整张表”这个错误前提上。

常见图存储会让节点更直接地定位自己的邻接边，再走到邻居；但具体物理实现可能是指针、记录编号、键值结构或压缩邻接块。**“图模型”不保证每个产品都采用同一种存储，也不保证一次跳转始终只需一次廉价内存访问。**

### 2.2 固定两跳与可变深度是不同需求

```sql
SELECT DISTINCT e2.target_id
FROM edges e1
JOIN edges e2 ON e2.source_id = e1.target_id
WHERE e1.source_id = 7
  AND e1.kind = 'depends_on'
  AND e2.kind = 'depends_on';
```

固定两跳的 SQL 很清楚。深度由数据决定时，可以使用递归 CTE，或使用图查询语言表达路径。递归 SQL 并非数据库外的补丁，PostgreSQL 的 [WITH 文档](https://www.postgresql.org/docs/18/queries-with.html)包含递归、遍历顺序与循环处理。

一种只求可达节点集合的写法如下；`UNION` 对单列节点编号去重，使循环不会无限重复加入同一节点：

```sql
WITH RECURSIVE reachable(node_id) AS (
  SELECT 7
  UNION
  SELECT e.target_id
  FROM reachable r
  JOIN edges e ON e.source_id = r.node_id
  WHERE e.kind = 'depends_on'
)
SELECT node_id FROM reachable WHERE node_id <> 7;
```

这不返回每条路径，也不计算最短距离。若递归行中加入不断变化的 `depth`，同一节点不同深度便不再是重复行，不能继续依赖这个去重方式防环。

## 3. 遍历：把 frontier 与 visited 分开

### 3.1 一次广度优先搜索的中间对象

<!-- figure:traversal:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/traversal.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/traversal.svg" alt="A 的第一层邻居为 B、C，第二层新节点为 D、E；重复到达 D 与返回 A 的环被 visited 控制。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 3 · A 的第一层邻居为 B、C，第二层新节点为 D、E；重复到达 D 与返回 A 的环被 visited 控制。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:traversal:end -->

graph traversal，图遍历，是按照邻接关系访问图。BFS 用队列按层扩展：初始 frontier 是起点 A；第一轮发现 B、C；第二轮发现 D、E。若 D 同时从 B 和 C 到达，记录一次访问即可；如果 D 又指回 A，visited 集合阻止无限循环。

```text
visited = {start}
queue = [(start, 0)]
while queue 非空:
    u, depth = 弹出队首
    if depth == max_depth: continue
    for v in 符合关系类型的邻居(u):
        if v 不在 visited:
            visited.add(v)
            记录 v 的前驱 u 和距离 depth + 1
            queue.append((v, depth + 1))
```

单位边权下，BFS 首次到达节点时得到最少跳数；它不求最短欧氏距离，也不适用于任意权重的最小总代价。非负边权可考虑 Dijkstra；需要的算法取决于“短”的业务定义。

DFS 则沿一条分支深入，再回溯；适合某些连通、循环和结构分析，但通常不能把第一次到达当作最短路径。遍历的结果可以是节点集合、边集合或路径集合，必须先约定。

### 3.2 找到一个节点和枚举所有路径，成本差别巨大

在邻接表示下，访问一个可达子图的基本工作量约为 $O(V_r+E_r)$，这里 $V_r$、$E_r$ 是实际触达的节点和边。这个模型不包含远程存储访问、属性读取、排序和输出巨大路径集合的全部成本。

若平均每节点扩展 $b$ 个新邻居，深度 $h$ 的树形展开近似：

$$
1+b+b^2+\cdots+b^h.
$$

$b=10$、$h=4$ 就有 11111 个位置。真实图会有重复节点，可达集合去重能减轻工作；但“所有符合条件的路径”仍可能指数级增多。

## 4. 图数据库也会碰到超级节点

<!-- figure:hubs:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/hubs.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/hubs.svg" alt="左侧中心节点连接大量邻居，右侧列出分支数十时四跳展开的节点数，说明一跳与多跳都可能昂贵。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 4 · 左侧中心节点连接大量邻居，右侧列出分支数十时四跳展开的节点数，说明一跳与多跳都可能昂贵。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:hubs:end -->

如果某个总配电站有一百万条入边，“只查一跳”也要考虑一百万个邻居。高出度节点、热门关系、跨分区边和大结果集，都会让局部遍历失去优势。

改进先从语义开始：限定边类型、时间有效性、最大深度、返回数量；明确是否允许重复节点或边；尽早利用有效的属性条件。不能为了加速偷偷删掉问题需要的路径。必要时预计算可达摘要或分析投影，同时承担刷新成本。

因此，图数据库适合的问题常包含**起点选择性高、关系重要、路径解释有价值**等特征，例如故障影响、权限继承、欺诈团伙和知识关联。全表聚合、简单固定连接或大量短事务，未必需要专门拆成图服务。

## 5. 知识图谱：图结构之外，还要有可解释的语义

<!-- figure:knowledge:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/knowledge.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/knowledge.svg" alt="设备、位置、类型和功率的三元组示例；结合显式子类规则可推导设备 A 属于设备类型。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 5 · 设备、位置、类型和功率的三元组示例；结合显式子类规则可推导设备 A 属于设备类型。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:knowledge:end -->

knowledge graph，知识图谱，强调实体、关系与概念的语义组织，常需要身份对齐、类型体系、来源与可信度。它是一种知识建模与应用方式，不是某个专用数据库产品的同义词。

RDF 用“主语—谓语—宾语”三元组表示断言；主语可为 IRI 或空白节点，谓语为 IRI，宾语还可为字面值。例如“设备 A—位于—楼宇 B”“设备 A—额定功率—5 kW”。属性图与 RDF 都能表达关系，但标识、属性与语义机制不同，不能逐字机械映射。[RDF 1.1 概念规范](https://www.w3.org/TR/rdf11-concepts/)给出正式数据模型。

若知识规则声明“泵属于设备”，可以让系统在适当推理规则下回答“有哪些设备”。没有规则与推理配置，画一条 `is_a` 边不会自动得到完整推理。不同资料把两个同名设施当成同一实体，也不是图索引能够自行纠正的错误。

## 6. 选择图技术前，先写出路径问题

| 维度 | 关系表与连接 | 图查询与遍历 |
| --- | --- | --- |
| 固定层数、强表约束 | 表达成熟，可用索引优化 | 同样可表达，未必更快 |
| 深度变化、路径模式复杂 | 递归 SQL 可行，需认真处理环与路径 | 查询语言通常更贴近问题 |
| 全局统计 | 擅长分组与集合运算 | 可能需要图分析或额外投影 |
| 主要成本 | 访问路径、连接基数、中间结果 | 触达边数、属性读取、路径数量 |

练习：A→B、A→C、B→D、C→D。问“可达哪些节点”，D 出现一次；问“从 A 到 D 的所有路径”，有两条。换了结果语义，去重策略和成本都变了。

下一篇让关系与属性进入时间轴：[时间数据库：保存变化，才能回答过去](/HomepageX/blog/modern-databases/06-temporal/)。
