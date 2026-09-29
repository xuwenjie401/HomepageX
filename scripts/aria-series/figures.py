"""Deterministic teaching figures; no model outputs or benchmark measurements.
Run from the repo root, then `node scripts/aria-series/typeset.mjs`.
All curves, projections, probabilities and matrix entries are computed below.
"""
from pathlib import Path
from html import escape
import math,json
import numpy as np
ROOT=Path(__file__).resolve().parents[2]; META={}
BLUE='#2563a6';RED='#ce593e';GREEN='#267a65';GRAY='#778396';GOLD='#b78c2c';INK='#213047';LIGHT='#eef3f7'
class SVG:
 def __init__(self,title,w=1100,h=500):
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

def panel(s,x,title):s.text(x,84,title,22,BLUE)
def foot(s,t):s.line(35,s.h-68,s.w-35,s.h-68,LIGHT,2);s.text(35,s.h-30,t,22)
def camera(s,x,y,c=BLUE):
 s.path([(x-13,y-13),(x+13,y-13),(x+13,y+13),(x-13,y+13)],c,2,'white',True);s.path([(x+13,y-7),(x+29,y-16),(x+29,y+16),(x+13,y+7)],c,2,'white',True)
def human(s,x,y,pose='stand',c=BLUE,scale=1):
 # Head is the shared origin; articulated side-view skeletons are teaching poses.
 coords={'stand':[(0,26),(0,62),(0,112),(-24,155),(-30,208),(20,155),(28,208),(-28,88),(-35,125),(25,88),(35,122)],'sit':[(0,26),(5,60),(12,105),(67,105),(69,170),(55,114),(55,170),(35,77),(66,94),(-15,80),(18,102)],'squat':[(0,26),(-9,60),(-35,105),(18,131),(-7,170),(27,133),(12,170),(30,85),(57,113),(14,92),(48,119)]}[pose]
 pts=[(x+a*scale,y+b*scale) for a,b in coords];s.circ(x,y,17*scale,'white',c)
 for i,j in [(0,1),(1,2),(2,3),(3,4),(2,5),(5,6),(1,7),(7,8),(1,9),(9,10)]:s.line(*pts[i],*pts[j],c,5)
 for p in pts:s.circ(*p,4*scale,c)
def hand(s,x,y,sc=1,c=BLUE):
 # Fixed palm / finger topology; all variants use exact similarity transforms.
 pts=np.array([(0,0),(-25,-15),(-45,-40),(-57,-60),(-62,-76),(-22,-47),(-30,-83),(-30,-110),(-28,-128),(0,-52),(0,-92),(1,-126),(3,-145),(20,-48),(28,-84),(32,-114),(33,-132),(36,-34),(51,-61),(60,-87),(62,-104)])*sc+[x,y]
 for f in range(5):
  chain=[0]+list(range(1+4*f,5+4*f))
  for a,b in zip(chain,chain[1:]):s.line(*pts[a],*pts[b],c,3)
 for a,b in [(5,9),(9,13),(13,17)]:s.line(*pts[a],*pts[b],c,2)
 for p in pts:s.circ(*p,3,c)

# Boxer: scale, robust aggregation, heteroscedastic loss, and static fusion.
s=SVG('二维框固定了张角，却没有固定距离与物体尺寸')
panel(s,45,'侧视几何');camera(s,100,245)
for z,size,col in [(400,110,BLUE),(673,220,RED)]:
 s.rect(z,245-size/2,30,size,'white',col);s.line(127,245,z,245-size/2,col,2);s.line(127,245,z,245+size/2,col,2)
 s.text(z+48,229,'$H$' if col==BLUE else '$2H$',26,col);s.text(z-10,373,'$Z$' if col==BLUE else '$2Z$',26,col)
