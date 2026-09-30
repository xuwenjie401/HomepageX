# 现代数据库系列：来源、插图与验证记录

## 内容与定位

九篇正文位于 `src/content/blog/modern-databases/`，专题入口为 `/HomepageX/blog/modern-databases/`。沿用任务开始前已有的 `databaseSeries` 注册和专题页面，不覆盖其原有内容。本文是数据库领域教程，不是围绕一篇论文复现实验的精读。48 张图全部为程序绘制的原创教学图；没有复制产品宣传图或把人工数字标成性能测量。

阅读顺序：基础 → 关系 → 索引 → 空间 → 图 → 时间 → 向量 → 多模型 → 系统设计。每篇包含机制、具体数据或查询、失败边界与工程应用；终篇独立说明六类实体、五类查询、存储和索引、版本同步、故障与演进。

## 来源与版本

核对日期：2026-09-29。逐项链接、所属文章、版本口径保存在 [sources.json](../scripts/database-series/sources.json)，共 35 个一手来源。网页在相应论点旁给简洁链接。

- PostgreSQL 文档固定为 **18**：关系概念、约束、事务、WAL、隔离、索引类型、多列索引、GIN、位图扫描、递归查询、范围、日期时间及逻辑解码。
- PostGIS 官方文档：几何类型、空间索引、`ST_3DDWithin`、二维 `<->`。动态文档以访问日期为准；本文不声称这些 SQL 已在所有 PostGIS 版本测试。
- Oracle Database **19c** 数据仓库指南：位图与分析负载。早期使用的 `dwhsg/indexes.html` 无法取得，已改成实际可访问的 `data-warehouse-optimizations-techniques.html`。
- Codd：1970 年论文的 **IBM Research 原始出版记录**，只用于关系模型历史定位。ACM DOI 页面当次返回 403，正文改链 IBM，不声称已从该页面阅读全文。
- RDF **1.1** W3C 标准、Neo4j 官方概念页、SciPy KDTree、Redis GEOADD、RocksDB 与 Stanford 信息检索教材：分别核对知识表示、邻接语义、维度边界、空间编码、LSM 和倒排概念。
- SQL Server 系统时间表概述：只引用系统版本历史的职责，不宣称系统时间自动解决有效时间。
- HNSW：**arXiv:1603.09320v4，2018-08-14**。检查完整 PDF，重点核对算法 1–5 的插入、邻居选择、分层搜索和候选宽度。原始 PDF 与抽取文本仅放仓库外。
- FAISS 官方索引 wiki、pgvector 项目、Milvus 概述与过滤查询、Debezium Outbox：区分算法库与系统能力，核对过滤和传播协议。动态页面不据此生成跨产品性能排名。

### 原论文图盘点与本系列的取舍

本系列没有实验复现或跨产品性能结论。Codd 的引用仅用于出版史；HNSW 是唯一深入到原论文算法的来源，因此已盘点其 **Figure 1–15**。下面均未重印：图 1–2 的机制在第 7 篇用简化数据与原创示意讲解；图 3–15 的实验依赖原论文数据、硬件与参数，本文未分析这些实验，也没有借其曲线宣称任一数据库的速度。选择省略是因为本系列讲解跨领域基础与设计，而非缩减一篇 HNSW 实验精读的覆盖。进一步做 HNSW 论文精读时应重新依照全图覆盖原则处理。

