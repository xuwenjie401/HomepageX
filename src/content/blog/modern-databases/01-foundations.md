---
title: "现代数据库 01｜为什么需要数据库：从保存文件到组织查询"
description: "从一份物品清单出发，理解数据库、表、模式、查询、事务、索引与存储引擎；用页访问、并发更新和行列布局建立数据库的第一层直觉。"
date: 2026-09-29
tags: [数据库, 系统入门, 数据组织, 事务]
---

一家设备租赁公司最初用 CSV 管理物品：编号、名称、类别、价格、可用数量。几百行时，打开文件就能查；几百万行后，“找一件东西”“统计库存”“两个人同时租最后一件”开始成为三个完全不同的问题。

这组文章面向会写程序、了解数组和文件，但没有数据库背景的读者。我们从这份清单建立概念，经过关系、索引、空间、图、时间和向量，最后设计一个同时管理地点、区域、路径、物体、事件和历史状态的系统。完整路线见[专题目录](/HomepageX/blog/modern-databases/)。每篇的图和数字都服务于一个问题：**数据库怎样利用数据的结构，让正确的答案以可接受的代价出现？**

## 1. 文件已经能存数据，为什么还需要数据库？

### 1.1 困难来自访问方式，而非文件扩展名

假设每条记录占 200 字节，共一千万条，不计编码与文件开销约 2 GB。找编号为 742 的记录，最直接的程序逐行读、解析、比较。最坏检查一千万条；即使只返回一行，也可能读完整个文件。

把文件按编号排序，可以二分查找。但按类别筛选、按价格范围查询时，这个顺序未必有用。再维护一份按价格排序的文件？每次修改必须同时更新两份；中间崩溃、编号重复、两人同时修改又怎么办？

<!-- figure:scan-pages:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/scan-pages.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/scan-pages.svg" alt="同一按编号查询：全扫描触达全部示意数据页，索引先定位到 P11，再读取目标记录。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 1 · 同一按编号查询：全扫描触达全部示意数据页，索引先定位到 P11，再读取目标记录。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:scan-pages:end -->

图中的橙色表示本次实际要读的页。**索引不是让硬盘读得更快，而是让查询少读不相关的页。** 这里的页是数据库成批读写的存储单位，并非每一行都触发一次物理磁盘访问；缓存、预读与操作系统会改变真实 I/O。

文件系统擅长提供文件、目录、字节读写和访问权限。它通常不直接理解“编号唯一”“可用数量不能小于零”“两次修改必须一起成功”“价格在 100 到 200 之间”。当然可以在文件之上实现这些能力——做到后来，就是在构建数据库管理系统。

所以，“文件系统无法解决”应理解为**没有直接提供这些记录级语义与统一机制**，不是说用文件实现数据库在逻辑上不可能。很多数据库本来就把数据保存在普通文件里。

### 1.2 两条主线：查得合适，改得正确

本系列强调针对查询建立高效的数据组织和索引，因为这是理解不同数据库技术的共同入口。但完整数据库还必须管理约束、并发、故障恢复、权限和运维。一个查得很快、却会卖出两次最后一件库存的系统，仍然不合格。

## 2. 把第一组术语放进同一个例子

<!-- figure:anatomy:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/anatomy.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/anatomy.svg" alt="物品表中高亮一条记录和价格列，数据库、命名空间与模式约束分别位于不同层次。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 2 · 物品表中高亮一条记录和价格列，数据库、命名空间与模式约束分别位于不同层次。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:anatomy:end -->

| 术语 | 在租赁清单中的含义 | 不应混淆的地方 |
| --- | --- | --- |
| database，数据库 | 受统一规则管理的一组数据，例如租赁业务的数据集合 | DBMS 是管理它的软件；口语经常把两者都叫数据库 |
| table，表 | 一组具有相同字段结构的物品记录 | 表是逻辑对象，不要求物理上对应一个 CSV 文件 |
| schema，模式 | 字段名称、类型、约束及关系的定义 | PostgreSQL 中 schema 还指表等对象的命名空间 |
| row，行／记录 | 编号 742 这件可租物品的一条记录 | 行的位置不是可靠身份；排序后位置会变化 |
| column，列／属性 | 所有物品共有的某个字段，例如 `price` | 一个字段值与整列是不同层次 |
| query，查询 | 筛选、连接、聚合、排序等数据请求 | 不只是按编号取一条，也不一定返回原始记录 |