s.line(240,135,240,350,GRAY,3);s.line(240,245-55*113/273,240,245+55*113/273,GREEN,7);s.text(203,124,'像平面',20);s.text(455,126,'同一对投影边界',22)
s.text(685,398,r'$h=fH/Z=f(2H)/(2Z)$',25)
foot(s,'图像证据给方向；度量深度与尺寸先验，帮助选出实际的三维盒子。')
s.save('boxernet','boxer-depth','按相似三角形绘制的尺度歧义。物体尺寸与深度同时加倍，图像高度不变；这是教学几何，不是检测输出。')
s=SVG('稀疏深度落进 patch：先稳健聚合，再保留缺测')
panel(s,45,'有效深度样本 / m');s.grid(65,115,5,5,48)
for (i,j),v in zip([(0,1),(1,3),(2,2),(4,0)],[1.9,2.0,2.1,8.0]):s.circ(89+48*j,139+48*i,18,RED if v==8 else BLUE);s.text(89+48*j,146+48*i,str(v),16,'white','middle')
s.line(335,240,425,240,GRAY,3,arrow=True)
panel(s,455,'排序后的有效样本');vals=[1.9,2,2.1,8]
for i,v in enumerate(vals):s.rect(455+i*135,140,112,66,'#fcece6' if i==3 else LIGHT);s.text(511+i*135,183,f'${v:g}$',26,RED if i==3 else BLUE,'middle')
s.line(642,222,777,222,GREEN,3);s.text(452,282,r'$\mathrm{median}=2.05\;\mathrm m$',27,GREEN);s.text(452,328,r'$\mathrm{mean}=3.50\;\mathrm m$',25,RED);s.text(65,395,'空 patch → 深度设为 −1；这是缺测标记，不是负距离。',24)
foot(s,'中位数抑制单个离群值；稀疏点仍可能属于背景或错位表面。')
s.save('boxernet','boxer-patches','四个有效像素深度的普通中位数为 2.05 m，均值为 3.50 m。论文描述中位数，所核查公开代码的稀疏点分支实际取均值；此图比较两种聚合的行为。')
s=SVG('不确定性可以降低几何惩罚，但自身也要付出代价')
s.axes(95,380,630,265,r'$\sigma$',r'$\mathcal L$');D=4
for tick in range(5):s.line(95+140*tick,380,95+140*tick,386,INK);s.text(95+140*tick,415,f'${tick}$',18,anchor='middle')
for v in [0,2,4,6]:s.text(76,386-v*42,f'${v}$',18,anchor='end')
for fn,col in [(lambda t:D*math.exp(-t),BLUE),(lambda t:t,GRAY),(lambda t:D*math.exp(-t)+t,RED)]:curve(s,95,380,560,42,fn,0,4,col)
x=95+140*math.log(D);y=380-42*(1+math.log(D));s.circ(x,y,7,RED);s.line(x,y,x,380,RED,1,True)
s.text(780,147,r'$D\exp(-\sigma)$',25,BLUE);s.text(780,206,r'$\sigma$',25,GRAY);s.text(780,265,r'$D\exp(-\sigma)+\sigma$',25,RED);s.text(760,344,r'$D=4,\quad\sigma^*=\log4$',23)
foot(s,r'高不确定性不是“免罚”：加上 $\sigma$ 后，损失在有限位置取最小值。')
s.save('boxernet','boxer-loss','直接计算 D=4 时的损失曲线。最优 log-variance 为 log 4≈1.386；蓝线为加权几何误差，灰线为不确定性惩罚，红线为总和。')
s=SVG('静态物体可以多帧融合；动态物体会被错误合成')
for off,title in [(45,'(a) 同一静态盒子'),(590,'(b) 物体正在移动')]:panel(s,off,title);s.line(off,352,off+455,352,GRAY)
for i in range(3):
 s.rect(180+i*5,160+i*7,155,110,'none',[BLUE,GREEN,GOLD][i]);camera(s,100+i*125,335);s.line(125+i*125,327,255,225,GRAY,1,True)
s.rect(186,168,155,110,'none',RED);s.text(80,393,'统一世界坐标后，等价朝向先对齐',21)
for i,c in enumerate([BLUE,GREEN,GOLD]):s.rect(640+i*70,175,150,100,'none',c)
s.line(650,308,985,308,GRAY,2,arrow=True);s.text(958,341,'时间',20);s.rect((640+0.5*710+1.5*780)/3,168,150,114,'none',RED);s.text(620,393,'相连的重叠框 → 平均到并不存在的位置',20)
foot(s,'跨帧融合依赖“同一个静态实体”；IoU 连通并不能替代运动建模。')
s.save('boxernet','boxer-fusion','俯视教学示意。左侧同一静态物体可融合，右侧红框是不同时间观测的置信加权结果，不对应这三个观测时刻中的任何一个；采样位置和权重保存在脚本中。')