| 原图 | PDF 物理页 | 内容 | 本文处理 |
| --- | --- | --- | --- |
| Figure 1 | 3 | 层次搜索 | 第 7 篇原创层级图与搜索说明 |
| Figure 2 | 3 | 跨簇邻居选择 | 第 7 篇说明连接多样性，未复现原图 |
| Figure 3 | 6 | 四维数据的层高参数 | 不重印参数实验 |
| Figure 4 | 6 | 高维数据的层高参数 | 不重印参数实验 |
| Figure 5 | 6 | SIFT 层高参数 | 不重印参数实验 |
| Figure 6 | 6 | 底层连接数参数 | 不重印参数实验 |
| Figure 7 | 6 | 聚簇与邻居选择对比 | 仅说明剪枝／导航依赖数据分布 |
| Figure 8 | 6 | 连接预算与召回代价 | 不引用实验数值 |
| Figure 9 | 7 | 构建线程扩展 | 不给构建吞吐结论 |
| Figure 10 | 7 | 构建与查询代价 | 仅解释两类预算不同 |
| Figure 11 | 7 | 数据量与候选预算 | 不作为复杂度无条件保证 |
| Figure 12 | 8 | NSW 与分层方法对比 | 不重印基准曲线 |
| Figure 13 | 9 | 欧氏数据算法比较 | 不给产品排名 |
| Figure 14 | 10 | 一般距离空间比较 | 不给产品排名 |
| Figure 15 | 11 | FAISS 比较与规模 | 不给当前产品性能结论 |

## 插图生产与复现

- 源码：[figures.py](../scripts/database-series/figures.py)，Python 标准库，无随机种子依赖。
- 公式：[typeset.mjs](../scripts/database-series/typeset.mjs)，复用 [MathJax/STIX2](../scripts/lib/math.mjs)，与正文采用同一路径字形。
- 图与图注清单：[illustrations.json](../scripts/database-series/illustrations.json)。每图含所属篇、真实尺寸、图注与 alt。
- 插图装配：[assemble.py](../scripts/database-series/assemble.py)，保留可重复替换的图标记，按每篇出现顺序编号。
- 发布文件：`public/media/modern-databases/*.svg`，48 张，每张 1000 × 500。图是矢量，可以点击放大；截图、PDF、栅格联系表和运行缓存不入仓库。

```sh
python3 scripts/database-series/figures.py
node scripts/database-series/typeset.mjs
python3 scripts/database-series/assemble.py
node scripts/database-series/render-qa.mjs /tmp/homepagex-database-qa/figures
python3 scripts/database-series/verify-examples.py
npm run build
python3 scripts/database-series/validate.py
npm run check
```

`render-qa.mjs` 使用现有 Sharp 生成逐图 PNG 和 8 张联系表，输出路径须为仓库外的绝对路径。`browser-qa.mjs` 使用已有 Playwright；若没有项目本地包，可通过 `DATABASE_QA_PLAYWRIGHT` 指定已安装模块 URL，再传入本地预览 origin 与外部输出目录。无需把当前机器的绝对依赖路径写进仓库。

## 计算假设与反例

- 页读取：一千万条记录，每页约 40 条，扫描约 25 万页；只做访问量估计，不转换成毫秒。树页估算使用 8192 字节页、192 字节预留和 32 字节条目，近似扇出 250。
- B+ tree：教学叶页容量为 4；键序列、插入 30 和范围 `[18,36]` 明确写入脚本，不代表特定数据库的页布局。
- 位图：`10110010 AND 11010100 = 10010000`，记录编号从左到右为 1–8；倒排交集为文档 3。
- 空间：几何按固定坐标计算。L 形区域的包围盒会误命中缺口；点到 `[3,5] × [4,6]` 的下界为 5。楼层例子 A=(0,0,30)、B=(3,4,0)，三维距离为 30 和 5。楼层侧图明确不按统一比例。
- Octree 绘制八个半边长子立方体；KD-tree 是固定点集分割示意，不声称采用某个具体实现的默认构造。
- Geohash 图只画前两位二分规则，不把它当完整字符编码或固定九宫格半径算法。
- 图遍历例子明确保存 visited 与层 frontier；分支数 10、深度 4 的完整树形展开合计 11111 个位置。条形保留可见宽度，数字才表示基数，不是假性能曲线。
- 双时间图横轴一小时 120 单位，纵轴一小时 54 单位；查询点对应有效时间 10:30，系统时间分别为 12:30 与 14:30。14 点关闭旧认知后插入仓库与维修区的新认知。
- 降采样由 23 个 1 和一个 10 得到均值 1.375，原始尖峰信息确实丢失。
- 向量使用二维单位向量手算；高维体积为 `0.9 ** d`；召回集合交集为 3/5。IVF 边界点在脚本中验证属于第二中心，而查询属于第一中心。
- 终篇假设对象与图片规模仅用于字节量和增长率估计。图中 0.94 等相似度是用来展示排序的教学输入，不是某个模型输出；HNSW 图不是实际索引构建结果。

