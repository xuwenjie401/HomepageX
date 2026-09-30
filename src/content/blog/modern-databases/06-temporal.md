---
title: "现代数据库 06｜时间数据库：保存变化，才能回答过去"
description: "从覆盖更新丢失历史的问题出发，理解时间戳、事件、版本、有效时间和系统时间；用双时间轴、区间查询与事件回放组织动态系统。"
date: 2026-09-29
tags: [数据库, 时间数据库, 历史版本, 事件]
---

昨天设备 A 在仓库，今天在维修区。普通 `UPDATE` 可以准确保存当前位置，却会让“昨天 15 点它在哪里”失去依据。[前几篇](/HomepageX/blog/modern-databases/)建立的关系、空间和图结构，若只保存当前状态，都面对这个问题。

时间数据库关心事实何时有效、系统何时知道，以及怎样查询过去。它可以由专门产品提供，也可以建立在关系表、范围类型和版本管理之上。给表加一个更新时间，只回答“最后改过一次是什么时候”，并没有保存之前的内容。

## 1. 时间戳、事件、状态和历史不是同一件事

<!-- figure:timeline:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/timeline.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/timeline.svg" alt="10 点进入维修区、12 点回仓库是两个点事件，维修区与仓库状态分别覆盖连续时间区间。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 1 · 10 点进入维修区、12 点回仓库是两个点事件，维修区与仓库状态分别覆盖连续时间区间。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:timeline:end -->

timestamp，时间戳，表示一个时间点；event，事件，记录发生了什么，例如“设备进入维修区”；state，状态，表示某时刻成立的属性；history，历史，是这些状态或事件随时间演化的记录。versioning，版本化，则是保留多个版本并定义其身份与有效范围的机制。

事件通常由 `event_id` 标识，而不是只用时间戳：同一微秒可以发生多件事，客户端时钟也可能偏移。要稳定排序，可额外使用源序列号、服务端提交顺序或约定的打破并列规则。不同来源的序列号不能直接当全局时间比较。

设备进入维修区是事件；“设备处于维修区”是一个状态区间。收到传感数据是另一个事件；它描述的测量时间可能比收到时间早。先区分这些意义，才能正确设计索引。

## 2. 用半开区间表达一个状态持续多久

### 2.1 为什么通常选择左闭右开？

设状态在 $a$ 开始、在 $b$ 被替代，记作 $[a,b)$。设备 10 点进入维修区、12 点转回仓库，则 12 点恰好只属于后一个状态，不会同时落入两个相邻版本。

<!-- figure:intervals:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/intervals.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/intervals.svg" alt="左闭右开状态区间在 12 点相接却不重叠，而请求区间 11 到 13 与两个状态均相交。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 2 · 左闭右开状态区间在 12 点相接却不重叠，而请求区间 11 到 13 与两个状态均相交。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:intervals:end -->

查询某时刻 $t$ 的状态，需要：

$$
a\le t<b.
$$

查询状态区间与请求区间 $[c,d)$ 是否重叠，需要：

$$
a<d\quad\land\quad c<b.
$$

例如 `[10,12)` 与 `[12,14)` 不重叠；`[10,13)` 与 `[12,14)` 重叠。`BETWEEN` 通常两端都包含，用它代替半开区间判断，会在边界上重复计数。

### 2.2 版本表需要约束，而不只是多存几行

一种单有效时间模型是 `object_state(object_id, version, valid_from, valid_to, location, status)`。对每个对象，应明确是否要求时间连续，以及是否允许版本重叠。状态缺测时应表达未知或空档，不要伪造连续轨迹。

PostgreSQL 可以使用 `tstzrange` 保存区间，以排斥约束禁止同一对象出现重叠的状态：

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE TABLE object_state (
  object_id BIGINT NOT NULL,
  version BIGINT NOT NULL,
  valid_period TSTZRANGE NOT NULL,
  status TEXT NOT NULL,
  PRIMARY KEY (object_id, version),
  CHECK (NOT isempty(valid_period)),
  EXCLUDE USING gist (object_id WITH =, valid_period WITH &&)
);
```

写入端还必须统一使用 `[)` 边界并处理开端、末端与连续性要求。这里的约束防重叠，不保证无空档。查询可以使用 `valid_period @> :time` 或 `valid_period && :window`。范围索引和排斥约束见 [PostgreSQL 范围类型](https://www.postgresql.org/docs/18/rangetypes.html)。

## 3. 两条时间轴：事情发生的时间，与数据库知道的时间

### 3.1 一条迟到的更正为什么需要两个答案？

<!-- figure:bitemporal:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/bitemporal.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/bitemporal.svg" alt="二维时间矩形保存旧认知与更正后认知：相同有效时刻 10:30，在 12:30 和 14:30 得到不同答案。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 3 · 二维时间矩形保存旧认知与更正后认知：相同有效时刻 10:30，在 12:30 和 14:30 得到不同答案。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:bitemporal:end -->

我们在 12 点记下“设备从 10 点起位于维修区”。14 点收到更正：“实际从 11 点起才进入维修区，10 到 11 点仍在仓库”。

现在有两个合理问题：“按目前知识，10:30 它在哪？”答案是仓库；“12:30 的系统当时认为 10:30 它在哪？”答案是维修区。如果只改原历史行，第二个答案就丢了。

valid time，有效时间，描述事实在业务世界何时成立；system time／transaction time，系统或事务时间，描述系统在何段时间持有这个版本。二者组合就是 bitemporal，双时间建模。

图中的一条记录不是时间线上的一个点，而是二维平面上的矩形：横向覆盖业务有效期，纵向覆盖系统认可期。查一个“有效时刻 + 知识时刻”，就是找同时覆盖两条坐标的版本。

### 3.2 更正时怎样保存旧认知？

14 点更正时，关闭旧记录的系统有效期，保留其内容；再插入新认知：仓库 `[10,11)`，维修区 `[11,∞)`，系统有效期均从 14 点开始。这些修改应在同一事务中完成。

概念查询为：

```sql
SELECT location
FROM object_state_bitemporal
WHERE object_id = :id
  AND valid_from <= :valid_at AND :valid_at < valid_to
  AND system_from <= :known_at AND :known_at < system_to;