# LAMP: world frame, line geometry, temporal supervision and look-ahead.
s=SVG('先消掉观察者运动，才能学习目标本身的运动')
for i,(cx,tx) in enumerate([(0,2),(.5,2)]):
 y=190+i*160;s.line(70,y,820,y,GRAY,2,arrow=True);camera(s,130+cx*260,y);human(s,130+tx*260,y-100,'stand',GREEN,.43);s.text(55,y-66,f'$t_{i}$',25);s.text(135+cx*260,y+39,f'相机 {cx:g} m',21);s.text(750,y-22,'目标 2 m',22,GREEN);s.line(160+cx*260,y-30,635,y-30,BLUE,2,arrow=True);s.text(330,y-45,f'相机相对距离：{tx-cx:g} m',23,BLUE)
s.text(880,191,'相机坐标：',23);s.text(880,234,r'$2\to1.5$',27,RED);s.text(880,306,'世界坐标：',23);s.text(880,349,r'$2\to2$',27,GREEN)
foot(s,'静止的人在相机坐标里也会“运动”；已知定位让两种运动分开。')
s.save('lamp','lamp-world','一维度量示例：观察者前进 0.5 m，静止目标的相机坐标从 2 m 变为 1.5 m，世界坐标保持 2 m。')
s=SVG('射线统一到世界坐标；交会角与时间差仍决定难度')
for off,title in [(45,'(a) 同时刻：交会角较大'),(405,'(b) 同时刻：近乎平行'),(755,'(c) 不同时刻：目标移动')]:panel(s,off,title)
for centers,targets,col in [([(90,350),(340,350)],[(215,155)]*2,BLUE), ([(475,350),(505,350)],[(490,145)]*2,GREEN), ([(790,350),(1035,350)],[(850,170),(1000,170)],RED)]:
 for c,t in zip(centers,targets):camera(s,*c,col);s.line(c[0],c[1]-15,t[0],t[1],col,2,arrow=True);s.circ(*t,7,col)
s.line(850,145,1000,145,RED,2,arrow=True);s.text(858,125,'运动',19,RED);s.text(113,396,'几何交会更稳定',21);s.text(440,396,'深度更容易漂移',21);s.text(782,396,'不能直接当静态点三角化',20)
foot(s,r'每条线用 $\mathbf d,\;\mathbf m=\mathbf o\times\mathbf d$ 表达；序列模型补充人体与运动先验。')
s.save('lamp','lamp-rays','三种二维截面的教学几何。世界射线仍不能消除小基线深度不确定性，也不能让不同时刻的移动关节自动成为同一点。')
s=SVG('位置误差很小，也可能包含一次明显的速度跳变')
s.axes(85,355,570,240,'帧序号','位置 / m')
for v in [0,.1,.2]:s.text(70,361-v*1000,f'${v:g}$',19,anchor='end');s.line(85,355-v*1000,640,355-v*1000,LIGHT,1)
for arr,col in [([0,.1,.2],GREEN),([0,.2,.2],RED)]:
 pts=[(130+i*220,355-v*1000) for i,v in enumerate(arr)];s.path(pts,col,3)
 for p in pts:s.circ(*p,7,col)
for i in range(3):s.text(130+i*220,392,f'${i}$',20,anchor='middle')
s.text(720,145,'真值位置：0, 0.1, 0.2',23,GREEN);s.text(720,190,'预测位置：0, 0.2, 0.2',23,RED);s.text(720,256,'真值增量：0.1, 0.1',23,GREEN);s.text(720,301,'预测增量：0.2, 0',23,RED);s.text(720,370,r'$\mathcal L_{\mathrm{vel}}$ 约束相邻差分',23)
foot(s,'关节监督看每帧偏离多少；速度监督看相邻帧之间是否出现不自然的跳动。')
s.save('lamp','lamp-loss','教学轨迹只在中间一帧偏移 0.1 m，却改变了两个时间间隔的增量。论文的 velocity loss 比较离散差分，不能直接省略采样间隔后称为 m/s。')
s=SVG('重叠窗口平均更稳定，但完整平均需要等未来观测')
s.axes(110,395,895,260,'帧 / 时间','')
for i,start in enumerate([0,30,60,90]):
 x=125+start*3.4;y=120+i*62;s.rect(x,y,120*3.4,35,LIGHT,BLUE,5);s.text(x+8,y+24,f'窗口 {i+1}：120 帧',19);s.circ(431,y+18,6,RED)
