---
title: "现代数据库 03｜数据库索引：数据结构决定你能快速问什么"
description: "逐步拆解 B-tree、B+ tree、哈希、位图和倒排索引；通过查找、范围扫描、分裂、集合运算与复合键反例，理解索引的能力边界。"
date: 2026-09-29
tags: [数据库, 索引, 数据结构, B+树]
---

同样是一千万件物品，按编号找一件、按价格找一段、按标签同时满足两个条件、按文字找描述，四个请求要求的数据组织并不相同。[关系模型](/HomepageX/blog/modern-databases/02-relational/)负责表达答案；索引负责提供有希望少读数据的路线。

索引的核心问题是：**什么信息能证明某一大块数据不用读？** 有序树利用大小关系，哈希利用键到桶的映射，位图利用集合运算，倒排利用词项到文档的反向映射。接下来让每个结构执行一次查询。

## 1. 为什么数据库里的树又矮又宽？

### 1.1 二叉树比较次数少，却可能碰很多页

在内存中，每次访问一个指针通常不太显眼；在外存中，每个节点落在不同页上会昂贵得多。与其每读一页只得到一次二选一，不如在一页放许多分隔键，把下层分成几十乃至几百个范围。

设一页有 $P$ 字节，可用空间为 $P-H$，每个键与子指针平均占 $e$ 字节，则粗略扇出为：

$$
F\approx\left\lfloor\frac{P-H}{e}\right\rfloor.
$$

若页为 8192 字节、页头等预留 192 字节、每项约 32 字节，得到约 250 个分支。真实扇出还受键长度、槽数组、填充率和压缩影响，不能直接把这个估算当实现常数。

## 2. B-tree 与 B+ tree：把有序区间组织成页

### 2.1 点查向下走，范围查询沿叶层走

<!-- figure:bplus:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/bplus.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/bplus.svg" alt="根节点用 20 和 40 分隔叶页；键 26 进入中间页，范围 18 到 36 扫描得到三个键。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 1 · 根节点用 20 和 40 分隔叶页；键 26 进入中间页，范围 18 到 36 扫描得到三个键。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:bplus:end -->

B-tree 是一类平衡多路搜索树；经典 B-tree 的内部节点也可以保存记录或记录关联信息。B+ tree 的典型形式把数据项集中在叶层，内部节点主要用于导航，并连接相邻叶页。所有叶子深度一致，避免一条分支无限拉长。

图中查键 26：根节点把键空间按 20、40 分割，26 进入中间叶页。查闭区间 `[18, 36]`：先定位 18 的插入位置，从那里沿叶层向右，读到大于 36 为止。若对应键只有 20、26、35，就返回这三项。

理想平衡条件下，定位成本按 $\log_F N$ 增长；返回 $k$ 条记录还要付出读叶页与取结果的代价，不能把范围查询整体写成“永远对数时间”。

