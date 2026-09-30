---
title: "现代数据库 04｜空间数据库：为什么附近不能只靠 XYZ 排序"
description: "从点、线、面和三维几何出发，拆解 R-tree、QuadTree、KD-tree、Octree 与 Geohash；用包围盒误命中、距离下界和楼层反例解释空间查询。"
date: 2026-09-29
tags: [数据库, 空间数据库, 空间索引, 三维几何]
---

一个城市设施平台要回答：哪些设备位于某个管理区域？哪些道路穿过施工区？离某个位置最近的设施有哪些？把坐标写进三列当然可以，但[上一种有序索引](/HomepageX/blog/modern-databases/03-indexes/)并不会因此理解“相交”与“附近”。

空间数据库不是只能存地图的另一套世界。它是在数据管理系统中加入几何类型、坐标参考、空间谓词和适合这些谓词的访问方法；例如 PostgreSQL 加 PostGIS，依然保留关系表、连接与事务。

## 1. 首先定义：我们究竟在测量什么？

### 1.1 Point、LineString、Polygon 与三维几何

<!-- figure:geometry:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/geometry.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/geometry.svg" alt="点、连续折线、带空洞的多边形与线框立方体并列，说明几何类型及三维曲面与实体的差别。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 1 · 点、连续折线、带空洞的多边形与线框立方体并列，说明几何类型及三维曲面与实体的差别。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:geometry:end -->

Point 表示点位置；LineString 由有顺序的顶点组成折线，不是无限延长的数学直线；Polygon 由外环与可选内环围成区域，内环表示洞。跨越两条道路的折线与只看道路端点，查询含义不同；落在多边形洞里的点，也不属于区域内部。