## 验证记录

2026-09-29：

- 已逐张查看全部 48 张自制图的栅格渲染，修复复合索引小标题重叠、并发图提交顺序、轴标签与连线穿字；对修改图额外检查原尺寸。
- `npm run build` 成功生成全站 33 个页面；`npm run check` 为 0 errors、0 warnings、0 hints。
- 九篇构建产物均含正文，48 张图完整装配；图片尺寸、alt、放大链接、连续编号、文章内锚点与相邻文章链接通过 `validate.py`。
- 数学公式在构建时渲染为 SVG，正文及图内无错误节点、无残留公式文本；XML 检查包括混排标签的重复属性。
- `verify-examples.py` 通过：SQLite 的连接、NULL、外键、范围查询、带环递归，以及两个独立连接的并发条件扣减；参考计算验证空间、时间、索引集合、向量过滤、乱序删除与分片 top-k。
- 这些检查**不是 PostGIS、Milvus、Neo4j 或 pgvector 的集成测试，也不是性能测试**。PostGIS 与范围类型 SQL 是按官方文档核对的教学模板。当前环境 Docker socket 不可访问，未启动外部数据库容器，不把 SQLite 结果冒充 PostgreSQL 执行结果。
- 实际浏览器完成 9 篇 × 2 视口：1440px 与 390px，检查真实 `innerWidth`、整页 `scrollWidth`、图片解码、分级目录存在、点击目标和手机跳转收起；专题页在两种宽度均有九篇文章且无整页溢出。48 张 SVG 文字边界无越界。
- 本次只写本地文件；未提交、推送或发布。沿用已有专题入口，未更改已有文章或共享文章模板。

## 逐图清单

下表由插图清单整理；每图已引用一次，详细说明与替代文本保存在 JSON 中。

