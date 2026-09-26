"""Exact photo homographies and explanatory loss diagrams. Requires Pillow/numpy.
Run this script, then node scripts/typeset-figure-math.mjs.
"""
from pathlib import Path
from html import escape
from PIL import Image, ImageDraw
import numpy as np
import base64, io, json, sys
OUT=Path(__file__).resolve().parents[1]/'public/media/superpoint'
INK,GRAY,BLUE,GREEN,ORANGE='#202a35','#657282','#306ba3','#288379','#c37a30'
def text(x,y,s,size=22,color=INK,anchor='start',weight=400):
 return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}" font-weight="{weight}">{escape(s)}</text>'
def rect(x,y,w,h,fill='white',stroke='#cbd5df',extra=''):
 return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" {extra}/>'
def line(x1,y1,x2,y2,c=GRAY,w=2,extra=''):
 return f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{c}" stroke-width="{w}" fill="none" {extra}/>'
def arrow(x1,y1,x2,y2,c=GRAY): return line(x1,y1,x2,y2,c,2.3,f'marker-end="url(#{c[1:]})"')
def dot(x,y,r=5,c=GREEN): return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" stroke="white" stroke-width="1.5"/>'
def head(title,subtitle): return [text(36,49,title,31,weight=650),text(36,86,subtitle,21,GRAY),line(36,108,1164,108,'#d8dfe6',1)]
def save(name,title,desc,h,p):
 defs=''.join(f'<marker id="{c[1:]}" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="{c}"/></marker>' for c in [GRAY,BLUE,GREEN,ORANGE])
 (OUT/name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="{h}" viewBox="0 0 1200 {h}" role="img" aria-labelledby="title desc"><title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc><defs>{defs}</defs><rect width="1200" height="{h}" fill="white"/><g font-family="Noto Sans CJK SC,Microsoft YaHei,sans-serif">'+''.join(p)+'</g></svg>')
def raster(im,x,y,w,h):
 b=io.BytesIO();im.save(b,format='JPEG',quality=92)
 return f'<image x="{x}" y="{y}" width="{w}" height="{h}" xlink:href="data:image/jpeg;base64,{base64.b64encode(b.getvalue()).decode()}"/>'

# Same source pixels; backward mapping is exactly the inverse of the annotated H.
base=OUT/'homography-source.webp'
if len(sys.argv)>1:
 Image.open(sys.argv[1]).convert('RGB').resize((960,720),Image.Resampling.LANCZOS).save(base,quality=94,method=6)
im=Image.open(base).resize((640,480),Image.Resampling.LANCZOS)
grid=im.copy();d=ImageDraw.Draw(grid,'RGBA')
for x in range(80,640,80): d.line((x,0,x,479),fill=(240,246,255,135),width=1)
for y in range(80,480,80): d.line((0,y,639,y),fill=(240,246,255,135),width=1)
def centered(A):
 T=np.array([[1,0,320],[0,1,240],[0,0,1.]])
 return T@A@np.linalg.inv(T)
a=np.deg2rad(15)
matrices=[np.eye(3),np.array([[1,0,60],[0,1,30],[0,0,1.]]),centered(np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1.]])),centered(np.array([[.82,.20,0],[0,.82,0],[0,0,1.]])),np.array([[1,.12,20],[.04,1,-10],[.0006,-.00025,1.]])]
titles=['(a) 原始图像','(b) 平移','(c) 绕中心旋转 15°','(d) 仿射：缩放 + 错切','(e) 透视：缩放随位置变化','(f) 透视变换的有效区域']
notes=['坐标框架：640 × 480 像素','右移 60，下移 30 像素','直角与平行关系保持','平行线仍然平行','直线保持，平行关系可以改变','白色可回采样；灰色无源像素']
points=[(140,120),(300,150),(490,350),(120,375)];colors=[BLUE,GREEN,ORANGE,'#8c609e']
p=head('单应变换如何改变同一张图片？','网格和四个彩点随源图一起运动；所有面板采用同一个目标画布。')
for i in range(6):
 x=36+(i%3)*388;y=158+(i//3)*373
 H=matrices[min(i,4)];inv=np.linalg.inv(H);inv/=inv[2,2]
 source=grid if i<5 else Image.new('RGB',im.size,'white')
 result=source.transform(im.size,Image.Transform.PERSPECTIVE,tuple(inv.flatten()[:8]),resample=Image.Resampling.BICUBIC,fillcolor='#d9dfe5')
 p += [text(x,y-19,titles[i],21,weight=600),raster(result,x,y,352,264),rect(x,y,352,264,'none'),text(x,y+297,notes[i],18,GRAY)]
 if i<5:
  for (px,py),c in zip(points,colors):
   q=H@np.array([px,py,1.]);qx,qy=q[:2]/q[2]
   if 0<=qx<640 and 0<=qy<480: p += [dot(x+qx*.55,y+qy*.55,5,c)]
p += [line(36,858,1164,858,'#d8dfe6',1),text(36,895,r'点坐标：$\mathbf p^{\prime}=\pi(H\tilde{\mathbf p})$       图像采样：$I^{\prime}(\mathbf p^{\prime})=I(\pi(H^{-1}\tilde{\mathbf p}^{\prime}))$',23),text(36,927,'生成场景 + 确定性矩阵变换；这不是相机真实移动后对三维场景的重新拍摄。',18,GRAY)]
save('homography-photo.svg','同一照片的单应变换','平移、旋转、仿射、透视与有效区域对比。像素按逆矩阵采样，彩点按前向矩阵投影。',940,p)
(OUT/'homography-matrices.json').write_text(json.dumps({'source_size':[640,480],'matrices':[m.tolist() for m in matrices],'points':points},indent=2)+'\n')

p=head('联合训练：每一项损失究竟看什么？','两张图、同一组网络参数；检测用伪标签，描述用已知几何对应。')
for row,y in enumerate([178,401]):
 prime="'" if row else ''
 p += [rect(38,y,145,112,'#eff4f8'),text(110,y+45,f'$I{prime}$',30,BLUE,'middle'),text(110,y+81,'图像输入',20,GRAY,'middle'),arrow(190,y+55,251,y+55),rect(265,y,183,112,'#eef4fa'),text(356,y+48,'SuperPoint',25,BLUE,'middle',600),text(356,y+82,'共享参数',20,GRAY,'middle'),arrow(452,y+30,512,y+30,BLUE),arrow(452,y+83,512,y+83,GREEN),text(568,y+39,f'$\\mathcal X{prime}$',27,BLUE,'middle'),text(568,y+92,f'$\\mathcal D{prime}$',27,GREEN,'middle'),arrow(611,y+30,682,y+30,BLUE),rect(698,y-8,440,85,'#f1f6fb'),text(718,y+26,f'$Y{prime}$ → 65 类交叉熵',22,BLUE),text(1120,y+57,f'$\\mathcal L_p(\\mathcal X{prime},Y{prime})$',26,BLUE,'end')]
p += [line(355,291,355,399,BLUE,2,'stroke-dasharray="6 5"'),text(376,347,'权重共享',19,GRAY),
 line(608,261,641,261,GREEN),line(641,261,641,421,GREEN),line(641,440,641,484,GREEN),line(608,484,641,484,GREEN),rect(690,320,448,67,'#eef7f3'),arrow(641,353,679,353,GREEN),text(710,361,r'$H\to S$ → 配对间隔损失',22,GREEN),text(1118,372,r'$\mathcal L_d$',25,GREEN,'end'),
 line(36,563,1164,563,'#d8dfe6',1),text(600,619,r'$\mathcal L=\mathcal L_p(\mathcal X,Y)+\mathcal L_p(\mathcal X^{\prime},Y^{\prime})+\lambda\mathcal L_d$',31,INK,'middle'),text(600,673,'定位与辨识各有监督，再通过共享编码器共同更新特征。',23,GRAY,'middle')]
save('loss-overview.svg','SuperPoint 联合损失的监督来源','两路共享网络的检测损失与几何对应驱动的描述损失。',720,p)

p=head('检测损失：把概率交给正确的格内位置','一格 64 个像素位置 + 1 个无点类别；不是 64 次独立二分类。')
x,y,step=55,164,29
for r in range(8):
 for c in range(8): p += [rect(x+c*step,y+r*step,step,step,'#d7e7f4' if (r,c)==(3,5) else '#f5f7f9')]
p += [dot(x+5.5*step,y+3.5*step,8,BLUE),text(170,433,'一个有标签点的 cell',21,GRAY,'middle'),arrow(300,275,356,275),text(546,167,'目标类别的概率',23,weight=600,anchor='middle')]
for j,(value,label) in enumerate([(.1,'训练前'),(.8,'训练后')]):
 yy=217+j*92;p += [text(380,yy+23,label,20,GRAY),rect(458,yy,240,28,'#edf1f4','none'),rect(458,yy,240*value,28,BLUE,'none'),text(716,yy+23,f'{value:.2f}',24,BLUE)]
p += [line(803,151,803,423,'#d8dfe6',1),text(839,184,'对应的交叉熵',23,weight=600),text(840,244,r'$-\log(0.10)\approx2.303$',24),text(840,336,r'$-\log(0.80)\approx0.223$',24,GREEN),text(383,418,'目标更可信 → 损失更小',24,GREEN),line(36,460,1164,460,'#d8dfe6',1),text(36,504,'没有标签点的 cell：把目标换成 dustbin，仍用同一条交叉熵。',23),text(36,545,r'在所有 $C=H_cW_c$ 个 cell 上平均；原图和变换图分别计算。',21,GRAY)]
save('loss-detector.svg','65类检测交叉熵','目标像素的概率从0.10提升至0.80，负对数损失相应下降。',570,p)

p=head('描述监督：先用几何决定哪些配对为正','距离阈值施加在输入图像坐标；不是从当前描述子的相似度猜标签。')
# Explicit target geometry: projected p1=(4,0), p2=(16,16); q1=(0,0), q2=(8,0), q3=(16,16).
ox,oy,scale=426,217,8
for gx in range(-8,25,8):
 for gy in range(-8,25,8): p += [dot(ox+gx*scale,oy+gy*scale,3,'#a8b5c0')]
p += [f'<circle cx="{ox+32}" cy="{oy}" r="64" fill="#288379" fill-opacity=".08" stroke="{GREEN}" stroke-width="2"/>',dot(ox+32,oy,6,GREEN),text(ox+32,oy-84,'8 px 半径',19,GREEN,'middle')]
for j,(qx,qy) in enumerate([(0,0),(8,0),(16,16)]):
 p += [dot(ox+qx*scale,oy+qy*scale,7,BLUE),text(ox+qx*scale+12,oy+qy*scale+26,f'$\\mathbf q_{j+1}$',22,BLUE)]
p += [dot(99,262,7,GREEN),text(79,304,r'$\mathbf p_1$',25,GREEN),arrow(126,260,352,221,GREEN),text(223,225,r'$\pi(H\tilde{\mathbf p}_1)$',24,GREEN,'middle'),text(377,421,'目标图的粗网格中心',22,GRAY),line(692,143,692,445,'#d8dfe6',1),text(914,163,'截取两行 × 三列配对',23,weight=600,anchor='middle')]
for j in range(3):p += [text(837+j*96,215,f'$\\mathbf q_{j+1}$',23,BLUE,'middle')]
for i,row in enumerate([[1,1,0],[0,0,1]]):
 p += [text(758,274+i*78,f'$\\mathbf p_{i+1}$',23,GREEN,'middle')]
 for j,value in enumerate(row):
  p += [rect(797+j*96,236+i*78,80,60,'#e2f2ec' if value else '#f6eee5'),text(837+j*96,276+i*78,str(value),27,GREEN if value else ORANGE,'middle')]
p += [text(940,423,'1：正对应     0：负对应',20,GRAY,'middle'),line(36,466,1164,466,'#d8dfe6',1),text(36,509,r'$s_{ij}=1\quad\Longleftrightarrow\quad\|\pi(H\tilde{\mathbf p}_i)-\mathbf q_j\|_2\le8$',27),text(36,555,'上图两个相邻中心都在绿色圆内：训练正对应不必一对一。',23),text(36,591,'完整训练使用两图所有粗网格 cell 的两两组合；右侧只截取一个小例子。',19,GRAY)]
save('loss-correspondence.svg','几何构造描述子正负对应','源点投影后8像素圆内的两个网格中心同时是正对应；配对标签与描述子相似度独立。',610,p)

p=head('间隔损失：正例拉近，负例只推到足够远','横轴是单位描述子的点积，也就是余弦相似度。')
for k in range(2):
 x=91+k*594;y=433;w=412;h=236
 f=lambda a:max(0,1-a) if k==0 else max(0,a-.2)
 maxy=2 if k==0 else 1
 X=lambda a:x+(a+1)/2*w
 Y=lambda v:y-v/maxy*h
 p += [text(x+200,151,'(a) 正对应 · 未乘权重' if k==0 else '(b) 负对应',25,GREEN if k==0 else ORANGE,'middle',600),arrow(x,y,x+w+24,y),arrow(x,y,x,y-h-18),text(x+w+32,y+7,r'$a$',21),text(x-17,y-h-26,r'$\ell$',21)]
 for a in [-1,0,.2,1]:
  p += [line(X(a),y,X(a),y+6),text(X(a),y+30,str(a),18,GRAY,'middle')]
 for v in ([1,2] if k==0 else [.5,1]):
  p += [line(x,Y(v),x+w,Y(v),'#e1e7ec',1),text(x-12,Y(v)+6,str(v),17,GRAY,'end')]
 c=GREEN if k==0 else ORANGE
 points=' '.join(f'{X(a)},{Y(f(a))}' for a in np.linspace(-1,1,101))
 p += [f'<polyline points="{points}" stroke="{c}" stroke-width="3.5" fill="none"/>',dot(X(.7),Y(f(.7)),6,c),text(X(.7)-9,Y(f(.7))-20,'(0.7, 0.3)' if k==0 else '(0.7, 0.5)',19,c,'end')]
 p += [arrow(X(-.4),Y(f(-.4))+25,X(.2),Y(f(.2))+25,c)] if k==0 else [arrow(X(.85)-14,Y(.65)-18,X(.35)-14,Y(.15)-18,c)]
 p += [text(x+190,508,r'$\max(0,1-a)$' if k==0 else r'$\max(0,a-0.2)$',25,c,'middle')]
p += [text(600,557,r'正例项乘 $\lambda_d=250$；对全部配对平均以后，再由 $\lambda=10^{-4}$ 平衡任务。',21,GRAY,'middle')]
save('loss-hinge.svg','描述子正负间隔损失曲线','按论文正间隔1和负间隔0.2精确绘制，显示相似度0.7时的两种惩罚。',580,p)
print('Generated photo homographies and four loss diagrams')