```

本例用有明确排序的无穷远表示开放末端；若采用 `NULL`，应显式处理，不能把上述比较原样照搬。系统时间通常应由权威服务或数据库管理，不能让不可信客户端随意回填。

双时间表的唯一性也更复杂：同一对象不能在两条时间维度上同时重叠，但允许两个系统认知版本覆盖同一业务时段。不能直接复制前面单时间表的“有效时间永不重叠”约束。SQL Server 的系统版本表主要自动维护系统时间历史；业务有效时间需要按应用语义另行设计。参见[官方时间表概述](https://learn.microsoft.com/en-us/sql/relational-databases/tables/temporal/overview?view=sql-server-ver17)。

## 4. 事件日志与状态版本：该保存哪一种？

<!-- figure:replay:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/replay.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/replay.svg" alt="库存从五经入库二、出库一得到六；库存七的快照允许只回放后一个事件，重复入库则出错。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 4 · 库存从五经入库二、出库一得到六；库存七的快照允许只回放后一个事件，重复入库则出错。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:replay:end -->

状态版本直接保存“这一段时间的属性”，查历史容易；事件日志保存变化原因，例如“入库”“移动”“维修完成”。事件溯源则进一步把事件序列作为权威依据，通过确定性的处理逻辑推导状态。

用 $S_0$ 表示初始状态，$e_i$ 表示事件，$f$ 表示状态转换：

$$
S_n=f(f(\cdots f(S_0,e_1),e_2)\cdots,e_n).
$$

例如库存 5，依次入库 2、出库 1，最终 6。若把“入库 2”重复处理一次就会变成 8，所以必须考虑事件身份与幂等处理。若乱序会改变含义，应按每对象序列检测缺口，不能只按到达顺序随意折叠。

从零回放全部事件会慢，因此可定期保存快照，再回放后续事件。快照要记录已覆盖的序列位置和转换逻辑版本。业务规则改变后，用新代码回放旧事件未必得到旧结果；重放策略必须版本化。

事件溯源、审计日志和 CDC 不是同义词。CDC 记录数据库变化；业务事件表达业务意义；审计关注谁在何时做了什么。可以协作，却不能自动互相替代。

## 5. temporal query：除了“那一刻是什么”还会问什么？

| 请求 | 需要的数据 | 候选访问方式 |
| --- | --- | --- |
| 对象 A 在某时刻的状态 | 版本区间 | 对象键 + 区间包含；或开始时间索引后检查结束时间 |
| 某小时发生的事件 | 独立事件与发生时间 | 时间范围索引、时间分区 |
| 哪些状态与停机窗口重叠 | 区间 | 范围索引与重叠谓词 |
| 当前认知与昨天认知有何差异 | 双时间版本 | 固定两次系统时间切片后比较 |
| 当时位于区域内的设备 | 历史几何 + 有效时间 | 时间与空间共同筛选、精查 |

索引 `(object_id, valid_from)` 有利于单对象回看，但不能仅因 `valid_from <= t` 就认定版本有效，仍需检查 `valid_to`，尤其在有空档、重叠或迟到修正时。两个时间边界并不自动变成一个紧凑的 B-tree 区间。

## 6. 时间序列与历史版本，各自优化什么？

<!-- figure:retention:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/retention.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/retention.svg" alt="24 个测量包含一次数值 10 的尖峰，降采样到均值 1.375 后无法恢复阈值越界发生时刻。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 5 · 24 个测量包含一次数值 10 的尖峰，降采样到均值 1.375 后无法恢复阈值越界发生时刻。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:retention:end -->

时间序列数据库通常围绕大量按时间追加的测量点，提供标签过滤、窗口聚合、压缩、降采样和保留策略。时间数据库的历史问题还可能要求有效区间、版本更正、双时间和审计解释；二者存在交集，但不能互换名称。

按月分区有利于淘汰整月事件和缩小时间查询范围。但持续一年的状态区间即使从一年前开始，也可能覆盖今天；仅按 `valid_from` 分区后只查当月，就会漏掉它。状态区间与点事件应分开考虑分区策略。

降采样保存“每小时平均温度”，无法恢复每秒尖峰，也无法精确证明某秒的阈值事件。是否可删除原始数据，要服从未来需要回答的问题。备份也不能替代在线历史模型：备份的粒度、恢复成本和可查询能力不同。

## 7. 一个历史查询的正确性检查

设 `[10,12)` 在仓库，`[12,14)` 在维修区，14 点后未知。问 12 点：维修区；问 14 点：未知；问与 `[11,13)` 重叠的状态：两条。再加入迟到更正时，应进一步问“按哪一时刻的知识”。

时间戳应明确时区与精度。PostgreSQL `timestamptz` 表达时间点，并按会话时区显示，不保留最初输入的时区名称；若业务需要当地日历规则，应额外保留地区时区。具体时间类型约定见 [PostgreSQL 时间类型文档](https://www.postgresql.org/docs/18/datatype-datetime.html)。版本序号也不等于物理时间：它保证对象修改次序，却未必解释现实中的发生先后。

下一篇讨论没有明确关键词却“意思接近”的查询：[向量数据库：把语义相似变成近邻检索](/HomepageX/blog/modern-databases/07-vector/)。