s.line(431,102,431,385,RED,2,True);s.text(412,84,'待输出帧',22,RED);s.line(438,367,830,367,RED,2,arrow=True);s.text(660,351,'等到最晚覆盖它的窗口结束',21,RED,'middle')
foot(s,r'最多额外等待 $119/30\approx3.97\;\mathrm s$；每次推理快，不等于输出没有延迟。')
s.save('lamp','lamp-latency','以 30 Hz、120 帧窗口示意滑窗平均的未来依赖。图中只画四个稀疏窗口以便阅读；实际窗口步长与实时输出策略另行决定。')

# HMD²: multimodality, voxel values, diffusion and streaming windows.
s=SVG('同一个头部位置，可以对应多种下肢状态')
for x,title,pose,col in [(190,'坐下','sit',BLUE),(550,'蹲下','squat',GREEN)]:
 panel(s,x-100,title);human(s,x,145,pose,col,1.2);s.line(x-90,349,x+130,349,GRAY,2);s.circ(x,145,23,'none',RED)
s.rect(169,270,100,8,GRAY);s.line(180,278,180,349,GRAY,3);s.line(255,278,255,349,GRAY,3)
s.line(221,145,518,145,RED,1,True);s.text(390,115,'相同头部观测',21,RED,'middle')
s.text(785,145,'还需要环境条件',26);s.rect(805,195,180,8,GRAY);s.line(820,203,820,318,GRAY,3);s.line(970,203,970,318,GRAY,3);s.text(785,373,'椅子、桌面与动作语义',22)
foot(s,'环境缩小候选集合；扩散保留多个合理动作，不把它们硬平均成唯一姿态。')
s.save('hmd2','hmd2-ambiguity','两个人工骨架共享头部位置，分别呈坐姿与蹲姿。环境和语义可减少歧义，但无法证明不可见肢体只有一个真实解。')
s=SVG('点云条件是到观测点的距离，不是已知自由空间')
panel(s,45,'侧视：头部下方的局部空间');human(s,190,140,'stand',BLUE,.85)
s.rect(63,140,265,265,'none',GRAY);s.line(329,140,374,106,GRAY);s.line(329,405,374,371,GRAY);s.line(374,106,374,371,GRAY);s.line(64,140,109,106,GRAY);s.line(109,106,374,106,GRAY);s.text(65,425,'边长 2 m；中心在头部下方 1 m',19)
panel(s,465,'一个水平切片：10 × 10 采样');pts=np.array([[.35,.55],[.35,.75],[.35,.95],[.35,1.15],[.35,1.35],[.35,1.55],[1.45,1.55],[1.65,1.55]])
for i in range(10):
 for j in range(10):
  d=min(np.linalg.norm(pts-np.array([.1+.2*j,.1+.2*i]),axis=1).min(),.1)/.1
  s.rect(485+j*24,113+i*24,22,22,f'rgb({int(51+195*d)},{int(115+132*d)},{int(159+91*d)})')
for p in pts:s.circ(485+p[0]*120,113+p[1]*120,4,RED)
s.text(780,166,r'$v=\min(d,0.1)$',25);s.text(780,218,'深色：靠近观测点',22);s.text(780,268,'浅色：距离达到截断值',22);s.text(780,326,'也可能只是从未被看见',22,RED)
foot(s,'编码器读取 10³ 个距离值；远离稀疏点，不代表那里一定没有障碍。')
s.save('hmd2','hmd2-voxel','按人工稀疏点计算最近距离并在 0.1 m 截断，颜色只用于展示该数值。左侧为 2 m 立方体的示意投影，右侧为其中一个教学切片。')
s=SVG('扩散只给动作加噪；头部、图像和环境作为条件')
s.text(50,90,'同一条件：头部轨迹 + CLIP 图像特征 + 点云编码',23,GREEN)
s.line(65,111,1030,111,GREEN,2)
rng=np.random.default_rng(12)
for i,(mix,label) in enumerate([(1,'初始噪声'),(.55,'中间状态'),(.12,'接近动作'),(0,'动作样本')]):
 x=60+i*270;s.text(x,156,label,23);base=np.sin(np.linspace(0,2*math.pi,34))*.7;noise=rng.normal(0,.7,34);v=(1-mix)*base+mix*noise
 s.path([(x+j*5.7,263-45*a) for j,a in enumerate(v)],BLUE,3);s.line(x,330,x+188,330,GRAY,1)
 if i<3:s.line(x+205,255,x+245,255,GRAY,2,arrow=True)
