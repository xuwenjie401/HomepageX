---
title: "现代数据库 02｜关系数据库：用表表达事实，用 SQL 组合答案"
description: "理解关系模型、主外键、连接、规范化与查询优化；从租赁清单中的重复信息出发，追踪一个 SQL 查询的逻辑含义和物理执行。"
date: 2026-09-29
tags: [数据库, 关系模型, SQL, 查询优化]
---

[上一篇](/HomepageX/blog/modern-databases/01-foundations/)解决了“为什么需要统一管理数据”。现在的问题是：物品、顾客、租赁记录越来越多，应该怎样表达它们之间的事实，才能可靠地回答新问题？

如果每条租赁记录都复制顾客姓名、手机号、物品类别和类别说明，读取一张表很方便。但修改一个手机号时，究竟应该修改多少行？漏掉其中一行，哪个版本才是真的？关系模型从这里进入我们的讨论。

## 1. 关系不是连线，而是一组符合结构的事实

### 1.1 从数组转向关系

数学上的 relation，关系，可以理解为给定属性上的元组集合。`Customer(customer_id, name)` 表示“编号与姓名组成的事实”；`Rental(rental_id, customer_id, item_id)` 表示“哪次租赁连接了哪位顾客和哪件物品”。表是这种思想的工程表示。

理论关系没有重复元组，也没有隐含行序；实际 SQL 默认常采用允许重复的多重集语义，且存在 `NULL`。因此不能把“SQL 的行为”与“纯粹集合代数”完全画等号。

<!-- figure:relations:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/relations.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/relations.svg" alt="三张小表通过顾客编号与物品编号关联：顾客 7 的两次租赁分别引用物品 742 和 743。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 1 · 三张小表通过顾客编号与物品编号关联：顾客 7 的两次租赁分别引用物品 742 和 743。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:relations:end -->

