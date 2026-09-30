"""Executable teaching checks, not performance benchmarks or external DB integration tests.
SQL uses Python's SQLite for portable relational semantics. Geometric, temporal,
ANN-filter and projection examples use independent reference computations.
"""
from pathlib import Path
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import sqlite3,tempfile,math,json
report={}
with tempfile.TemporaryDirectory(prefix='homepagex-database-') as tmp:
 path=str(Path(tmp)/'lesson.sqlite');db=sqlite3.connect(path);db.execute('PRAGMA foreign_keys=ON')
 db.executescript('''
 CREATE TABLE items(item_id INTEGER PRIMARY KEY, name TEXT NOT NULL,
 price NUMERIC NOT NULL CHECK(price>=0),available INTEGER NOT NULL CHECK(available>=0));
 CREATE TABLE customers(customer_id INTEGER PRIMARY KEY,name TEXT NOT NULL);
 CREATE TABLE rentals(rental_id INTEGER PRIMARY KEY,
 customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
 item_id INTEGER NOT NULL REFERENCES items(item_id),status TEXT NOT NULL);
 INSERT INTO items VALUES(742,'相机',120,1),(743,'支架',30,4);
 INSERT INTO customers VALUES(7,'林'),(8,'周'),(9,'陈');
 INSERT INTO rentals VALUES(101,7,742,'open'),(102,7,743,'closed'),
 (103,7,742,'closed'),(104,8,743,'closed');
 CREATE INDEX item_price ON items(price);
 CREATE TABLE receipts(request_id INTEGER PRIMARY KEY,item_id INTEGER NOT NULL REFERENCES items(item_id));
 ''')
 assert len(db.execute('SELECT * FROM customers c JOIN rentals r ON c.customer_id=r.customer_id').fetchall())==4
 assert len(db.execute('SELECT * FROM customers c LEFT JOIN rentals r ON c.customer_id=r.customer_id').fetchall())==5
 on=db.execute("SELECT c.customer_id,r.rental_id FROM customers c LEFT JOIN rentals r ON c.customer_id=r.customer_id AND r.status='open'").fetchall()
 where=db.execute("SELECT c.customer_id,r.rental_id FROM customers c LEFT JOIN rentals r ON c.customer_id=r.customer_id WHERE r.status='open'").fetchall()
 assert on==[(7,101),(8,None),(9,None)] and where==[(7,101)]
 assert db.execute('SELECT NULL = NULL, NULL IS NULL').fetchone()==(None,1)
 try:db.execute("INSERT INTO rentals VALUES(999,404,742,'open')")
 except sqlite3.IntegrityError:db.rollback()
 else:raise AssertionError('Foreign key must reject absent customer')
 assert db.execute('SELECT item_id FROM items WHERE price>=100 AND price<200 ORDER BY price,item_id').fetchall()==[(742,)]
 report['relational']={'inner_rows':4,'left_rows':5,'on_filter_rows':len(on),'where_filter_rows':len(where),'foreign_key':'rejects absent ID'}
 db.close();barrier=Barrier(2)
 def rent(request):
  c=sqlite3.connect(path,timeout=5);barrier.wait()
  with c:
   affected=c.execute('UPDATE items SET available=available-1 WHERE item_id=742 AND available>0').rowcount
   if affected:c.execute('INSERT INTO receipts VALUES(?,742)',(request,))
  c.close();return affected
 with ThreadPoolExecutor(max_workers=2) as pool:counts=list(pool.map(rent,[1,2]))
 db=sqlite3.connect(path)
 assert sorted(counts)==[0,1]
 assert db.execute('SELECT available FROM items WHERE item_id=742').fetchone()[0]==0
 assert db.execute('SELECT COUNT(*) FROM receipts').fetchone()[0]==1
 report['concurrent_inventory']={'attempts':2,'successful_rentals':1,'remaining':0,'engine':sqlite3.sqlite_version}
 # The recursive node-set query is also tested with a cycle.
 db.executescript('CREATE TABLE edges(source_id INTEGER,target_id INTEGER,kind TEXT);')
 db.executemany("INSERT INTO edges VALUES(?,?,'depends_on')",[(7,8),(7,9),(8,10),(9,10),(10,7)])
 reachable=db.execute("WITH RECURSIVE reachable(node_id) AS (SELECT 7 UNION SELECT e.target_id FROM reachable r JOIN edges e ON e.source_id=r.node_id WHERE e.kind='depends_on') SELECT node_id FROM reachable WHERE node_id<>7 ORDER BY node_id").fetchall()
 assert reachable==[(8,),(9,),(10,)];db.close()
 report['recursive_SQL']=[x[0] for x in reachable]