三维几何可以是带 Z 的点或折线，也可以是曲面、三角网或有明确实体语义的体。**给 Polygon 的顶点加 Z，不会自动获得任意实体体积、内部判定和三维布尔运算能力。** 支持存储某种类型，也不意味着所有函数都利用它的全部维度。[PostGIS 数据模型](https://postgis.net/docs/using_postgis_dbmanagement.html)列出了类型、有效性和索引约定。

### 1.2 坐标系与单位是查询正确性的前提

平面工程坐标可能以米计，经纬度通常以角度计。经度差一度在不同纬度对应不同距离，不能把经纬度直接当米做欧氏距离。大范围地理问题要考虑球面或椭球面；局部 XYZ 则要记录原点、轴方向、单位和垂直基准。

对于共同局部直角坐标系里的两个点，三维欧氏距离为：

$$
d(\mathbf p,\mathbf q)=\sqrt{(p_x-q_x)^2+(p_y-q_y)^2+(p_z-q_z)^2}.
$$

若各轴单位都是米，结果才是米。设置 SRID 标签只是声明坐标系；坐标转换需要真正的变换，不能靠换标签完成。不同园区的局部坐标即使同为 `(10, 20, 3)`，也不是同一个地点。

## 2. 为什么三个普通 B-tree 不够自然？

<!-- figure:scalar-space:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/scalar-space.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/scalar-space.svg" alt="同一组二维点上，x 区间形成竖带；圆内红点才是半径查询结果，竖带含许多远处候选。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 2 · 同一组二维点上，x 区间形成竖带；圆内红点才是半径查询结果，竖带含许多远处候选。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:scalar-space:end -->

要找圆内的点，可以先过滤 `x` 和 `y` 的区间。但单列 `x` 索引拿到的是一条竖带，里面可能绝大多数点离查询位置很远。组合 `(x, y)` 按字典序排列，一块二维矩形也未必对应一个紧凑的一维区间。

多个索引求交、空间编码加 B-tree 都可能有效；这里的问题不是“普通数据库做不到”，而是**一维次序没有直接保存二维或三维邻近性**。稀疏范围和最近邻要有能同时利用多个维度的剪枝依据。

更复杂的是区域相交：不能只取多边形中心点。一个很长的区域可能中心很远、边缘却与施工区相交；用中心点替代几何，会产生真正的漏检。

## 3. R-tree：把附近的几何包进层层矩形

### 3.1 内部节点保存的是覆盖范围

<!-- figure:rtree:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/rtree.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/rtree.svg" alt="L 形多边形包围盒中的缺口产生假阳性；另一面板展示兄弟包围盒重叠导致多分支访问。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 3 · L 形多边形包围盒中的缺口产生假阳性；另一面板展示兄弟包围盒重叠导致多分支访问。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:rtree:end -->

R-tree 的叶项保存对象的最小轴对齐包围矩形 MBR 与对象标识；内部项保存覆盖子树的包围矩形。三维推广对应包围盒。查询范围与某个内部包围盒都不相交时，子树内对象更不可能相交，可以整支跳过。

与 B+ tree 的键区间不同，兄弟包围盒可以重叠。查询可能进入多条分支；因此不能把 R-tree 一概描述为“每次对数复杂度”。长条对象、密集重叠或高维数据都会削弱剪枝。

### 3.2 命中包围盒之后，为什么还要精查？

图中的 L 形区域包围盒覆盖了空白缺口。查询点落在缺口里，会通过包围盒测试，却不属于真实区域。这是允许出现的假阳性：粗筛保留候选，精确几何谓词把它排除。

正确的索引粗筛必须是实际答案的超集。包围盒不能随意缩小到丢掉细长边缘。PostGIS 常用 GiST 框架组织这种空间访问；**GiST 是可扩展索引框架，不是另一种特定几何形状**。两阶段查询可参阅 [PostGIS 空间索引教程](https://postgis.net/workshops/postgis-intro/indexing.html)。

### 3.3 写入时在优化什么？

插入一个新对象，要选择适合容纳它的子节点，例如尽量少扩大包围范围；节点满后分裂，目标之一是降低包围盒重叠。不同变体还优化面积、周长和重叠等指标。分布变化后，批量重建有时比长期零散插入产生更好的结构，但也增加维护成本。

## 4. QuadTree、KD-tree、Octree：切空间的三种方法

<!-- figure:partitions:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/partitions.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/partitions.svg" alt="二维 QuadTree 递归四分、KD-tree 按不同轴二分、三维 Octree 八分的几何对照。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 4 · 二维 QuadTree 递归四分、KD-tree 按不同轴二分、三维 Octree 八分的几何对照。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:partitions:end -->

### 4.1 QuadTree：二维区域递归四等分

从一个正方形或矩形区域开始，每层沿两轴分成四个子区；密集区域继续细分，稀疏区域保持粗粒度。查矩形范围时，访问与查询重叠的格子；画地图分块、做二维空间聚合很自然。

无限重合的点不能靠无限细分解决，应设置最大深度或叶容量。跨多个格子的面对象需要选择重复引用、保留在较高层等策略，并在查询时去重；点的处理不能直接照搬到大多边形。

### 4.2 KD-tree：根据点分布沿一根轴二分

KD-tree 每个内部节点选择一根轴与切分值，把点集分到两侧。经典构造可轮流选择轴并按中位数切分，使点数较平衡；不同实现的轴选择与切分规则会变化。

低维静态点集的范围查找和近邻查询很合适。动态插入可能破坏平衡；维度增加时，查询球与许多子区都相交，递归访问接近全扫描。[SciPy KDTree 文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.KDTree.html)也明确提醒不要期待高维一定快于暴力搜索。

### 4.3 Octree：三维区域递归八等分

Octree 沿三轴二分，每个节点最多八个子块，是三维体素分块、层级分辨率和稀疏空间组织的常见结构。它保留“哪个空间块包含哪些对象”的层级，但不自动提供数据库事务、持久化或 SQL。

三者共同点是空间分区；差别在切分规则、数据分布适应性、对象跨边界时的处理，以及更新成本。R-tree 更偏向按对象范围分组，QuadTree 与 Octree 更偏向按空间分块。

## 5. 最近邻：关键是找到可证明的距离下界

<!-- figure:spatial-knn:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/spatial-knn.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/spatial-knn.svg" alt="查询点到盒子最近角距离为 5，已知候选距查询点 2，因此整个盒子都可以从最近邻搜索中剪掉。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 5 · 查询点到盒子最近角距离为 5，已知候选距查询点 2，因此整个盒子都可以从最近邻搜索中剪掉。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:spatial-knn:end -->

对一个轴对齐盒子 $B=\prod_{j=1}^{d}[l_j,u_j]$，查询点 $\mathbf q$ 到盒子的最小可能距离为：

$$
d_{\min}(\mathbf q,B)=\sqrt{\sum_{j=1}^{d}\max(l_j-q_j,\,0,\,q_j-u_j)^2}.
$$

每一维上，点若位于区间内，贡献为 0；位于外部就取离最近边界的距离。例如查询点为 `(0,0)`，盒子为 `[3,5] × [4,6]`，下界是 $\sqrt{3^2+4^2}=5$。已知一个真实候选距查询点仅 2 米，那么这个盒子不可能改善当前最近结果。

精确 top-k 搜索可以用优先队列，按盒子下界从小到大展开；维护目前 k 个最好对象及第 k 名的真实距离。当所有未访问节点的下界都不小于这个距离时，才有停止依据。若需要保留所有并列距离，还要按并列策略处理等号。

这是一种可证明的剪枝逻辑。只搜查询点所在格子、只取固定数量的邻格或固定数量的近邻候选，都没有自动获得同样的完整性保证。

## 6. Geohash：把空间单元编码成可排序的字符串

<!-- figure:geohash:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/geohash.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/geohash.svg" alt="经纬度二分的前缀单元边界两侧有两个很近的点，跨界半径查询必须覆盖两边再精查。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 6 · 经纬度二分的前缀单元边界两侧有两个很近的点，跨界半径查询必须覆盖两边再精查。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:geohash:end -->

Geohash 交替细分经度与纬度范围，把区间选择编码成位，再按每 5 位编码为字符。较长的共同前缀通常表示同属一个较小单元，适合按前缀组织存储、缓存和粗筛。[Redis GEOADD 文档](https://redis.io/docs/latest/commands/geoadd/)解释了地理编码与有序集合的结合。

但图中边界两侧两个非常近的点，可能没有长共同前缀。查半径必须覆盖相交单元，再计算真实距离；不能只查一个前缀。查询范围变大时，也要动态选择编码精度并覆盖足够多的格子，而不是永远取固定九宫格。

Geohash 单元不是面积恒定的正方形，纬度和编码精度会影响形状；它也不是天然的 XYZ 三维索引。把编码映射到 B-tree 是空间技术与传统数据库协作的一个例子，而非二者互斥。

## 7. 真正的 XYZ 查询：别让楼上对象变成零距离

<!-- figure:xyz:start -->
<figure>
  <a href="/HomepageX/media/modern-databases/xyz.svg" target="_blank" rel="noopener"><img src="/HomepageX/media/modern-databases/xyz.svg" alt="A 位于正上方 30 米，B 水平距查询点 5 米；二维误选 A，三维精确距离应选择 B。" width="1000" height="500" loading="lazy" /></a>
  <figcaption>自制图 7 · A 位于正上方 30 米，B 水平距查询点 5 米；二维误选 A，三维精确距离应选择 B。 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:xyz:end -->

查询点为 `(0,0,0)`，A 为 `(0,0,30)`，B 为 `(3,4,0)`。二维距离认为 A 为 0、B 为 5；三维距离则认为 A 为 30、B 为 5。只做二维近邻再截取少量候选，可能把真正的三维近邻 B 排除。

PostGIS 的 `geometry <-> geometry` 是二维距离排序操作符，不能直接宣传成三维 KNN。三维半径查询可使用 `ST_3DDWithin`，并为相应访问方式建立 n-D 索引：

```sql
CREATE INDEX objects_position_nd
ON objects USING gist (position gist_geometry_ops_nd);

SELECT object_id,
       ST_3DDistance(position, :query_point) AS distance_m
FROM objects
WHERE ST_3DDWithin(position, :query_point, :radius_m)
ORDER BY distance_m, object_id;
```

这是 PostGIS 查询模板，冒号参数由应用绑定。前提是所有点采用相同的局部米制坐标约定，查询函数与索引操作符类配套。它得到半径内完整候选，再按真实三维距离排序；不是无界 top-k 的现成保证。函数细节见 [ST_3DDWithin](https://postgis.net/docs/ST_3DDWithin.html)和[二维 KNN 操作符](https://postgis.net/docs/geometry_distance_knn.html)。

要得到全局最近 k 个点，可以逐步扩大半径：当半径内已有 k 个有效对象，且第 k 个距离不超过当前半径时，所有半径外对象都不更近。在同一数据快照与坐标空间内，这才有明确终止证明。第 9 篇会把过滤、权限与这一流程放在一起。

## 8. 空间索引加速的是候选排除

建模前先回答四件事：对象是什么几何，距离是什么单位，查询是相交／包含／半径／最近邻中的哪一种，结果是否要求精确完整。再选择包围盒树、点分割、空间格网或编码。

练习：一条公路与查询圆相交，但两个端点都在圆外，能否仅索引端点后判断“没有公路”？不能。索引对象必须保守覆盖所查询的实际几何。

下一篇从空间邻近转向关系邻接：[图数据库：当问题变成沿着关系继续找](/HomepageX/blog/modern-databases/05-graph/)。