产品命名不一定采用教科书分类：PostgreSQL 对外称 B-tree，其实现有叶页、内部页和同层页链接。讨论实现应以文档为准，见 [PostgreSQL B-tree](https://www.postgresql.org/docs/18/btree.html)。

### 2.2 插入为什么会引起分裂？

<!-- figure:split:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/split.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/split.svg" alt="五个键超过教学页容量四：叶页分成两部分，并把右侧起始键 30 复制为导航边界。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 2 · 五个键超过教学页容量四：叶页分成两部分，并把右侧起始键 30 复制为导航边界。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:split:end -->

假设教学叶页最多放 4 个键。已有 `[20, 26, 35, 38]`，插入 30 后超出容量，于是分成 `[20, 26]` 和 `[30, 35, 38]`，把右页的边界 30 交给父节点。父节点如果也满，还可能继续向上分裂；根分裂会增加一层。

分裂不是只写新记录：要更新页内容、导航信息和日志。随机键可能导致分散的页修改；单调递增键集中在右侧，局部性较好，也可能形成热点。删除后的回收、合并与并发页操作，各实现有自己的策略。

### 2.3 聚簇与二级索引：叶子后面还有什么？

有的引擎按主键组织主数据，主键树叶子就是整行，二级索引再保存主键；有的引擎把表数据放在堆页中，索引指向元组位置。因此“查到索引叶子”不总等于“已经取到整条记录”。选择很多列和只返回索引中已有列，代价可能不同。

## 3. 复合索引：多列如何变成一个顺序？

<!-- figure:composite:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/composite.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/composite.svg" alt="按类别再价格排列的六个复合键中，低价项分散在三个类别段，指定类别后才形成紧凑范围。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 3 · 按类别再价格排列的六个复合键中，低价项分散在三个类别段，指定类别后才形成紧凑范围。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:composite:end -->

`(category, price)` 通常按字典序排列：先比较类别，类别相同才比较价格。`category = 'camera' AND price < 200` 因而对应一个较连续的区间；只有 `price < 200` 时，低价项散布在每个类别的小区间里。

这就是“左侧前导列”为什么重要。不要把口诀夸大成“没有第一列就完全不能用索引”：某些引擎会采用 skip scan 等方式，反复定位不同前导值，是否划算取决于不同值数量和选择率。PostgreSQL 18 的具体边界见[多列索引文档](https://www.postgresql.org/docs/18/indexes-multicolumn.html)。

两个独立索引 `(category)`、`(price)` 也不等于一个复合索引。前者可能分别得到候选集合再相交，后者直接沿共同的键顺序访问。所需排序、返回规模、列之间的相关性，都会影响选择。

## 4. 哈希索引：相等很直接，大小关系被打散

<!-- figure:hash:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/hash.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/hash.svg" alt="整数按模四映射到四个桶：2、6、10 冲突在桶 2，范围 6 到 10 却跨越全部桶。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 4 · 整数按模四映射到四个桶：2、6、10 冲突在桶 2，范围 6 到 10 却跨越全部桶。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:hash:end -->

哈希函数把键映射到桶号。教学例子使用 $h(k)=k\bmod 4$：键 2、6、10 都进入桶 2。查键 6，先算桶号，再在桶内比较原键。**哈希值相同不能证明键相同**，冲突处理是算法的一部分。

良好分布和合适负载因子下，等值查找通常有期望常数级的桶访问；这不是最坏情况保证，也不包含所有磁盘、锁和溢出成本。热点、冲突与扩容都可能变贵。

查 `[6, 10]` 就不自然了：哈希打散了顺序，结果可能落在所有桶中。也不能靠它直接得到“价格最小的 20 件”。因此，哈希不是比有序树“更高级”的替代品，而是利用了更窄的查询假设。[PostgreSQL 索引类型说明](https://www.postgresql.org/docs/18/indexes-types.html)给出了各访问方法支持的操作类型。

## 5. 位图索引：一组布尔条件变成机器字运算

### 5.1 把每个值对应的记录集合编码为位

<!-- figure:bitmap:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/bitmap.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/bitmap.svg" alt="camera 位图与 available 位图按位相交，计算得到 10010000，即记录 1 和 4。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 5 · camera 位图与 available 位图按位相交，计算得到 10010000，即记录 1 和 4。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:bitmap:end -->

假设 8 条记录，位置从左到右对应编号 1 到 8。`camera` 的位图为 `10110010`，`available` 的位图为 `11010100`，逐位 AND 得 `10010000`，结果是编号 1 和 4。

一位表示该行是否具有该值；AND 对应交集，OR 对应并集。CPU 可以一次操作一个机器字，压缩位图还能跳过长段相同位。涉及 NOT 时要注意有效行集合、已删除行和空值语义，不能把所有不存在的位简单翻成结果。

### 5.2 为什么常用于分析型工作负载？

少量离散值、很多行和多条件组合，有利于复用位图并压缩。若每行几乎都有不同值，或频繁修改引发大量维护与并发争用，收益可能下降；压缩方式和具体实现会改变边界。[Oracle 数据仓库索引文档](https://docs.oracle.com/en/database/oracle/oracle-database/19/dwhsg/data-warehouse-optimizations-techniques.html)讨论了位图与分析工作负载。

还要区分**持久化位图索引**与**查询执行时临时生成的位图**。PostgreSQL 的 Bitmap Index Scan 可以从普通索引收集位置，再按数据页访问，并不意味着磁盘上存在同名的位图索引类型。参见[索引组合](https://www.postgresql.org/docs/18/indexes-bitmap-scans.html)。

## 6. 倒排索引：把“文档有哪些词”反过来

### 6.1 一个词对应一份出现位置清单

<!-- figure:inverted:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/inverted.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/inverted.svg" alt="四篇小文档生成相机与防水的倒排列表，双列表交集只包含文档 3。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 6 · 四篇小文档生成相机与防水的倒排列表，双列表交集只包含文档 3。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:inverted:end -->

正向表示是“文档 1 → 红色、相机”；倒排表示是“相机 → 文档 1、3、4”。每个词对应的 posting list 可以保存文档编号、词频和出现位置。

查询“相机 AND 防水”时，对两个有序编号列表求交。用双指针：编号相同就输出并前进两边；较小的一边前进。最直接的工作量与两个列表长度之和成正比，跳跃指针、压缩块和更好的交集策略能进一步少做比较。

### 6.2 字面匹配与语义匹配不是同一种能力

词项存在并不表示短语出现。如果要判断“红色 相机”相邻，需要位置；如果要排序，需要词频、文档频率等评分信号。分词、大小写、同义词与语言处理都会影响召回。算法基础可参见 [Stanford 信息检索教材](https://nlp.stanford.edu/IR-book/html/htmledition/a-first-take-at-building-an-inverted-index-1.html)。

PostgreSQL 的 GIN 是通用倒排索引框架，可以支持全文、数组等对象的组成元素查询；不是所有 JSON 表达式都会被任意一个 GIN 索引支持，要匹配操作符类。[GIN 文档](https://www.postgresql.org/docs/18/gin.html)描述了这种结构。

倒排擅长“哪些对象包含这些词项”，却不会自动知道“防雨”与“防水”语义接近。第 7 篇将介绍另一种近邻组织方式；它们常常值得组合。

## 7. 把查询形状与数据结构对应起来

| 查询形状 | 首先考虑的结构 | 保留下来的信息 | 主要代价或边界 |
| --- | --- | --- | --- |
| 编号精确相等 | B+ tree 或哈希 | 顺序或桶定位 | 写维护、冲突、回表 |
| 范围、排序、前缀组合 | B+ tree | 全序 | 键顺序必须匹配查询 |
| 多个离散条件组合 | 位图 | 成员关系 | 更新和编码成本 |
| 词项、标签、组成元素 | 倒排 | 元素到对象的清单 | 分词、长列表、评分成本 |
| 空间相交、最近邻 | 空间结构 | 区域边界与距离界 | 下一篇讨论 |

练习：只有 `(name)` 的 B-tree，是否必然能加速 `LIKE '%camera%'`？通常不能用普通的前缀范围定位，因为模式开头没有固定前缀；具体语言排序规则、操作符与专用文本索引还会影响行为。这说明“字段上有索引”远远不够，还要看表达式能否映射成索引理解的操作。

评估索引应观察候选数、页访问、维护成本与真实结果规模。下一篇把一维顺序推向多维空间：[空间数据库：为什么附近不能只靠 XYZ 排序](/HomepageX/blog/modern-databases/04-spatial/)。