例如下面定义的不只是四个名字，还包括“不允许空编号”“价格非负”等规则：

```sql
CREATE TABLE items (
  item_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  price NUMERIC NOT NULL CHECK (price >= 0),
  available INTEGER NOT NULL CHECK (available >= 0)
);

SELECT item_id, name, price
FROM items
WHERE price >= 100 AND price < 200
ORDER BY price, item_id;
```

`SELECT` 指定返回哪些列，`WHERE` 定义哪些行符合条件，`ORDER BY` 定义结果顺序。没有 `ORDER BY` 时，不能依赖“上次恰好看到的行顺序”。表、行、列与顺序的正式说明可参阅 [PostgreSQL 概念入门](https://www.postgresql.org/docs/18/tutorial-concepts.html)。

## 3. 索引：为一种问题提前整理一份路线图

### 3.1 正文与目录为什么可以分开？

书的正文按章节组织，书末索引却按关键词组织。同样，数据库可以保持原始记录的位置，同时建立“价格 → 记录位置”的辅助结构。查价格区间时，先定位索引中的区间，再访问对应记录。

这个“记录位置”可能是页号和页内位置，也可能是主键；不同存储引擎实现不同。索引也可能包含查询所需的全部字段，减少回到主数据的访问，但是否真正免去访问主数据，还取决于系统的可见性检查等机制。

设记录数为 $N$，每个数据页约容纳 $b$ 条记录，结果为 $k$ 条：

$$
P_{\mathrm{scan}}\approx\left\lceil\frac{N}{b}\right\rceil,
\qquad
P_{\mathrm{index}}\approx h+P_{\mathrm{leaf}}+P_{\mathrm{fetch}}.
$$

这里 $P$ 表示页访问数量，$h$ 是定位到索引叶页的树高成本，后两项分别是继续扫描叶页与取回数据的成本。这是推理模型，不是性能预测器。若一千万条记录每页放 40 条，全扫约 25 万页；查少量记录时，索引可能只涉及几层目录和少量数据页。

但若要返回 80% 的数据，大量零散回表可能比顺序扫描更贵。**有索引，不代表每次使用索引都划算。**

### 3.2 每一种“快”都有维护成本

新增一行，既要写主数据，也要更新相关索引；索引占空间、占缓存，改变排序键还会改变索引位置。索引越多，写入与备份成本通常越高。

因此，设计索引前应列出工作负载：最常见的过滤条件、排序方式、返回数量，以及读写比例。`item_id = 742`、`price BETWEEN ...`、全文检索与“离某坐标最近”需要利用不同结构，第 3、4、7 篇会逐层解释。

## 4. 存储引擎：逻辑上的行，最终怎样落到字节？

### 4.1 行存与列存：访问什么，就希望什么靠在一起

<!-- figure:layouts:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/layouts.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/layouts.svg" alt="三条记录的行存与列存布局对照：列存将价格集中，行存将同一对象的字段集中。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 3 · 三条记录的行存与列存布局对照：列存将价格集中，行存将同一对象的字段集中。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:layouts:end -->

行存把一条记录的多个字段放得较近，按编号取整条记录很自然。列存把同一列的大量值放得较近，计算一千万件物品的平均价格时，可只读价格列，并利用重复值压缩与批量计算。

这解释了两类工作负载：**OLTP** 关注短事务、点查和频繁修改；**OLAP** 关注大范围扫描、分组统计和分析。它们是工作负载倾向，不是互斥的产品标签；混合系统可以组合多种布局。

### 4.2 页、缓冲池、日志与有序文件

storage engine，即存储引擎，负责把逻辑读写落实成页、文件、缓存和索引操作。缓冲池缓存热页；日志提供恢复依据；索引组织查找路径。查询优化器决定怎么执行请求，存储引擎提供执行时需要的访问方式。

常见组织不止一种。面向页的树结构通过更新或分裂相关页维护有序性。LSM 家族则先累积内存中的修改，再写出有序文件，通过后台合并整理不同版本。

<!-- figure:lsm:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/lsm.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/lsm.svg" alt="内存新值形成有序文件，新旧文件合并时保留所需版本；A 的新值 3 替换示例旧值 2。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 4 · 内存新值形成有序文件，新旧文件合并时保留所需版本；A 的新值 3 替换示例旧值 2。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:lsm:end -->

这把部分随机写改成批量顺序写，却会引入合并成本、查询多个文件的读放大与额外空间。Bloom filter 可以快速排除“不可能包含此键”的文件，存在假阳性，但正确实现下不会把已插入的键误判为不存在；它不能代替完整索引。相关实现脉络见 [RocksDB 入门](https://rocksdb.org/docs/getting-started.html)。

树与 LSM 都不是“一定更快”的答案。缓存大小、更新分布、后台合并、持久性设置和读写比例，都会改变结果。

## 5. 事务：最后一件库存不能租给两个人

### 5.1 两次“先读再写”为什么会出错？

<!-- figure:transaction:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/transaction.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/transaction.svg" alt="左侧两个请求先读后写导致重复出租；右侧条件扣减后第二个请求不能再满足库存大于零。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 5 · 左侧两个请求先读后写导致重复出租；右侧条件扣减后第二个请求不能再满足库存大于零。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:transaction:end -->

两个请求都读到 `available = 1`，都在应用程序里判断“可以出租”，再分别写入 0。库存看似合法，却发出了两份成功确认。错误来自两次操作之间的竞争窗口。

一个更直接的库存扣减入口是条件更新：

```sql
BEGIN;
UPDATE items
SET available = available - 1
WHERE item_id = 742 AND available > 0;
-- 应用必须检查受影响行数：恰好 1 行才继续写入租赁记录。
-- 为 0 行则不应返回出租成功；随后提交或回滚本次空操作。
COMMIT;
```

如果还要插入租赁记录，应把它放在同一事务里；插入失败时整个事务回滚。这个例子依赖数据库对并发更新的协调，不等于“写了 BEGIN，任意业务逻辑就自动正确”。需要读取多个对象并联合决策时，还可能需要显式锁、更强隔离级别和冲突重试。

### 5.2 ACID 四个词分别保护什么？

原子性（Atomicity）保护一组操作的整体成败；一致性（Consistency）指事务维持声明的约束和业务不变量，错误业务规则不会被数据库凭空修正；隔离性（Isolation）控制并发事务能观察到什么；持久性（Durability）规定确认成功后在约定故障模型下如何保留结果。

“隔离”不意味着所有数据库默认都像串行执行。比如 PostgreSQL 的默认 Read Committed 可以在同一事务的不同语句中看到新提交的数据。要把业务要求与具体隔离级别对应起来。参见[事务教程](https://www.postgresql.org/docs/18/tutorial-transactions.html)和[隔离级别](https://www.postgresql.org/docs/18/transaction-iso.html)。

写前日志 WAL 的关键次序是：有关日志先持久化，再允许相应脏数据页落盘；崩溃后可以依据日志恢复。提交确认、日志刷盘与副本确认的策略应明确配置。WAL 也不等于备份，误删数据照样可能忠实传播。参见 [WAL 原理](https://www.postgresql.org/docs/18/wal-intro.html)。

## 6. 亲手推演：该从哪里开始优化？

对同一张物品表，分别提出三个请求：按编号取一行、按价格取前 20 件、统计全表平均价格。先写出需要哪些列、可能读多少行，再考虑编号索引、价格有序索引或批量列扫描。不要一开始就问“选哪个数据库最快”。

再做一个反例：给每一列都加索引，是否总会改善系统？如果主要负载是高频写入、查询只按编号，你会付出额外维护代价，却几乎没有读取收益。

这一篇建立了两个判断尺度：**查询能排除多少不相关数据，修改能否维持必要约束。** 下一篇从逻辑层继续：[关系数据库：用表表达事实，用 SQL 组合答案](/HomepageX/blog/modern-databases/02-relational/)。