| 篇 | 文件 | 说明 |
| --- | --- | --- |
| 01 | [scan-pages.svg](../public/media/modern-databases/scan-pages.svg) | 同一按编号查询：全扫描触达全部示意数据页，索引先定位到 P11，再读取目标记录。 |
| 01 | [anatomy.svg](../public/media/modern-databases/anatomy.svg) | 物品表中高亮一条记录和价格列，数据库、命名空间与模式约束分别位于不同层次。 |
| 01 | [layouts.svg](../public/media/modern-databases/layouts.svg) | 三条记录的行存与列存布局对照：列存将价格集中，行存将同一对象的字段集中。 |
| 01 | [lsm.svg](../public/media/modern-databases/lsm.svg) | 内存新值形成有序文件，新旧文件合并时保留所需版本；A 的新值 3 替换示例旧值 2。 |
| 01 | [transaction.svg](../public/media/modern-databases/transaction.svg) | 左侧两个请求先读后写导致重复出租；右侧条件扣减后第二个请求不能再满足库存大于零。 |
| 02 | [relations.svg](../public/media/modern-databases/relations.svg) | 三张小表通过顾客编号与物品编号关联：顾客 7 的两次租赁分别引用物品 742 和 743。 |
| 02 | [join.svg](../public/media/modern-databases/join.svg) | 顾客与租赁的配对矩阵显示三处等值命中；结果中顾客 7 出现两次，这是两笔事实。 |
| 02 | [null.svg](../public/media/modern-databases/null.svg) | 左连接中 ON 过滤保留顾客 8 的空租赁行；把条件放进 WHERE 会使该顾客从结果消失。 |
| 02 | [normalization.svg](../public/media/modern-databases/normalization.svg) | 左侧租赁表重复顾客电话导致部分更新；右侧单独保存顾客当前电话，通过编号恢复关联。 |
| 02 | [plans.svg](../public/media/modern-databases/plans.svg) | 两种查询路线的教学行数对照：先过滤可把后续连接输入从一百万行降到一百行。 |
| 03 | [bplus.svg](../public/media/modern-databases/bplus.svg) | 根节点用 20 和 40 分隔叶页；键 26 进入中间页，范围 18 到 36 扫描得到三个键。 |
| 03 | [split.svg](../public/media/modern-databases/split.svg) | 五个键超过教学页容量四：叶页分成两部分，并把右侧起始键 30 复制为导航边界。 |
| 03 | [composite.svg](../public/media/modern-databases/composite.svg) | 按类别再价格排列的六个复合键中，低价项分散在三个类别段，指定类别后才形成紧凑范围。 |
| 03 | [hash.svg](../public/media/modern-databases/hash.svg) | 整数按模四映射到四个桶：2、6、10 冲突在桶 2，范围 6 到 10 却跨越全部桶。 |
| 03 | [bitmap.svg](../public/media/modern-databases/bitmap.svg) | camera 位图与 available 位图按位相交，计算得到 10010000，即记录 1 和 4。 |
| 03 | [inverted.svg](../public/media/modern-databases/inverted.svg) | 四篇小文档生成相机与防水的倒排列表，双列表交集只包含文档 3。 |
| 04 | [geometry.svg](../public/media/modern-databases/geometry.svg) | 点、连续折线、带空洞的多边形与线框立方体并列，说明几何类型及三维曲面与实体的差别。 |
| 04 | [scalar-space.svg](../public/media/modern-databases/scalar-space.svg) | 同一组二维点上，x 区间形成竖带；圆内红点才是半径查询结果，竖带含许多远处候选。 |
| 04 | [rtree.svg](../public/media/modern-databases/rtree.svg) | L 形多边形包围盒中的缺口产生假阳性；另一面板展示兄弟包围盒重叠导致多分支访问。 |
| 04 | [partitions.svg](../public/media/modern-databases/partitions.svg) | 二维 QuadTree 递归四分、KD-tree 按不同轴二分、三维 Octree 八分的几何对照。 |
| 04 | [spatial-knn.svg](../public/media/modern-databases/spatial-knn.svg) | 查询点到盒子最近角距离为 5，已知候选距查询点 2，因此整个盒子都可以从最近邻搜索中剪掉。 |
| 04 | [geohash.svg](../public/media/modern-databases/geohash.svg) | 经纬度二分的前缀单元边界两侧有两个很近的点，跨界半径查询必须覆盖两边再精查。 |
| 04 | [xyz.svg](../public/media/modern-databases/xyz.svg) | A 位于正上方 30 米，B 水平距查询点 5 米；二维误选 A，三维精确距离应选择 B。 |
| 05 | [graph.svg](../public/media/modern-databases/graph.svg) | 设备 A 依赖供电柜 B，B 依赖配电站 C；节点功率与边有效时间分别是不同对象的属性。 |
| 05 | [join-graph.svg](../public/media/modern-databases/join-graph.svg) | 四条 source-target 边记录与菱形邻接图表示同一关系，可通过边表索引或图邻接访问遍历。 |
| 05 | [traversal.svg](../public/media/modern-databases/traversal.svg) | A 的第一层邻居为 B、C，第二层新节点为 D、E；重复到达 D 与返回 A 的环被 visited 控制。 |
| 05 | [hubs.svg](../public/media/modern-databases/hubs.svg) | 左侧中心节点连接大量邻居，右侧列出分支数十时四跳展开的节点数，说明一跳与多跳都可能昂贵。 |
| 05 | [knowledge.svg](../public/media/modern-databases/knowledge.svg) | 设备、位置、类型和功率的三元组示例；结合显式子类规则可推导设备 A 属于设备类型。 |
| 06 | [timeline.svg](../public/media/modern-databases/timeline.svg) | 10 点进入维修区、12 点回仓库是两个点事件，维修区与仓库状态分别覆盖连续时间区间。 |
| 06 | [intervals.svg](../public/media/modern-databases/intervals.svg) | 左闭右开状态区间在 12 点相接却不重叠，而请求区间 11 到 13 与两个状态均相交。 |
| 06 | [bitemporal.svg](../public/media/modern-databases/bitemporal.svg) | 二维时间矩形保存旧认知与更正后认知：相同有效时刻 10:30，在 12:30 和 14:30 得到不同答案。 |
| 06 | [replay.svg](../public/media/modern-databases/replay.svg) | 库存从五经入库二、出库一得到六；库存七的快照允许只回放后一个事件，重复入库则出错。 |
| 06 | [retention.svg](../public/media/modern-databases/retention.svg) | 24 个测量包含一次数值 10 的尖峰，降采样到均值 1.375 后无法恢复阈值越界发生时刻。 |
| 07 | [vectors.svg](../public/media/modern-databases/vectors.svg) | 查询与两个单位向量的夹角、余弦和欧氏距离对照；A 的余弦 0.8，对应距离约 0.632。 |
| 07 | [highdim.svg](../public/media/modern-databases/highdim.svg) | 二维中心子盒保留 81% 面积，同规则在 100 维只保留约 0.0000266 的体积，数值由公式计算。 |
| 07 | [hnsw.svg](../public/media/modern-databases/hnsw.svg) | HNSW 示意图中上层只含 A、C、F，下降到完整底层后保留多个候选方向继续搜索。 |
| 07 | [ivf.svg](../public/media/modern-databases/ivf.svg) | 查询点位于左侧粗中心分区边缘，最近数据点位于第二个分区；只探测一个倒排列表会漏召回。 |
| 07 | [filter.svg](../public/media/modern-databases/filter.svg) | 全局前五对象都不满足过滤而得到空结果；正确过滤集合仍含对象 6、7、8，可在其中排序。 |
| 07 | [recall.svg](../public/media/modern-databases/recall.svg) | 精确前五与近似前五重合对象 1、2、3，按集合交集计算 Recall@5 为 0.6。 |
| 08 | [models.svg](../public/media/modern-databases/models.svg) | 对象 A 的关系字段、空间点、业务邻接、时间区间与数值向量围绕同一身份展开。 |
| 08 | [consistency.svg](../public/media/modern-databases/consistency.svg) | 主库与图投影已到版本 12，向量仍为版本 11，显示跨系统可见延迟与版本核对的必要性。 |
| 08 | [outbox.svg](../public/media/modern-databases/outbox.svg) | 对象 A 的版本 12 与 Outbox E902 在同一事务提交，异步投影通过事件身份与源版本处理重复投递。 |
| 08 | [shards.svg](../public/media/modern-databases/shards.svg) | 左侧将对象 1 到 6 拆成两个分区，右侧两个副本都保存对象 1 到 6，说明分片与复制的区别。 |
| 09 | [entities.svg](../public/media/modern-databases/entities.svg) | 六类对象的小表与园区几何对应：地点锚点、区域轮廓、路径折线和物体由事件与历史引用。 |
| 09 | [architecture.svg](../public/media/modern-databases/architecture.svg) | 关系、几何、历史和边在权威库内统一提交；对象存储保存图片，外部向量与图是可重建投影。 |
| 09 | [hybrid.svg](../public/media/modern-databases/hybrid.svg) | 左侧全局前五经空间过滤为空；右侧在区域候选 6、7、8 中评分得到对象 8 最相似。 |
| 09 | [history-query.svg](../public/media/modern-databases/history-query.svg) | 设备在 14:05 事件发生时位于区域内，18:00 已移出；连接当前位置会漏掉真实历史事件。 |
| 09 | [evolution.svg](../public/media/modern-databases/evolution.svg) | 表格将三种实际瓶颈对应到向量隔离、图投影、事件归档，并列出各自新增的一致性与恢复成本。 |