图中三张表描述三类事实，编号是连接它们的稳定锚点。物品今天在文件中的第 30 行，明天移到第 90 行，不应改变租赁记录指向谁。逻辑模型与物理位置的分离，使存储布局能改变，而业务查询继续成立。关系模型的历史起点是 [Codd 的 1970 年论文](https://research.ibm.com/publications/a-relational-model-of-data-for-large-shared-data-banks)。

### 1.2 SQL 描述答案，而非逐条搬运步骤

```sql
SELECT c.name, i.name AS item_name
FROM rentals AS r
JOIN customers AS c ON c.customer_id = r.customer_id
JOIN items AS i ON i.item_id = r.item_id
WHERE r.status = 'open';
```

这个查询表达“返回未结束租赁中的顾客名与物品名”。程序没有指定先读哪张表、用树还是哈希、是否并行。数据库可以在保持结果语义的前提下选择不同物理算法。这就是声明式查询的重要价值。

## 2. 主键和外键：让连接有可靠依据

primary key，主键，是选定用于唯一标识行的键；可以是一列，也可以是多列组合。在 SQL 中，它要求唯一且非空。顾客姓名不适合作为主键，因为会重名、会改名；稳定的 `customer_id` 更合适。

foreign key，外键，约束某个字段组合必须指向被引用表中存在的键。例如：

```sql
CREATE TABLE customers (
  customer_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);
CREATE TABLE rentals (
  rental_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
  item_id INTEGER NOT NULL REFERENCES items(item_id),
  status TEXT NOT NULL CHECK (status IN ('open', 'closed'))
);
```

这样就不能悄悄为不存在的顾客登记租赁。`NOT NULL` 表示本例不允许“暂时没有顾客”；仅有外键通常不禁止空值。删除被引用对象时，拒绝、级联删除或置空，也应由业务含义决定。

**约束与索引职责不同。** 外键负责引用完整性，索引负责加速查找。在 PostgreSQL 中，主键会建立唯一索引，但引用端外键列不会因此自动建立索引；需要根据连接与删除检查负载决定。具体行为见[约束文档](https://www.postgresql.org/docs/18/ddl-constraints.html)。

## 3. Join 到底做了什么？

### 3.1 每个结果行来自一对满足条件的输入行

<!-- figure:join:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/join.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/join.svg" alt="顾客与租赁的配对矩阵显示三处等值命中；结果中顾客 7 出现两次，这是两笔事实。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 2 · 顾客与租赁的配对矩阵显示三处等值命中；结果中顾客 7 出现两次，这是两笔事实。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:join:end -->

内连接可以先想象为枚举左右表所有行对，再保留键相等的组合。如果顾客 7 有两笔租赁，结果里就出现两次顾客 7。重复出现并不一定是“连接出了错”，而是一个对象对应多个事实。

设两侧分别有 $n$ 和 $m$ 行，朴素枚举需要检查 $nm$ 对。这个定义帮助理解结果，却不是数据库一定采用的执行方式。

### 3.2 三类常见物理算法

| 算法 | 实际怎么做 | 哪些条件下值得考虑 |
| --- | --- | --- |
| Nested Loop，嵌套循环 | 对外表每行，寻找内表匹配项 | 外表很小，且内表连接键有有效索引 |
| Hash Join，哈希连接 | 把一侧按连接键放进哈希表，再扫描另一侧探测 | 等值连接，较小一侧能较好地放进内存 |
| Merge Join，归并连接 | 两侧按键排序，像合并两个有序列表一样前进 | 输入已有合适顺序，或排序成本能被摊销 |

哈希连接在理想内存条件下通常接近线性的读入工作量，但重复键可能产生大量结果，不能省去输出这些行的代价。内存不足会分批或溢写；嵌套循环也不必然差：外表只有 3 行时，做 3 次索引查找可能非常便宜。

### 3.3 外连接与 NULL：不要无意删除“没有发生”的事实

```sql
SELECT c.customer_id, r.rental_id
FROM customers AS c
LEFT JOIN rentals AS r
  ON r.customer_id = c.customer_id AND r.status = 'open';
```

左连接保留没有未结束租赁的顾客，右侧字段填 `NULL`。若把 `r.status = 'open'` 移到 `WHERE`，没有匹配的行会被过滤掉，因为与 `NULL` 比较不是 true。

<!-- figure:null:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/null.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/null.svg" alt="左连接中 ON 过滤保留顾客 8 的空租赁行；把条件放进 WHERE 会使该顾客从结果消失。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 3 · 左连接中 ON 过滤保留顾客 8 的空租赁行；把条件放进 WHERE 会使该顾客从结果消失。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:null:end -->

`NULL` 表示缺失或未知，不能用 `= NULL` 检查，应写 `IS NULL`。条件可以得到 true、false、unknown，`WHERE` 只保留 true。还要区分 `COUNT(*)`（行数）和 `COUNT(r.rental_id)`（非空租赁编号数量）。这类语义错误，比选错一个索引更隐蔽。

## 4. 规范化：重复的到底是什么事实？

### 4.1 把手机号复制到每一笔租赁，会发生什么？

<!-- figure:normalization:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/normalization.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/normalization.svg" alt="左侧租赁表重复顾客电话导致部分更新；右侧单独保存顾客当前电话，通过编号恢复关联。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 4 · 左侧租赁表重复顾客电话导致部分更新；右侧单独保存顾客当前电话，通过编号恢复关联。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:normalization:end -->

三种异常来自同一个根因：把不同层次的事实混在一张表里。修改手机号需要改多行，这是更新异常；还没有租赁就无法登记顾客，是插入异常；删掉最后一笔租赁就丢失顾客资料，是删除异常。

normalization，规范化，利用依赖关系拆分这些事实。若每个顾客编号唯一确定当前手机号，可以写：

$$
\mathrm{customer\_id}\to\mathrm{phone}.
$$

箭头表示函数依赖：相同顾客编号不能对应两个不同的当前手机号。这不是程序的函数调用，也不是“编号数值算出了电话”。

### 4.2 用一张明细表理解前三级范式

设租赁明细以 `(rental_id, item_id)` 为组合键，并保存 `quantity`、`item_name`、`customer_id`、`customer_phone`。

- **第一范式**：让每个字段保存其定义域中的单个值，不把 `item_id` 写成逗号拼接的多个编号。原子性的界线由模型决定，不能机械理解为“所有字符串都得继续拆”。
- **第二范式**：在第一范式基础上，非主属性不能只依赖候选键的一部分。例如 `item_name` 仅依赖 `item_id`，应归入物品表。
- **第三范式**：进一步控制非键属性引入的传递依赖。顾客电话依赖 `customer_id`，不应随每笔租赁重复保存。严格说，对每个非平凡依赖，决定因素应为超键，或被决定的属性是候选键的一部分。

拆表不是越碎越好。需要检查拆分能否无损连接回来，关键约束能否继续有效维护。超键是能唯一确定整行的属性集合，候选键是去掉任何属性就不再具备此能力的最小超键；主键是候选键中被选定的一个。

### 4.3 历史价格为什么不应该随当前价格更新？

订单成交价格是订单发生时的事实，不是当前商品价格的冗余副本。把它单独存入明细，是在保存不同语义；不能为了“没有重复”而只连接当前价格，否则过去账单会随着调价改变。

有意识的反规范化也很常见，例如分析宽表、物化汇总。但要明确事实源、刷新规则与容许延迟。先理解规范化保护什么，才能判断何时值得付出重复维护成本。

## 5. 查询优化：同一个问题可以有很不一样的路线

### 5.1 先缩小候选，再做昂贵工作

<!-- figure:plans:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/plans.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/plans.svg" alt="两种查询路线的教学行数对照：先过滤可把后续连接输入从一百万行降到一百行。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 5 · 两种查询路线的教学行数对照：先过滤可把后续连接输入从一百万行降到一百行。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:plans:end -->

假设一百万笔租赁，只有 100 笔未结束。先把全部租赁与物品连接，再过滤，可能传递很多无用数据；若能先过滤，就只需处理少量租赁。图中的数字是教学基数，表示每步有多少行，不是实测时间。

优化器会枚举或启发式搜索连接顺序与访问路径，依据统计信息估算代价。选择率是满足条件的比例：

$$
\hat n_{\mathrm{out}}=n_{\mathrm{in}}\hat s.
$$

例如一百万行乘估计选择率 $0.0001$，得到 100 行。如果数据已经变化、统计信息却没更新，实际可能有十万行；原本很便宜的嵌套循环会变得昂贵。类别与价格高度相关时，也不能总把两列的选择率简单相乘。

### 5.2 读执行计划时，先比较估计与实际

PostgreSQL 可以运行：

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT item_id FROM items WHERE price >= 100 AND price < 200;
```

`EXPLAIN` 展示计划；`ANALYZE` 会真正执行语句。重点看估计行数与实际行数、循环次数、过滤掉的行、缓冲页访问与是否发生溢写。计划 cost 是优化器成本单位，不是毫秒。细节见 [EXPLAIN 文档](https://www.postgresql.org/docs/18/using-explain.html)。

不要把“先过滤”当成任意改写的许可。外连接中的过滤位置可能改变结果；聚合前后过滤也有不同含义。优化必须先保持语义，再减少工作。不同引擎支持的改写和算法也有差异，可对照 [SQLite 优化器说明](https://www.sqlite.org/optoverview.html)。

## 6. 为什么关系数据库持续有用，又在哪里需要补充？

它长期成为核心业务系统的常见基础，是因为它同时提供了稳定的数据建模、约束、事务与声明式查询。新需求经常只是多写一个连接和分组，而不必重新安排全部磁盘文件。这种可组合性与成熟工具生态，解释了它持续适合订单、库存、账务和管理系统。

它的边界来自工作负载，而非“表不能存复杂数据”：超高频时间序列写入可能需要特定布局；可变深度关系探索需要高效邻接访问；几百维语义距离需要专门的近邻结构。关系数据库也能通过扩展承担其中很多任务，不能把 SQL 与空间、图、向量能力看成互斥阵营。

自测一次：有 3 位顾客、4 笔租赁，其中一人没有租赁、一人有 3 笔。内连接和左连接各返回多少行？答案分别是 4 行和 5 行；每个结果行都是一个匹配事实，而非“每个顾客只能出现一次”。

下一篇把物理访问路线拆开：[数据库索引：数据结构决定你能快速问什么](/HomepageX/blog/modern-databases/03-indexes/)。