s.text(160,401,r'$x_0=0.8,\quad\bar\alpha=0.64,\quad\epsilon=-0.5\;\Rightarrow\;x_t=0.34$',27)
foot(s,'下方是单个动作标量的加噪例子；折线只帮助理解去噪，不是论文生成结果。')
s.save('hmd2','hmd2-diffusion','使用固定随机种子绘制概念曲线；标量例按正文的前向加噪公式计算。真实模型对整段关节旋转序列生成，训练预测干净动作。')
s=SVG('240 帧窗口：较小的新帧块降低等待，却更依赖历史')
for i,h in enumerate([180,10]):
 y=140+i*145;s.text(45,y-24,rf'$T=240,\;h={h}$',24);start=140;scale=3.2;old=240-h
 s.rect(start,y,old*scale,60,BLUE);s.rect(start+old*scale,y,h*scale,60,GOLD);s.text(start+old*scale/2,y+39,f'历史 {old} 帧',21,'white','middle')
 if h>30:s.text(start+(old+h/2)*scale,y+39,f'新 {h} 帧',22,'white','middle')
 else:s.line(892,y-8,983,y-8,GOLD,2);s.text(939,y-24,'新 10 帧',21,GOLD,'middle')
 s.text(965,y+43,f'{h/60:.3g} s',24,GOLD)
foot(s,'每次去噪都回写历史；60 Hz 下，新块分别持续 3 s 与约 0.167 s。')
s.save('hmd2','hmd2-window','按真实帧数比例绘制 240 帧窗口。蓝色是重叠历史，金色是新增块；右侧数字是新增块时长，首帧最大前视间隔为 (h−1)/60。')

# EgoForce: similarity ambiguity, crop intrinsics, point-to-line and conditioning.
s=SVG('二维投影相同，不代表手的度量尺寸和深度相同')
camera(s,45,245);s.line(45,245,970,245,GRAY,1,True)
hand(s,425,260,.75,BLUE);hand(s,805,275,1.5,RED)
# Both hand origins and all hand points are exact factor-two scalings about the camera at (45,245).
for q in [(425,260),(425+.75*3,260-.75*145),(425-.75*62,260-.75*76)]:
 end=(45+2*(q[0]-45),245+2*(q[1]-245));s.line(45,245,*end,GRAY,1,True)
s.text(344,330,'尺寸 $H$，深度 $Z$',24,BLUE);s.text(730,330,'尺寸 $2H$，深度 $2Z$',24,RED);s.text(430,400,r'$\pi(s\mathbf P_i)=\pi(\mathbf P_i)$',30)
foot(s,'前臂提供更长的几何结构与尺寸先验；严格尺度仍需要额外用户信息。')
s.save('egoforce','egoforce-scale','人工手骨架的三维截面作精确二倍相似变换：尺寸与深度同时加倍，投影射线保持一致。并非模型预测或真实用户手型。')
s=SVG('裁块缩放以后，焦距和主点也必须一起变换')
panel(s,45,'原图像平面');s.rect(60,108,460,300,LIGHT,GRAY);s.rect(132,115,288,288,'white',BLUE);hand(s,285,350,.92,BLUE)
s.line(132,412,420,412,BLUE,2);s.text(265,426,'裁块宽 400 px',22,BLUE,'middle');s.circ(290.4,236,6,RED);s.text(302,226,'主点',20,RED);s.text(75,104,'$x_0=100$',21)
s.line(555,235,615,235,GRAY,3,arrow=True);panel(s,655,'缩放到 224 × 224');s.rect(685,125,224,224,'white',BLUE);hand(s,804,125+235*224/288,.92*224/288,BLUE);s.circ(808.2,125+121*224/288,6,RED);s.line(797,125,797,349,GRAY,1,True)
s.text(659,379,r'$f_x^\prime=800\times224/400=448$',24);s.text(659,413,r'$c_x^\prime=(320-100)\times224/400=123.2$',20)
foot(s,'裁块中心是 112，但变换后的主点是 123.2；把两者混同会改变反投影射线。')
s.save('egoforce','egoforce-crop','针孔数值例：原焦距 800、主点 320，裁块起点 100、宽度 400，缩至 224 后焦距为 448、主点为 123.2。图中骨架只是几何示意。')
s=SVG('RSS 求一个共享平移，让所有关节靠近自己的射线')
o=np.array([105.,365.]);points=[np.array([320.,160.]),np.array([540.,235.]),np.array([320.,315.])]
for j,p in enumerate(points):
 d=(p-o)/np.linalg.norm(p-o);s.line(*o,*(o+1.13*np.linalg.norm(p-o)*d),BLUE,2);q=p+np.array([40.,55.]);proj=o+d*np.dot(q-o,d);s.circ(*q,8,RED);s.circ(*proj,5,BLUE);s.line(*q,*proj,RED,3);s.text(q[0]+12,q[1]+7,rf'$\mathbf J_{j}+\mathbf t$',21,RED)