keys=[3,8,15,20,26,35,40,52,60]
assert [k for k in keys if 18<=k<=36]==[20,26,35]
assert [k for k in range(12) if k%4==2]==[2,6,10]
a,b='10110010','11010100';bits=''.join(str(int(x)&int(y)) for x,y in zip(a,b))
assert bits=='10010000'
postings={'相机':{1,3,4},'防水':{2,3}};assert postings['相机']&postings['防水']=={3}
report['indexes']={'range':[20,26,35],'bitmap':bits,'postings_intersection':[3]}
q=(0,0,0);a=(0,0,30);b=(3,4,0)
assert math.dist(q,a)==30 and math.dist(q,b)==5
assert math.dist(q[:2],a[:2])==0
lo=(3,4);hi=(5,6);lb=math.sqrt(sum(max(l-x,0,x-u)**2 for x,l,u in zip((0,0),lo,hi)))
assert lb==5 and lb>2
# Point (2,1) is within the L-shaped polygon's box [0,3]^2 but outside its body.
poly=[(0,0),(1,0),(1,2),(3,2),(3,3),(0,3)]
def inside(pt,polygon):
 x,y=pt;hit=False
 for (x1,y1),(x2,y2) in zip(polygon,polygon[1:]+polygon[:1]):
  if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1:hit=not hit
 return hit
assert not inside((2,1),poly) and inside((.5,1),poly)
# Spatial radius expansion after all filters matches exhaustive nearest neighbors.
points=[(i,(float(i%7),float(i//7),float(i%3))) for i in range(35)]
allowed=[p for p in points if p[0]%2==0];radius=.5;k=5
while True:
 candidates=sorted([(math.dist(q,p),i) for i,p in allowed if math.dist(q,p)<=radius])
 if len(candidates)>=k:break
 radius*=2
assert candidates[:k]==sorted((math.dist(q,p),i) for i,p in allowed)[:k]
report['spatial']={'A_3d':30,'B_3d':5,'box_lower_bound':lb,'L_shape_false_positive':True,'radius_top_k_exact':True}
contains=lambda a,b,t:a<=t<b
overlap=lambda a,b,c,d:a<d and c<b
assert not overlap(10,12,12,14) and overlap(10,12,11,13)
assert not contains(10,12,12) and contains(12,14,12)
# (valid_from, valid_to, system_from, system_to, state)
versions=[(10,math.inf,12,14,'repair'),(10,11,14,math.inf,'warehouse'),(11,math.inf,14,math.inf,'repair')]
def asof(valid,known):return [s for a,b,c,d,s in versions if contains(a,b,valid) and contains(c,d,known)]
assert asof(10.5,12.5)==['repair'] and asof(10.5,14.5)==['warehouse']
report['temporal']={'before_correction':asof(10.5,12.5),'after_correction':asof(10.5,14.5),'mean_of_spike':sum([1]*23+[10])/24}
qv=(1,0);av=(.8,.6);bv=(0,1)
assert math.isclose(math.dist(qv,av)**2,2-2*.8) and math.dist(qv,av)<math.dist(qv,bv)
assert math.isclose(.9**100,2.6561398887587544e-5)
gold={1,2,3,4,5};approx={1,2,3,8,9};assert len(gold&approx)/5==.6
# Toy IVF: nearest coarse center is left, nearest point belongs to right.
centers=[(200,257),(490,257),(800,257)];query=(338,240);nearest=(356,240)
closest=lambda p:min(range(len(centers)),key=lambda i:math.dist(p,centers[i]))
assert closest(query)==0 and closest(nearest)==1
ranked=list(range(1,9));allowed_ids={6,7,8}
assert [i for i in ranked[:5] if i in allowed_ids]==[]
assert [i for i in ranked if i in allowed_ids][:3]==[6,7,8]
report['vector']={'distance_A':math.dist(qv,av),'Recall@5':.6,'IVF_boundary_miss':True,'filtered_top3':[6,7,8]}
# Full-snapshot projection: duplicates and older updates cannot resurrect a deletion.
state={'version':0,'deleted':False};history=[]
for version,deleted in [(11,False),(12,True),(11,False),(12,True)]:
 if version>state['version']:state={'version':version,'deleted':deleted}
 history.append(dict(state))
assert state=={'version':12,'deleted':True}
shards=[[1,9,12],[2,3,20],[4,6,7]];k=3
assert sorted(x for shard in shards for x in sorted(shard)[:k])[:k]==sorted(x for shard in shards for x in shard)[:k]
report['multi_model']={'out_of_order_delete_preserved':True,'exact_shard_top_k_merge':True}
print(json.dumps(report,ensure_ascii=False,indent=2))
print('PASS: relational semantics, concurrent conditional update, recursion, index sets, geometry, history, vector/filter counterexamples, and projection ordering.')
