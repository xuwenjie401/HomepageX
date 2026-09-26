"""Deterministic teaching figures; no model outputs or benchmark measurements.
Run from the repo root, then `node scripts/vision-series/typeset.mjs`.
All curves, projections, probabilities and matrix entries are computed below.
"""
from pathlib import Path
from html import escape
import math,json
import numpy as np
ROOT=Path(__file__).resolve().parents[2]; META={}
BLUE='#2563a6';RED='#ce593e';GREEN='#267a65';GRAY='#778396';GOLD='#b78c2c';INK='#213047';LIGHT='#eef3f7'
class SVG:
 def __init__(self,title,w=1100,h=470):
  self.w,self.h=w,h;self.a=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="white"/><defs><marker id="arr" markerWidth="9" markerHeight="9" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="context-stroke"/></marker></defs>'];self.text(35,38,title,25)
 def text(self,x,y,s,size=20,color=INK,anchor='start'):self.a.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-family="Noto Sans CJK SC,Microsoft YaHei,sans-serif">{escape(str(s))}</text>')
 def line(self,x1,y1,x2,y2,color=GRAY,width=2,dash=False,arrow=False):self.a.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"'+(' stroke-dasharray="7 5"' if dash else '')+(' marker-end="url(#arr)"' if arrow else '')+'/>')
 def rect(self,x,y,w,h,fill=LIGHT,stroke='none',r=0):self.a.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
 def circ(self,x,y,r=7,fill=BLUE,stroke='none'):self.a.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
 def path(self,pts,color=BLUE,width=3,fill='none',close=False,dash=False):self.a.append('<path d="'+' '.join(('M' if i==0 else 'L')+f'{x:.2f},{y:.2f}' for i,(x,y) in enumerate(pts))+(' Z' if close else '')+f'" fill="{fill}" stroke="{color}" stroke-width="{width}"'+(' stroke-dasharray="7 5"' if dash else '')+'/>')
 def axes(self,x,y,w,h,xlabel='',ylabel=''):
  self.line(x,y,x+w,y,INK,arrow=True);self.line(x,y,x,y-h,INK,arrow=True)
  self.text(x+w-8,y+28,xlabel,18,anchor='end');self.text(x+4,y-h-10,ylabel,18)
 def matrix(self,arr,x,y,cell=55,rows=None,cols=None,fmt='.2g'):
  a=np.array(arr);mx=max(abs(a).max(),1)
  for i,row in enumerate(a):
   for j,v in enumerate(row):
    alpha=abs(v)/mx
    self.rect(x+j*cell,y+i*cell,cell-2,cell-2,f'rgb({int(242-125*alpha)},{int(247-83*alpha)},{int(251-35*alpha)})')
    self.text(x+j*cell+cell/2,y+i*cell+cell*.65,'$'+format(v,fmt)+'$',19,INK,'middle')
  if rows:
   for i,s in enumerate(rows):self.text(x-12,y+i*cell+cell*.63,s,19,anchor='end')
  if cols:
   for j,s in enumerate(cols):self.text(x+j*cell+cell/2,y-14,s,19,anchor='middle')
 def grid(self,x,y,n=6,m=5,s=25,mask=()):
  for i in range(m):
   for j in range(n):self.rect(x+j*s,y+i*s,s-2,s-2,GRAY if (i,j) in mask else [LIGHT,'#d8e7f0','#b9d5e5'][(i+j)%3])
 def graph(self,pts,edges,color=BLUE,fixed=()):
  for i,j in edges:self.line(*pts[i],*pts[j],GRAY)
  for i,(x,y) in enumerate(pts):
   if i in fixed:self.rect(x-10,y-10,20,20,'white',INK)
   else:self.circ(x,y,10,color)
   self.text(x,y+33,str(i),17,anchor='middle')
 def save(self,slug,name,caption):
  p=ROOT/'public/media'/slug;p.mkdir(parents=True,exist_ok=True)
  (p/(name+'.svg')).write_text(''.join(self.a)+'</svg>')
  META[name]={'article':slug,'width':self.w,'height':self.h,'caption':caption}
def curve(s,x,y,w,h,fn,a,b,color=BLUE):s.path([(x+(t-a)/(b-a)*w,y-fn(t)*h) for t in np.linspace(a,b,180)],color)
def corners(s,x,y,scale=1):
 s.rect(x,y,120*scale,120*scale,'#e6e9ec');s.rect(x+55*scale,y,65*scale,65*scale,'#596c81');s.circ(x+55*scale,y+65*scale,6,RED)
# 01: conditioning, update, pyramid, histogram
s=SVG('同样的像素噪声，在不同方向上产生不同的位置不确定性')
for k,(vals,title) in enumerate([((.2,.2),'(a) 平坦：两个方向都弱'),((8,.2),'(b) 直边：沿边方向弱'),((8,6),'(c) 角点：两个方向都有约束')]):
 x=185+k*355;s.text(x,76,title,19,anchor='middle');s.line(x-148,225,x+148,225,GRAY,arrow=True);s.line(x,370,x,104,GRAY,arrow=True);s.text(x+145,254,r'$\delta x$',18,anchor='end');s.text(x+8,123,r'$\delta y$',18)
 for a in [1,1.5,2]:
  pts=[(x+a*30/math.sqrt(vals[0])*math.cos(t),225+a*30/math.sqrt(vals[1])*math.sin(t)) for t in np.linspace(0,2*math.pi,100)]
  s.path(pts,BLUE,2)
 s.text(x,397,f'$\\lambda_1={vals[0]},\\;\\lambda_2={vals[1]}$',21,anchor='middle')
s.save('gftt-klt-sift','gftt-conditioning','按二次误差计算的等高线。平坦区两方向都不确定，直边有长而窄的谷，角点形成可定位的盆地。')
s=SVG('LK 一次更新：所有梯度共同投票给同一个二维位移')
s.matrix([[2,1],[1,2]],85,150,70,cols=['$x$','$y$']);s.text(90,120,'$G=J^{\\mathsf T}J$',23)
s.text(285,237,'$\\Delta\\mathbf u=$',25);s.matrix([[5],[4]],465,150,70);s.text(475,120,'$-J^{\\mathsf T}r$',23)
s.axes(710,350,270,220,'$u_x$','$u_y$');s.line(710,350,890,260,RED,4,arrow=True);s.circ(890,260,8,RED);s.text(885,235,'$(2,1)$',25)
s.text(45,420,'把右端的亮度差投影到梯度方向；求解结果要同时满足横向与纵向证据。',23)
s.save('gftt-klt-sift','klt-update','数值例子的正规方程：G 乘以 (2,1) 得到 (5,4)，更新方向由残差符号和梯度共同决定。')
s=SVG('图像金字塔把大位移变成粗尺度的小位移')
for i,sc in enumerate([.25,.5,1]):
 x=70+i*340;corners(s,x,150,sc);s.line(x+40,y1:=320,x+40+96*sc,320,RED,3,arrow=True);s.text(x,365,['粗层：3 像素','中层：6 像素','原图：12 像素'][i],22)
 if i<2:s.line(x+150,205,x+265,205,BLUE,3,arrow=True);s.text(x+160,178,'× 2 + 修正',18)
s.save('gftt-klt-sift','klt-pyramid','教学示意：原图 12 像素位移在两次二倍下采样后为 3 像素，逐层放大估计并优化残差。')
s=SVG('SIFT 把局部梯度转成带空间布局的方向直方图')
for i in range(4):
 for j in range(4):
  x=70+j*65;y=115+i*65;s.rect(x,y,62,62,LIGHT)
  for a in range(3):s.line(x+10+a*16,y+45,x+22+a*13,y+18,BLUE,2,arrow=True)
s.line(365,240,465,240,GRAY,3,arrow=True)
for i in range(4):
 for j in range(4):
  x=515+j*125;y=125+i*60
  for k in range(8):s.rect(x+k*12,y+35-[5,10,24,33,22,11,7,4][(k+i+j)%8],9,[5,10,24,33,22,11,7,4][(k+i+j)%8],BLUE)
s.text(85,421,'$4\\times4$ 个空间单元',23);s.text(565,421,'每单元 8 个方向 → 128 维',23)
s.save('gftt-klt-sift','sift-histogram','示意梯度投票的空间布局；箭头与柱高是教学输入，展示 4×4×8 的组织方式，不是某张实测图的描述子。')
# Matching diagrams
s=SVG('重复窗格的局部外观相似，上下文提供额外关系')
for off in [65,610]:
 for i in range(3):
  for j in range(4):s.rect(off+j*75,110+i*77,45,45,'#dce8ef',BLUE);s.circ(off+j*75+22,132+i*77,4,RED)
s.rect(65,285,45,22,GOLD);s.rect(610,285,45,22,GOLD)
for j in range(4):s.line(237,209,632+j*75,209,RED,1,dash=True)
s.line(87,300,632,300,GREEN,3,arrow=True)
s.text(65,398,'局部：多个候选外观近似',23);s.text(610,398,'上下文：门的位置帮助消歧',23)
s.save('superglue-lightglue','matching-context','重复窗格产生一对多歧义；稳定邻域关系提供附加证据，但没有可区分结构时上下文也会失败。')
s=SVG('SuperGlue 的 dustbin 允许未匹配，同时满足扩展边缘质量')
s.matrix([[1,0,0],[0,1,0],[0,0,1],[0,0,2]],180,125,64,rows=['$a_1$','$a_2$','$a_3$','空槽'],cols=['$b_1$','$b_2$','空槽'])
for i,v in enumerate([1,1,1,2]):s.text(412,169+64*i,'→ '+str(v),22)
s.text(201,420,'列和： 1       1       3',22)
s.text(565,155,'真实点每行 / 列质量为 1',25);s.text(565,220,'$M=3,\\quad N=2$',26);s.text(565,280,'空行质量 $N$；空列质量 $M$',23);s.text(565,342,'右下角质量不是真实匹配',23)
s.save('superglue-lightglue','matching-dustbin','一个满足 SuperGlue 扩展边缘约束的硬分配极限：a3 未匹配，空槽之间的质量用于平衡矩阵。')
s=SVG('几何标签先建立对应，匹配网络再为这些标签分配概率')
s.matrix([[.8,.1,.1],[.15,.7,.15],[.1,.1,.8]],100,130,70,rows=['$a_1$','$a_2$','$a_3$'],cols=['$b_1$','$b_2$','空槽'])
for i in range(3):s.rect(100+70*i,130+70*i,68,68,'none',GREEN)
s.text(470,170,'正确标签：$a_1\\leftrightarrow b_1$，$a_2\\leftrightarrow b_2$',23);s.text(470,235,'$a_3$ 在另一图不可见 → 空槽',23);s.text(470,310,'$-\\log(0.8)-\\log(0.7)-\\log(0.8)$',25);s.text(470,365,'正确项概率越高，负对数越小',22)
s.save('superglue-lightglue','matching-supervision','教学概率矩阵展示标签与负对数监督；这些示意概率不代表 Sinkhorn 完整扩展矩阵。')
s=SVG('LightGlue：可匹配性决定匹配，置信度决定是否继续计算')
pts=[(120+i*80,155) for i in range(10)]
for i,(x,y) in enumerate(pts):s.circ(x,y,13,BLUE if i%3 else RED);s.text(x,y-25,str(i),18,anchor='middle')
s.text(55,98,'第 $l$ 层',22)
for i,(x,y) in enumerate(pts):
 if i in [0,3,6]:s.line(x,y+30,x,y+95,RED,2);s.line(x-9,y+85,x+9,y+103,RED,3);s.line(x-9,y+103,x+9,y+85,RED,3)
 else:s.line(x,y+30,x,300,BLUE,2,arrow=True);s.circ(x,315,13,BLUE)
s.text(70,400,'剪除：已确信不可匹配的点',22,RED);s.text(555,400,'继续：可匹配或仍不确定的点',22,BLUE)
s.save('superglue-lightglue','lightglue-pruning','点剪枝并非直接删掉低匹配分数点；应结合对最终判断的置信度，防止过早删除尚未消歧的点。')
# Retrieval
s=SVG('定位是逐步收缩候选空间，再用几何恢复相机位姿')
for i in range(24):s.rect(55+(i%6)*45,115+(i//6)*50,35,35,BLUE if i in [2,8,15] else LIGHT)
s.line(355,215,435,215,GRAY,3,arrow=True)
for i in range(3):s.rect(480,100+i*88,125,60,'#dae8f0',BLUE);s.text(495,139+i*88,f'候选 {i+1}',19)
s.line(640,215,710,215,GRAY,3,arrow=True)
for i,(x,y) in enumerate([(790,150),(950,120),(940,320),(760,300)]):s.circ(x,y,7,GREEN);s.line(850,260,x,y,GREEN)
s.path([(830,280),(875,280),(855,245)],BLUE,3,close=True);s.text(770,385,'2D–3D 对应 → PnP',23)
s.save('netvlad-hfnet','localization-hierarchy','全局检索缩小数据库范围，局部对应连接三维地图，最后几何估计输出位姿。')
s=SVG('VLAD 聚合的是到簇中心的残差，而不是只数落入多少点')
for off,c in [(90,BLUE),(600,RED)]:
 s.axes(off,345,330,235,'特征维度 1','特征维度 2');s.circ(off+140,220,11,GOLD);s.text(off+120,195,'$c_k$',23)
 for x,y in ([(90,145),(190,130),(235,245),(70,270)] if c==BLUE else [(180,145),(250,165),(275,245),(185,270)]):s.circ(off+x,y,6,c);s.line(off+140,220,off+x,y,c,2,arrow=True)
 s.text(off+20,405,'相同点数，残差方向可以不同',21)
s.save('netvlad-hfnet','vlad-residuals','两簇各有四个局部特征，VLAD 保留位置相对中心的残差信息；软分配版本再用归属概率加权。')
s=SVG('弱地理标签：附近图像里只需有一个真正共享视野的正样本')
s.circ(180,220,90,'#e5f0e9');s.circ(180,220,10,BLUE);s.text(160,200,'query',21)
for x,y in [(135,160),(235,190),(200,290)]:s.circ(x,y,9,GREEN);s.line(180,220,x,y,GREEN,2)
for x,y in [(490,150),(620,285),(870,175)]:s.circ(x,y,10,RED);s.text(x,y-22,'negative',19,anchor='middle')
s.text(65,390,'正候选集合：取当前最相似者',23);s.text(560,390,'负样本必须被拉开间隔',23)
s.save('netvlad-hfnet','retrieval-supervision','NetVLAD 的弱监督不把所有 GPS 邻近照片都视作必然正对；视角不重叠的近邻可能不适合作为正样本。')
s=SVG('HF-Net 蒸馏：三个输出接受各自教师的监督')
s.grid(65,160,5,4,32)
for y,title,c in [(115,'全局向量',BLUE),(240,'局部描述',GREEN),(365,'检测分数',RED)]:
 s.line(250,225,440,y,c,3,arrow=True)
 if y==115:
  for i,v in enumerate([25,52,31,62,40,20]):s.rect(475+i*22,y-v/2,15,v,c)
 elif y==240:s.matrix([[.2,.8,.1],[.7,.1,.4]],475,y-35,40)
 else:
  for x in [490,545,600]:s.circ(x,y,9,c)
 s.text(670,y+8,title,24,c);s.line(955,y,820,y,c,2,dash=True,arrow=True);s.text(1030,y+8,'教师',21,anchor='end')
s.save('netvlad-hfnet','hfnet-distillation','共享骨干服务三个不同粒度的输出；虚线表示训练监督，推理只运行学生网络。')
s=SVG('检索靠外观，相机候选分组还要靠共同三维点')
pts=[(140,155),(270,115),(360,240),(150,300),(690,140),(825,210),(930,135)]
s.graph(pts,[(0,1),(1,2),(2,3),(0,3),(4,5),(5,6)],fixed=())
for x,y in [(240,210),(795,300)]:
 s.path([(x,y-12),(x+12,y+8),(x-12,y+8)],GREEN,2,fill=GREEN,close=True)
 for px,py in (pts[:4] if x==240 else pts[4:]):s.line(x,y,px,py,GREEN,1,dash=True)
s.text(75,410,'候选组 A：共同地标把图像连接起来',22);s.text(670,410,'候选组 B：另一处结构',22)
s.save('netvlad-hfnet','covisibility-retrieval','共视聚类把检索出的图像按地图连接分组，防止将外观相似但空间不同的候选混入同一次位姿估计。')
# DINO
s=SVG('一个 ViT 输出既有全图 token，也有保留网格位置的 patch token')
s.grid(60,110,6,5,42);s.line(355,215,445,215,GRAY,3,arrow=True)
s.rect(490,100,40,40,GOLD);s.text(552,130,'CLS：整图表示',24)
s.grid(490,180,6,5,31);s.text(760,260,'Patch：空间网格',24);s.text(490,402,'同一图像，不同输出承担不同下游任务',22)
s.save('dinov2-dinov3','dino-tokens','CLS 聚合全局信息，patch token 保留空间索引；有空间索引并不意味着已经达到像素级几何定位精度。')
s=SVG('教师给出目标分布；学生跨视图预测；教师由 EMA 缓慢更新')
s.grid(55,160,5,4,30);s.grid(350,110,4,4,25);s.grid(350,285,3,3,25)
s.line(235,210,330,155,GRAY,2,arrow=True);s.line(235,220,330,320,GRAY,2,arrow=True)
for x,y,vals,c in [(620,110,[.05,.8,.1,.05],GREEN),(620,285,[.1,.6,.2,.1],BLUE)]:
 for j,v in enumerate(vals):s.rect(x+j*40,y+90-v*100,28,v*100,c)
s.text(465,82,'教师 / stop-gradient',22,GREEN);s.text(460,410,'学生 / 梯度更新',22,BLUE);s.line(865,300,865,160,RED,2,arrow=True);s.text(892,245,'EMA',22,RED)
s.save('dinov2-dinov3','dino-teacher','两个视图的分布对齐通过学生反传，教师参数缓慢跟随学生；EMA 路径不等同于对目标概率直接求梯度。')
s=SVG('防坍塌要同时关注：每个样本的预测，与整个批次的使用分布')
s.matrix([[1,0,0],[1,0,0],[1,0,0]],95,130,62);s.text(70,365,'都选择同一个原型',23,RED)
s.matrix([[.33,.33,.34]]*3,425,130,62);s.text(410,365,'每个样本都均匀',23,GOLD)
s.matrix([[.9,.05,.05],[.05,.9,.05],[.05,.05,.9]],755,130,62);s.text(735,365,'单样本清晰，批次多样',23,GREEN)
s.save('dinov2-dinov3','dino-collapse','三种教学分布：全部占用一个原型与全部均匀都可能退化；温度、批次平衡和特征分散约束承担不同角色。')
s=SVG('iBOT：学生看被遮挡的网格，教师给相同位置的目标')
s.grid(95,135,6,5,42,mask={(1,2),(2,2),(2,3),(3,4)});s.grid(655,135,6,5,42)
for i,j in [(1,2),(2,2),(2,3),(3,4)]:s.line(655+j*42+20,135+i*42+20,95+j*42+20,135+i*42+20,GREEN,1,dash=True,arrow=True)
s.text(95,408,'学生：mask token 替换输入 patch',22);s.text(655,408,'教师：对应未遮挡视图',22)
s.save('dinov2-dinov3','dino-masking','虚线只连接同一裁剪坐标中的被遮挡位置；patch 目标与跨不同裁剪的 CLS 目标不能混为一项。')
s=SVG('Gram anchoring 对齐 token 之间的关系，不强迫特征坐标轴相同')
a=np.array([[1,0],[0,1],[1/math.sqrt(2),1/math.sqrt(2)]]);q=np.array([[0,-1],[1,0]]);gram=a@a.T
s.matrix(a,65,145,60);s.text(65,120,'$X$',25);s.matrix(a@q,335,145,60);s.text(335,120,'$XQ$',25)
s.matrix(gram,680,135,65);s.text(635,405,'$XX^{\\mathsf T}=(XQ)(XQ)^{\\mathsf T}$',25)
s.line(220,235,300,235,GRAY,2,arrow=True);s.text(235,195,'旋转',20);s.line(490,235,615,235,GRAY,2,arrow=True)
s.save('dinov2-dinov3','dino-gram','三个单位 token 的数值例子：共同正交旋转改变特征坐标，却不改变 token–token Gram 矩阵。')
# Foundation models
s=SVG('下游任务不同，应该保留的信息粒度也不同')
for j,title in enumerate(['地点检索','独立稀疏特征','图像对稠密匹配']):
 x=65+j*360;s.text(x,100,title,25);s.grid(x,135,6,4,30)
 if j==0:
  for k,h in enumerate([30,60,42,75,25,48]):s.rect(x+10+k*26,355-h,17,h,BLUE)
 elif j==1:
  for xx,yy in [(25,35),(90,75),(140,28)]:s.circ(x+xx,145+yy,7,RED);s.line(x+xx,260,x+xx,350,BLUE,2)
 else:
  for k in range(8):s.line(x+20+k*18,265,x+10+k*21,350,GREEN,2)
s.text(65,415,'每图一个向量',22);s.text(425,415,'点 + 可缓存描述子',22);s.text(785,415,'依赖双方的对应场',22)
s.save('foundation-model-vpr-features','foundation-task-map','基础模型特征可以服务三个不同接口；全局检索、独立局部描述和成对匹配的计算与缓存成本不同。')
s=SVG('SALAD：每个真实簇接收固定质量，剩余质量进入 dustbin')
a=[[.8,.2,0],[.2,.7,.1],[0,.1,.9],[0,0,1]];s.matrix(a,110,135,63,cols=['簇 1','簇 2','空槽'],rows=['1','2','3','4']);s.text(90,425,'列和 $(1,1,2)$；行和均为 1',22)
s.text(520,150,'4 个 token → 2 个真实簇',25);s.text(520,230,'每簇按分配权重汇聚特征',23);s.text(520,305,'$v_k=\\sum_i P_{ik}f_i$',27);s.text(520,382,'没有减去簇中心这一项',22,RED)
s.save('foundation-model-vpr-features','salad-transport','数值矩阵满足 SALAD 的容量直觉。与 NetVLAD 不同，SALAD 对降维后的特征加权求和，不聚合到中心的残差。')
s=SVG('语义告诉我们是哪类区域；几何还要知道落在区域的哪一点')
s.grid(70,130,8,6,32);s.rect(134,162,128,96,'#bcd8cb',GREEN);s.circ(205,210,35,'none',GREEN)
corners(s,585,130,1.7);s.line(440,220,540,220,GRAY,3,arrow=True);s.circ(678.5,240.5,8,RED)
s.text(65,395,'粗网格：同一窗户具有相似语义',23);s.text(585,395,'细结构：窗角需要精确落点',23)
s.save('foundation-model-vpr-features','sparse-semantic-local','粗语义特征与局部高分辨率结构互补；插值只能增加采样密度，不能凭空恢复骨干未保留的定位信息。')
s=SVG('RoMa：粗匹配的多个可能位置，不应该先平均成一个错误位置')
s.axes(75,360,405,250,'目标坐标','概率密度');curve(s,75,360,390,230,lambda x:.8*math.exp(-(x+1.4)**2/.18)+.8*math.exp(-(x-1.4)**2/.18),-3,3)
s.line(270,350,270,160,RED,2,dash=True);s.text(270,130,'均值落在空处',21,RED,'middle')
s.axes(630,360,370,250,'局部偏移','细化概率');curve(s,630,360,350,230,lambda x:.9*math.exp(-x*x/.3),-3,3,GREEN)
s.text(90,420,'粗层保留多个候选模式',23);s.text(665,420,'选定区域后再局部回归',23)
s.save('foundation-model-vpr-features','roma-multimodal','按高斯混合计算的教学曲线：双峰分布的均值不一定对应真实匹配，解释粗分类与细回归分工。')
# TartanAir
s=SVG('在同一个障碍地图上，改变轨迹就能改变运动难度')
for off in [60,600]:
 s.rect(off,100,420,265,LIGHT,GRAY)
 for xx,yy,w,h in [(60,45,80,75),(210,120,85,100),(320,40,65,60)]:s.rect(off+xx,100+yy,w,h,'#b6c4cf')
s.path([(90,330),(220,330),(255,220),(365,200),(455,240)],BLUE,4)
s.path([(630,330),(740,270),(765,135),(805,120),(885,190),(925,295),(980,330)],RED,4)
for x,y,ang in [(735,270,-.6),(805,120,.2),(925,295,.9)]:s.line(x,y,x+35*math.cos(ang),y+35*math.sin(ang),GREEN,3,arrow=True)
s.text(70,420,'路径覆盖：去过哪些地方',23);s.text(610,420,'姿态变化：相机朝哪里、怎样转动',23)
s.save('tartanair','tartan-paths','二维教学地图展示路径与朝向是两类设计变量；避障路径本身不保证真实机器人能够满足动力学约束。')
s=SVG('从深度和相对位姿生成对应：先到三维，再投到另一幅图')
s.circ(230,340,12,BLUE);s.circ(760,340,12,GREEN);s.circ(500,105,11,RED)
s.line(230,340,500,105,BLUE,3);s.line(760,340,500,105,GREEN,3);s.line(230,340,760,340,GRAY,2,arrow=True)
s.line(155,245,350,245,BLUE,4);s.line(640,245,835,245,GREEN,4);s.circ(339,245,7,BLUE);s.circ(655,245,7,GREEN)
s.text(125,405,'相机 A / 已知深度',24);s.text(695,405,'相机 B / 投影',24);s.text(480,80,'$P$',26);s.text(445,322,'$T_{BA}$',26)
s.save('tartanair','tartan-reprojection','教学几何示意：相机 A 的像素沿射线恢复三维点，通过相对位姿投到 B；真实代码必须统一坐标和深度定义。')
s=SVG('投影落在画面里，不代表这个点在第二帧可见')
s.circ(140,340,12,BLUE);s.circ(850,340,12,GREEN);s.circ(490,100,10,RED);s.line(140,340,490,100,BLUE,3);s.line(850,340,490,100,GREEN,3,dash=True)
s.rect(615,195,55,115,'#b4bfca',INK);s.circ(650,207,8,GOLD);s.text(690,218,'前景遮挡',23)
s.text(300,405,'目标投影深度 > 第二帧表面深度 → 应屏蔽',25)
s.save('tartanair','tartan-occlusion','第二帧的射线上先遇到遮挡物；用深度一致性检查可见性，不能只检查投影是否越界。')
s=SVG('同样 10 像素，在不同焦距相机中对应不同角度')
for x,f,c in [(220,100,BLUE),(760,200,GREEN)]:
 s.circ(x,345,8,c);s.line(x,345,x,130,c,2);s.line(x,345,x+10/f*210,135,c,3);s.text(x,110,f'$f={f}$ px',25,anchor='middle');s.text(x,410,f'$x_n=10/{f}={10/f}$',24,anchor='middle')
s.text(420,240,'$x_n=(u-c_x)/f_x$',25,anchor='middle')
s.save('tartanair','tartan-intrinsics','归一化射线把像素运动与相机内参联系起来；示例使用 100 和 200 像素焦距。')
s=SVG('仿真 IMU：姿态给角速度，位置二阶导数给加速度')
for off,label,fn,col in [(65,'$p=\\sin t$',math.sin,BLUE),(415,'v=\\cos t',math.cos,GREEN),(765,'$a=-\\sin t$',lambda t:-math.sin(t),RED)]:
 s.axes(off,350,270,235,'$t$ (s)',label if label.startswith('$') else '$'+label+'$');s.line(off,235,off+255,235,GRAY,1,dash=True);curve(s,off,235,255,95,fn,0,2*math.pi,col)
 for yy,v in [(140,'1'),(235,'0'),(330,'−1')]:s.text(off-8,yy+6,v,16,anchor='end')
s.text(55,420,'位置幅值 1 m、角频率 1 rad/s；加速度计还需旋转到机体系并去除重力。',22)
s.save('tartanair','tartan-imu','同一正弦轨迹的位置（米）、速度（米每秒）和加速度（米每二次方秒），保留正负号和共同时间轴；轨迹光滑不等于满足执行器限制。')
# LET
s=SVG('亮度改变时，正确对齐的位置也会有灰度残差')
s.axes(70,350,420,235,'位置','强度');curve(s,70,350,395,205,lambda x:.3+.3*math.tanh(x),-3,3,BLUE);curve(s,70,350,395,205,lambda x:.55+.35*math.tanh(x),-3,3,RED)
s.text(560,150,'蓝：第一帧',24,BLUE);s.text(560,205,'红：同位置，曝光变化',24,RED);s.text(560,290,'$I_B=aI_A+b$',27);s.text(560,365,'几何位置正确，灰度差仍不为零',23)
s.save('letnet','let-illumination','同一条边在增益和偏置变化后的强度曲线，说明光度误差并不只由运动造成。')
s=SVG('特征要对光照稳定，也要对空间位移保持足够敏感')
s.axes(70,345,415,240,'位移','匹配代价');curve(s,70,345,395,40,lambda x:.2*x*x,-2.4,2.4,BLUE);s.line(75,333,460,333,RED,3);s.text(580,175,'有结构：存在可定位的最低点',24,BLUE);s.text(580,245,'常量特征：代价很小，但处处一样',24,RED);s.text(580,335,'$J^{\\mathsf T}J$ 需要足够秩',25)
s.save('letnet','let-landscape','二次代价与常量特征的教学对比：让所有对应相似并不足够，还要防止失去定位梯度。')
s=SVG('把求解器接进训练：外层位置误差反过来塑造内层残差')
for i,x in enumerate([100,340,580,820]):
 s.axes(x,280,150,125,'$u$','');curve(s,x,280,145,30,lambda u:(u-.4)**2,-1.5,2,BLUE);u=[-1.1,-.5,.12,.38][i];px=x+(u+1.5)/3.5*145;py=280-(u-.4)**2*30;s.circ(px,py,8,RED);s.text(x,335,f'迭代 {i}',23)
 if i<3:s.line(x+165,200,x+220,200,GRAY,2,arrow=True)
s.line(915,395,100,395,GREEN,3,arrow=True);s.text(550,438,'位移损失 → 可微迭代 → 特征网络参数',24,GREEN,'middle')
s.save('letnet','let-unroll','有限步优化的教学展开：红点逐步接近局部极小值，外层监督最终坐标；图不声称每次真实 LM 都采用该步长。')
s=SVG('真值附近训练，主要教会局部收敛；大运动仍需良好初值')
s.axes(80,360,900,245,'初值误差 / px','代价');curve(s,80,360,880,12,lambda x:1+.045*x*x+2*(1-math.cos(x)), -12,12,BLUE)
s.rect(447,105,146,245,'#edf5ed');curve(s,80,360,880,12,lambda x:1+.045*x*x+2*(1-math.cos(x)), -12,12,BLUE)
s.line(520,360,520,100,GREEN,2,dash=True);s.text(520,84,'真值',23,GREEN,'middle');s.text(520,415,'绿色区示意训练扰动集中区域；并非实测吸引域',22,anchor='middle')
s.save('letnet','let-basin','示意多极小值目标与局部初始化范围。LET-NET2 固定训练代码使用真值加标准差 2 像素的噪声，不能据此证明任意大运动可收敛。')
# ALIKED
s=SVG('共享密集特征继续保留，最终描述只在稀疏坐标上计算')
s.grid(70,125,10,7,27);s.grid(650,125,10,7,27)
for i in range(7):
 for j in range(10):s.circ(83+j*27,138+i*27,4,BLUE)
for i,j in [(1,2),(3,4),(5,2),(2,8),(6,9)]:s.circ(663+j*27,138+i*27,7,RED)
s.text(70,400,'密集描述头：$HW$ 个位置',24);s.text(650,400,'稀疏描述头：$N$ 个位置',24)
s.save('aliked','aliked-sparse-cost','点标记表示最终描述子需要被计算的位置；ALIKED 仍然需要密集共享特征与分数图。')
s=SVG('局部 softargmax：用连续质心细化离散候选点')
for i,(p,a) in enumerate([(-1,.1),(0,.3),(1,.6)]):
 x=120+i*135;s.rect(x,340-a*350,65,a*350,BLUE);s.text(x+32,375,str(p),24,anchor='middle');s.text(x+32,320-a*350,str(a),22,anchor='middle')
s.text(630,170,'$\\hat x=(-1)0.1+0(0.3)+1(0.6)$',25);s.text(630,240,'$\\hat x=0.5$',29,GREEN);s.text(630,330,'梯度改变质量分布，从而移动坐标',23)
s.save('aliked','aliked-subpixel','按三个归一化权重计算得到 0.5 像素的连续位置；局部细化不等于 NMS 索引本身可微。')
s=SVG('稀疏可变形采样：同一个关键点，支持区域随局部结构调整')
for off,skew in [(65,0),(620,55)]:
 s.path([(off+50,120),(off+285,120+skew),(off+285,320),(off+50,320-skew)],BLUE,4,fill=LIGHT,close=True)
 center=(off+70,160);s.circ(*center,9,BLUE)
 for j,(dx,dy) in enumerate([(10,0),(100,15),(180,32),(15,60),(60,130),(170,130)]):
  px=off+70+dx;py=145+dy+skew*dx/235;s.circ(px,py,6,RED);s.line(*center,px,py,GREEN,1,dash=True)
s.text(60,412,'蓝点：关键点；红点：支持采样坐标',23);s.text(650,412,'偏移由局部特征预测',23)
s.save('aliked','aliked-sampling','教学示意中两幅图共享局部结构但发生剪切，支持采样位置跟随结构；真实偏移由描述损失间接学习。')
s=SVG('Sparse NRE：在检测到的候选点中，让几何正对赢得竞争')
a=np.array([.9,.7,.2]);p=np.exp(a/.1);p/=p.sum()
for i,v in enumerate(p):s.rect(110+i*130,355-v*240,65,v*240,GREEN if i==0 else BLUE);s.text(142+i*130,388,f'$b_{i+1}$',24,anchor='middle');s.text(142+i*130,330-v*240,f'{v:.3f}',22,anchor='middle')
s.text(595,175,'相似度：(0.9, 0.7, 0.2)',24);s.text(595,245,'$\\tau=0.1$',26);s.text(595,320,f'$-\\log p_1={-math.log(p[0]):.3f}$',27)
s.save('aliked','aliked-supervision','由三个相似度直接计算的 softmax 与负对数，展示温度以及困难负样本对稀疏描述训练的影响。')
# Loop closure: objects, factors and geometry, not paragraph boxes.
s=SVG('一条回环从外观候选走到共享的几何状态')
for x in [60,270]:
 s.rect(x,130,130,120,LIGHT,BLUE)
 for j in range(3):s.rect(x+15+j*37,150,22,40,'#afc8dc')
s.line(190,185,260,185,GOLD,3,arrow=True)
for i in range(3):s.line(95+i*30,205,305+i*30,205,GREEN,1)
pts=[(555,300),(605,140),(775,120),(865,270),(675,345)];s.graph(pts,[(0,1),(1,2),(2,3),(3,4)],fixed=(0,));s.line(*pts[0],*pts[4],RED,4)
s.text(70,408,'候选检索 → 局部几何验证',24);s.text(565,408,'新增约束 → 图优化与地图融合',24)
s.save('loop-closure','loop-overview','外观相似只产生候选；几何对应确认后才能添加约束，并把校正传播到地图。')
s=SVG('同一组观测，可以诱导不同的图；它们的边不是同一种信息')
for i in range(3):s.circ(120+i*110,150,11,BLUE)
for j in range(4):
 x=90+j*95;s.path([(x,310),(x+9,328),(x-9,328)],GREEN,2,fill=GREEN,close=True)
 for i in range(3):
  if (i+j)%3:s.line(120+i*110,150,x,315,GRAY)
s.graph([(665,145),(930,170),(785,320)],[(0,1),(1,2),(2,0)])
s.text(65,408,'观测图：相机 — 地标',23);s.text(645,408,'共视图：相机 — 相机',23)
s.save('loop-closure','loop-graphs','共享地标可以诱导相机间共视连接；共享点数本身不等于相对位姿测量及其信息矩阵。')
s=SVG('坐标变换方向：$T_{AB}$ 将 B 中的坐标变到 A')
for x,y,label in [(180,330,'W'),(555,280,'B'),(890,210,'C')]:
 s.line(x,y,x+65,y,RED,3,arrow=True);s.line(x,y,x,y-65,GREEN,3,arrow=True);s.text(x-20,y+40,label,25)
s.line(865,235,605,280,BLUE,3,arrow=True);s.text(730,245,'$T_{BC}$',26,anchor='middle')
s.line(530,300,240,330,BLUE,3,arrow=True);s.text(390,282,'$T_{WB}$',26,anchor='middle')
s.text(485,110,'$T_{WC}=T_{WB}T_{BC}$',30,anchor='middle');s.text(500,415,'投影世界点时使用逆变换 $T_{CW}$',24,anchor='middle')
s.save('loop-closure','loop-frames','变换复合遵循坐标路径。相机位姿的存储方向与投影时需要的方向相反，代码阅读必须先核对。')
s=SVG('Local BA：局部位姿与点一起更新，外围相机提供固定边界')
pts=[(100,160),(320,150),(550,160),(780,150),(1000,160)];s.graph(pts,[(0,1),(1,2),(2,3),(3,4)],fixed=(0,4))
for j in range(7):
 x=170+j*115;y=300+20*(j%2);s.path([(x,y-9),(x+9,y+9),(x-9,y+9)],GREEN,2,fill=GREEN,close=True)
 for i in range(5):
  if abs(x-pts[i][0])<260:s.line(*pts[i],x,y,GRAY,1)
s.text(90,425,'方形：固定外围帧；圆形：活动相机；三角形：活动地标',24)
s.save('loop-closure','loop-local-ba','局部 BA 的观测不只来自活动相机，也来自看到这些地标的固定外围相机。')
s=SVG('视觉惯性图：像素约束几何，IMU 同时连接运动与偏置')
for i,x in enumerate([170,440,710,980]):
 s.circ(x,160,14,BLUE);s.rect(x-14,265,28,28,'#e8dfbd',GOLD);s.text(x,125,f'$T_{i}$',23,anchor='middle');s.text(x,340,f'$v_{i},b_{i}$',23,anchor='middle');s.line(x,175,x,265,GRAY)
 if i<3:
  s.rect(x+120,210,22,22,GOLD)
  for xx,yy in [(x,160),(x+270,160),(x,280),(x+270,280)]:s.line(x+131,221,xx,yy,GOLD,1.5)
s.text(95,421,'每个预积分因子连接前后姿态、位置、速度和偏置，不能简化成一条纯位置边。',23)
s.save('loop-closure','loop-imu','惯性因子的依赖关系示意；圆为位姿，方为速度/偏置，金色小方块代表联合惯性残差。')
s=SVG('Schur 消元：先去掉当前线性系统的地标增量，再回代')
a=np.array([[1,1,1,1,0],[1,1,0,1,1],[1,0,1,0,0],[1,1,0,1,0],[0,1,0,0,1]])
s.matrix(a,80,120,50);s.rect(80,120,98,98,'none',RED);s.rect(180,220,148,148,'none',GREEN)
s.line(380,235,525,235,GRAY,3,arrow=True);s.matrix([[3.5,0],[0,1]],580,160,70)
s.text(70,419,'相机与地标联合系统',23);s.text(560,350,'约化相机系统',23);s.text(785,235,'$S=H_{cc}-H_{cp}H_{pp}^{-1}H_{pc}$',19)
s.save('loop-closure','loop-schur','左图为块稀疏性示意，右侧数值来自正文手算例子；消元后仍保留原始非线性观测用于下一次迭代。')
s=SVG('边缘化留下局部二次先验；被删测量不能自动重新线性化')
s.graph([(90,185),(245,185),(400,185)],[(0,1),(1,2)],fixed=());s.circ(90,185,20,'none',RED);s.line(70,165,110,205,RED,3)
s.line(455,185,565,185,GRAY,3,arrow=True);s.graph([(650,185),(885,185)],[(0,1)])
s.rect(745,270,35,35,GOLD);s.line(762,270,650,185,GOLD,2);s.line(762,270,885,185,GOLD,2)
s.text(80,365,'旧状态和测量被压缩',24);s.text(620,365,'先验依赖原线性化点',24);s.text(620,421,'$r_{prior}=A(x\\boxminus\\bar x)+b$',24)
s.save('loop-closure','loop-marginalization','金色因子表示旧信息形成的先验；把状态移出窗口与只在一次线性求解中消元是不同操作。')
s=SVG('几何验证的输入不同，能恢复的运动信息也不同')
for k,title in enumerate(['2D–2D','2D–3D','3D–3D']):
 off=65+k*360;s.text(off,100,title,26)
 if k<2:s.rect(off,160,85,130,LIGHT,BLUE)
 for i in range(4):
  y=175+i*29
  if k<2:s.circ(off+40,y,5,BLUE)
  else:s.path([(off+40,y-9),(off+49,y+9),(off+31,y+9)],BLUE,2,fill=BLUE,close=True)
  if k==0:s.circ(off+210,y+12,5,GREEN)
  else:s.path([(off+200,y),(off+210,y+18),(off+190,y+18)],GREEN,2,fill=GREEN,close=True)
  s.line(off+45,y,off+200,y+9,GRAY,1)
 s.text(off,390,['E：平移方向','PnP：地图坐标位姿','$SE(3)$ / $Sim(3)$'][k],22)
s.save('loop-closure','loop-geometry','不同维度的对应决定几何问题：本质矩阵通常不提供米制平移，PnP 依赖已有地图尺度。')
s=SVG('闭合误差的分配由不确定性决定：弱约束承担更多改动')
for i,(v,d) in enumerate([(1,-1),(1,-1),(4,-4)]):
 x=170+i*340;s.rect(x,130,90,v*43,BLUE);s.text(x+45,110,f'方差 {v}',24,anchor='middle');s.text(x+45,365,f'修正 {d} m',26,RED,'middle')
s.text(160,435,'总误差 6 m；$\\delta=-6(1,1,4)/6=(-1,-1,-4)$ m',24)
s.save('loop-closure','loop-error-spread','按正文约束最小二乘精确计算的误差分配。相等权重才对应平均摊开。')
s=SVG('错误回环会拉弯整条轨迹；鲁棒核降低影响，但不能替代验证')
pts=[(90,330),(180,120),(365,120),(440,315),(305,355)];s.graph(pts,[(0,1),(1,2),(2,3),(3,4)]);s.line(*pts[0],*pts[2],RED,5,dash=True);s.text(100,420,'错误边把不同地方强行连接',22,RED)
s.axes(625,355,365,250,'残差大小','代价');curve(s,625,355,350,17,lambda x:x*x,0,3.5,RED);curve(s,625,355,350,17,lambda x:x*x if x<=1 else 2*x-1,0,3.5,BLUE)
s.text(700,125,'平方损失',21,RED);s.text(830,305,'Huber',21,BLUE)
s.save('loop-closure','loop-false-edge','右图按公式计算 Huber 与平方损失。鲁棒核减缓大残差增长，不保证识别所有自洽的假回环。')
s=SVG('Essential Graph 从共视关系中保留连通骨架和强连接')
p=[(105,250),(215,130),(340,180),(370,330),(220,365),(500,240)]
for off in [0,535]:
 pp=[(x+off,y) for x,y in p]
 ed=[(i,j) for i in range(6) for j in range(i+1,6)] if off==0 else [(0,1),(1,2),(2,3),(3,4),(2,5)]
 s.graph(pp,ed)
 if off:s.line(*pp[0],*pp[4],RED,4);s.line(*pp[1],*pp[5],GREEN,3)
s.text(60,430,'密集共视关系',23);s.text(615,430,'生成树 + 回环边 + 强共视边',23)
s.save('loop-closure','loop-essential','稀疏全局传播图的教学示意；红为回环，绿为额外强共视连接，父子树保证基本连通。')
s=SVG('校正地图点：旧世界 → 参考相机 → 新世界')
for x,label,col in [(150,'旧世界点',BLUE),(535,'相机坐标',GRAY),(935,'新世界点',GREEN)]:s.circ(x,220,13,col);s.text(x,155,label,25,col,'middle')
s.line(180,220,500,220,BLUE,3,arrow=True);s.text(340,270,'$S_{iW}^{old}$',26,anchor='middle');s.line(565,220,895,220,GREEN,3,arrow=True);s.text(735,270,'$(S_{iW}^{new})^{-1}$',26,anchor='middle')
s.text(550,392,'$S_{iW}^{new}P_W^{new}=S_{iW}^{old}P_W^{old}$',28,anchor='middle')
s.save('loop-closure','loop-map-correction','保持参考关键帧中的点坐标，从而保持其投影；同一点应避免被多个邻居重复校正。')
s=SVG('轨迹对齐之后，重复地标还需要合并观测')
for off,merge in [(0,False),(540,True)]:
 cams=[(90+off,140),(380+off,140),(90+off,330),(380+off,330)]
 for x,y in cams:s.circ(x,y,10,BLUE)
 for i,(x,y) in enumerate(cams):s.line(x,y,235+off+(0 if merge else (-30 if i%2==0 else 30)),230,GRAY)
 for x in ([235+off] if merge else [205+off,265+off]):s.path([(x,216),(x+12,240),(x-12,240)],GREEN,2,fill=GREEN,close=True)
s.text(90,415,'两个地标，各自解释一段历史',23);s.text(600,415,'一个地标，共享两段观测',23)
s.save('loop-closure','loop-fusion','地标融合改变观测关联结构；它使两段历史的像素真正约束同一个三维变量。')
s=SVG('异步优化必须处理快照之后新增的帧')
s.line(130,175,1000,175,BLUE,4,arrow=True);s.line(130,305,1000,305,GREEN,4,arrow=True)
for i in range(8):s.circ(160+i*105,175,8,BLUE);s.text(160+i*105,140,str(i),19,anchor='middle')
s.rect(275,285,480,40,'#d3e7df');s.text(515,271,'后台优化快照中的旧状态',22,GREEN,'middle');s.line(280,182,280,285,GRAY,2,dash=True);s.line(760,305,760,182,RED,3,arrow=True)
s.text(70,230,'实时图持续增长',23,BLUE);s.text(765,360,'结果校验 + 新状态传播',22,RED);s.text(120,430,'旧代次结果不能覆盖更新的回环；提交时位姿和地标必须一致。',23)
s.save('loop-closure','loop-async','横轴为时间；优化使用一个历史快照，提交时还要更新未参与该次优化的新关键帧与地图点。')
s=SVG('Atlas 合并：先对齐两张地图，再在交界处联合优化')
a=[(90,300),(170,165),(300,210),(360,340)];b=[(580,290),(690,145),(855,160),(960,310)]
s.graph(a,[(0,1),(1,2),(2,3)],BLUE);s.graph(b,[(0,1),(1,2),(2,3)],GREEN)
s.line(*a[2],*b[0],RED,4,arrow=True);s.line(*a[3],*b[1],RED,2,dash=True)
s.rect(280,115,450,265,'none',GOLD);s.text(500,95,'焊接窗口',25,GOLD,'middle');s.text(130,420,'公共区域对齐 + 重复点融合 + welding BA',25)
s.save('loop-closure','loop-atlas','金色窗口示意两张地图接缝处参与联合优化的状态；外围状态作为边界，随后传播校正。')
s=SVG('VINS-Fusion：局部窗口保留测量，全局图保留关键帧关系')
s.graph([(100,160),(255,160),(410,160),(565,160)],[(0,1),(1,2),(2,3)],BLUE)
for x in [195,350,505]:s.rect(x,245,18,18,GOLD);s.line(x+9,245,x-95,170,GOLD);s.line(x+9,245,x+60,170,GOLD)
s.graph([(660,340),(770,150),(960,165),(995,335),(825,375)],[(0,1),(1,2),(2,3),(3,4)],GREEN);s.line(660,340,825,375,RED,4)
s.text(60,408,'VIO：像素 + IMU + 边缘化先验',22);s.text(665,440,'全局图：相对位姿 + 回环',22)
s.save('loop-closure','loop-vins-two-graphs','两种历史结构同时存在；独立 loop_fusion 的位姿图校正并不重建局部窗口已经丢弃的全部非线性测量。')
s=SVG('OKVIS2 把共同观测压成带信息矩阵的相对位姿因子')
s.circ(140,150,12,BLUE);s.circ(420,150,12,BLUE)
for j in range(5):
 x=160+j*55;s.circ(x,300,6,GREEN);s.line(140,150,x,300,GRAY);s.line(420,150,x,300,GRAY)
s.line(460,220,595,220,GRAY,3,arrow=True);s.circ(660,220,12,BLUE);s.circ(995,220,12,BLUE);s.rect(815,207,26,26,GOLD);s.line(675,220,815,220,GOLD,3);s.line(841,220,980,220,GOLD,3)
s.text(75,415,'两帧的共同像素观测',23);s.text(650,335,'$W=H^*,\\quad e_0=-(H^*)^+b^*$',23);s.text(650,410,'局部二阶信息得到保留',23)
s.save('loop-closure','loop-okvis-compress','Schur 消去地标后形成相对位姿因子；信息矩阵携带方向相关约束，但成对压缩仍可能重复计算共享观测。')
s=SVG('恢复观测依赖归档数据，不能只靠一个小信息矩阵逆推')
s.circ(145,220,12,BLUE);s.circ(375,220,12,BLUE);s.rect(247,208,25,25,GOLD);s.line(155,220,247,220,GOLD,3);s.line(272,220,363,220,GOLD,3)
s.rect(180,330,200,40,LIGHT,GRAY);s.text(280,357,'观测与关联归档',20,anchor='middle');s.line(380,350,575,350,GREEN,2,arrow=True)
s.circ(680,150,12,BLUE);s.circ(980,150,12,BLUE)
for x in [725,785,850,915]:s.circ(x,300,7,GREEN);s.line(680,150,x,300,GRAY);s.line(980,150,x,300,GRAY)
s.line(450,220,590,220,RED,3,arrow=True);s.text(515,185,'回环',22,RED,'middle');s.text(670,420,'重新激活像素因子与地标',23)
s.save('loop-closure','loop-okvis-revive','压缩因子和原始数据归档承担不同职责；回环恢复的是保存下来的观测，不是从 Hessian 唯一反演出来的图像。')
s=SVG('稠密子地图留在局部坐标，闭环首先改变它们的锚定位姿')
for off,ang,c in [(130,0,BLUE),(710,-.3,GREEN)]:
 pts=[]
 for i in range(5):
  for j in range(5):
   x,y=j*38,i*38;xx=off+math.cos(ang)*x-math.sin(ang)*y;yy=150+math.sin(ang)*x+math.cos(ang)*y;s.rect(xx,yy,18,18,LIGHT,c)
 s.circ(off,150,10,RED);s.line(off,150,off+85,150,RED,3,arrow=True)
s.line(400,225,590,225,GRAY,3,arrow=True);s.text(550,400,'$P_W=T_{Wa}P_a$：锚点变，局部体素索引不变',25,anchor='middle')
s.save('loop-closure','loop-submaps','刚性移动子地图降低全局校正成本；若子地图内部已发生明显形变，只修改锚定位姿仍不够。')
(ROOT/'scripts/vision-series/illustrations.json').write_text(json.dumps(META,ensure_ascii=False,indent=2)+'\n')
print(f'Generated {len(META)} teaching figures')