camera(s,*o);s.text(53,403,'相机原点',21)
s.text(770,149,r'$P_i=I-\mathbf d_i\mathbf d_i^{\mathsf T}$',24);s.text(770,212,'红线是垂直射线的残差',22,RED);s.text(770,278,r'$A=\sum_iw_iP_i$',26);s.text(770,339,r'$A\mathbf t=-\sum_iw_iP_i\mathbf J_i$',23)
foot(s,'求解平移时，根相对形状保持固定；置信度低的关节，对最小二乘的影响较小。')
s.save('egoforce','egoforce-rays','用向量投影精确画出点到无限直线的垂直残差。RSS 同时求解所有关节共享的平移；正向深度不是这个无约束闭式解自动施加的条件。')
s=SVG('射线角度太接近，沿深度方向的约束会变弱')
for k,angle in enumerate([30,5]):
 off=80+k*535;panel(s,off,f'半夹角 {angle}°');theta=math.radians(angle);origin=np.array([off+180.,365.]);target=np.array([off+180.,155.])
 for sign in [-1,1]:s.line(*origin,target[0]+sign*210*math.tan(theta),target[1],BLUE,2)
 camera(s,*origin);target[1]=220
 # Eigenvalues of sum(I-dd^T) for d=(±sin θ, cos θ), scaled equally across panels.
 lx,lz=2*math.cos(theta)**2,2*math.sin(theta)**2
 rx,rz=13/math.sqrt(lx),13/math.sqrt(lz)
 s.path([(target[0]+rx*math.cos(t),target[1]+rz*math.sin(t)) for t in np.linspace(0,2*math.pi,160)],RED,3)
 s.text(off+180,408,rf'$\lambda_\mathrm{{depth}}={lz:.3f}$',24,RED,'middle')
foot(s,'相同残差等高线：夹角越小，深度方向越长；正则化让求解稳定，却不会凭空增加观测。')
s.save('egoforce','egoforce-conditioning','二维对称射线的法矩阵，半夹角 30 度时深度特征值为 0.5，5 度时约 0.015。红色等高线按同一误差阈值计算，展示小夹角病态。')

# Photoreal: rolling time, nonlinear exposure, warped row map and adaptive sampling.
s=SVG('一帧画面里的不同行，实际看到了不同的相机姿态')
panel(s,45,'理想竖线');s.rect(60,117,200,260,LIGHT);s.line(160,128,160,362,BLUE,5)
panel(s,350,'滚动读出 + 转头');s.rect(366,117,285,260,LIGHT)
for i in range(9):
 y=128+i*29;shift=1200*math.tan(math.radians(100*.016*i/8));s.line(375,y,640,y,'#d4dfe8',1);s.circ(472+shift*2.5,y,4,RED)
s.path([(472+1200*math.tan(math.radians(100*.016*t))*2.5,128+232*t) for t in np.linspace(0,1,80)],RED,4)
s.line(690,126,690,363,GRAY,2,arrow=True);s.text(709,145,'首行：0 ms',21);s.text(709,361,'末行：16 ms',21)
s.text(758,216,r'$\Delta\theta=1.6^\circ$',25);s.text(758,273,r'$1200\tan(1.6^\circ)\approx33.5$',25)
foot(s,'整帧套一个姿态，可能把读出时序造成的弯斜错误地解释为场景几何。')
s.save('photoreal-egocentric-reconstruction','photoreal-timing','以 16 ms 读出、100°/s 转动和 1200 px 焦距计算跨行位移约 33.5 px。示意图夸大斜率便于阅读；实际位移随场景点位置与相机模型变化。')
s=SVG('先在线性辐亮度域积分，最后再经过非线性响应')
panel(s,45,'一个像素的两次时刻采样');s.rect(70,130,150,150,'#3b3b3b');s.rect(270,130,150,150,'#ffffff',GRAY);s.text(145,320,'$L_1=0.04$',25,anchor='middle');s.text(345,320,'$L_2=1.00$',25,anchor='middle')
val_correct=((.04+1)/2)**(1/2.2);val_wrong=(.04**(1/2.2)+1)/2
for i,(v,label,col) in enumerate([(val_correct,'线性平均 → gamma',GREEN),(val_wrong,'gamma → 编码值平均',RED)]):
 x=580+i*260;c=int(v*255);s.rect(x,130,150,150,f'rgb({c},{c},{c})');s.text(x+75,324,f'${v:.3f}$',29,col,'middle');s.text(x+75,375,label,21,col,'middle')
foot(s,r'$\phi((L_1+L_2)/2)\ne(\phi(L_1)+\phi(L_2))/2$：积分顺序改变了像素亮度。')
s.save('photoreal-egocentric-reconstruction','photoreal-exposure','采用指数为 1/2.2 的教学 gamma 响应，积分后编码为约 0.743，先编码再平均为约 0.616。色块按计算值绘制。')
s=SVG('去畸变会扭曲“原始行号图”，行时间也要跟着搬家')
for k,title in enumerate(['原始传感器行号','反向径向映射后的行号']):
 off=85+k*540;panel(s,off,title)
 for i in range(36):
  for j in range(48):
   x=(j+.5)/48*2-1;y=(i+.5)/36*2-1;r=x*x+y*y;source_y=y if k==0 else y*(1+.35*r);v=(source_y+1)/2
   color='#edf1f4' if not 0<=v<=1 else f'rgb({int(245-180*v)},{int(238-108*v)},{int(190+40*v)})'
   s.rect(off+j*7.5,117+i*7.5,7.7,7.7,color)
 for sy in [-.5,0,.5]:
  pts=[]
  for x in np.linspace(-1,1,140):
   y=sy
   if k:
    for _ in range(10):y-=(y*(1+.35*(x*x+y*y))-sy)/(1+.35*x*x+1.05*y*y)
   pts.append((off+(x+1)*180,117+(y+1)*135))
  s.path(pts,'white',2)
 s.text(off+180,418,'白线：相同的原始行号 / 时间',20,anchor='middle')
foot(s,'渲染输出的第 y 行，不再等于原始传感器的第 y 行；必须查询变换后的行号。')
s.save('photoreal-egocentric-reconstruction','photoreal-rowmap','以确定的教学径向映射逐格计算原始行号；白色等时线由数值求根得到。映射系数 0.35 保存在脚本中，不代表 Aria 标定。')
s=SVG('用像素运动来选时间采样：运动越快，采样越密')
for row,(velocity,label) in enumerate([(1,'慢：同样曝光内仅移动 1 px'),(7,'快：同样曝光内移动 7 px')]):
 y=173+row*165;s.text(55,y-54,label,24);s.line(130,y,880,y,GRAY,2,arrow=True);n=2 if velocity==1 else 9
 for t in np.linspace(0,1,n):s.circ(140+t*720,y,8,BLUE);s.line(140+t*720,y+14,140+t*720,y+34,BLUE,2)
 s.text(948,y+8,f'{n} 次',24,BLUE);s.text(140,y+61,'曝光开始',20);s.text(830,y+61,'曝光结束',20)
foot(s,'论文按可见点的中位像素位移选采样；“中位数 < 1 px”不保证每个点都 < 1 px。')
s.save('photoreal-egocentric-reconstruction','photoreal-sampling','匀速教学例，用不同数量的曝光时刻采样表达快慢运动的区别；图中的 2 与 9 是示意采样数，不是论文每帧固定配置。')

(ROOT/'scripts/aria-series/illustrations.json').write_text(json.dumps(META,ensure_ascii=False,indent=2)+'\n')
print(f'Wrote {len(META)} deterministic figures.')
