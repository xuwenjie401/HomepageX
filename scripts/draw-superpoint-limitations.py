"""Five original explanatory SVG figures; Python 3 standard library only."""
from pathlib import Path
from html import escape
from math import exp

OUT = Path(__file__).resolve().parents[1] / 'public/media/superpoint'
INK, GRAY, BLUE, ORANGE, GREEN = '#202a35', '#657282', '#306ba3', '#c37a30', '#288379'


def t(x,y,s,size=22,color=INK,bold=False,anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{650 if bold else 400}" text-anchor="{anchor}">{escape(s)}</text>'


def box(x,y,w,h,fill='#fff',stroke='#d8dfe6',extra=''):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" {extra}/>'


def line(x,y,u,v,color=GRAY,dash=False,arrow=False):
    return f'<path d="M{x},{y} L{u},{v}" fill="none" stroke="{color}" stroke-width="2"'+(' stroke-dasharray="6 5"' if dash else '')+(f' marker-end="url(#{color[1:]})"' if arrow else '')+'/>'


def dot(x,y,r=5,color=GREEN):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'


def ring(x,y,r=10,color=GREEN):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{color}" stroke-width="2.5"/>'


def header(title,sub):
    return [t(36,47,title,30,bold=True),t(36,84,sub,21,GRAY),line(36,107,1164,107,'#d8dfe6')]


def footer(p,y,insight,note):
    p += [line(36,y,1164,y,'#d8dfe6'),t(36,y+40,insight,23,GREEN,True),t(36,y+77,note,19,GRAY)]


def save(name,title,desc,height,p):
    markers=''.join(f'<marker id="{c[1:]}" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="{c}"/></marker>' for c in [GRAY,BLUE,ORANGE,GREEN])
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-labelledby="title desc"><title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc><defs>{markers}</defs><rect width="1200" height="{height}" fill="white"/><g font-family="Noto Sans CJK SC,Microsoft YaHei,sans-serif">'+''.join(p)+'</g></svg>',encoding='utf-8')


# 1. Two depth layers under horizontal camera translation. Wall shift -24,
# foreground shift -65; wall-plane H adds +24 and leaves -41 foreground residual.
p=header('一张 $H$ 能对齐墙面，却未必能对齐前景','深度不同 → 视差不同；重新显露的背景也无法从原图凭空恢复。')
for i,title in enumerate(['(a) 原始视图 A','(b) 相机横向移动后的 B','(c) 用墙面的 $H$ 对齐 B']):
    x=42+i*389; y=173
    p += [t(x+164,146,title,23,bold=True,anchor='middle'),box(x,y,328,226,'#f1f5f8')]
    wallshift=-24 if i==1 else 0
    for col in range(1,8):
        wx=x+col*40+wallshift
        p += [line(wx,y,wx,y+226,'#c6d3df')]
    for row in range(1,5):p += [line(x,y+row*45,x+328,y+row*45,'#c6d3df')]
    fg=[150,85,109][i]
    if i==2:
        p += [box(x+159,y+28,41,183,'#d6eee8','none'),box(x+150,y+28,50,183,'none',ORANGE,'stroke-dasharray="7 5" stroke-width="2"')]
    p += [box(x+fg,y+28,50,183,'#dab384','#b57c39'),dot(x+fg+25,y+74,6,ORANGE),dot(x+280+wallshift,y+45,6,BLUE)]
    if i==0:p += [t(x+28,432,'远处墙面',20,BLUE),t(x+178,432,'近处立柱',20,ORANGE)]
    elif i==1:
        p += [t(x+10,432,'墙面位移 −24；立柱位移 −65',19,GRAY),t(x+10,462,'像素单位 · 人工设定的教学例子',18,GRAY)]
    else:
        p += [line(x+134,y+244,x+175,y+244,ORANGE,arrow=True),t(x+12,462,'墙面对齐后，立柱仍残留 41 px 偏差',18,ORANGE)]
p += [box(42,493,1110,91,'#f7fafc'),t(64,526,'横向平移的简化针孔模型：$\\Delta x=-f\\,t_x/Z$',23,bold=True),
      t(64,563,'$Z$ 越小，位移幅度越大。右图虚框：原立柱位置；浅绿：移动后新显露的背景。',20,GRAY)]
footer(p,611,'改进方向：真实图像对 + 深度 / 位姿 + 可见性判断','几何示意；只讨论平移与深度差异。纯旋转或同一平面仍可由合适的单应关系描述。')
save('limitation-parallax.svg','不同深度造成单应对齐后的视差残差','墙面和前景立柱随相机平移产生不同位移。以墙面估计的单应关系无法同时消除前景视差，也无法从原图恢复新显露区域。',715,p)


# 2. Repeatable detections in periodic texture, but ambiguous local appearance.
def windows(x,y):
    q=[box(x,y,340,220,'#edf1f5')]
    for r in range(2):
        for c in range(3):
            xx,yy=x+28+c*104,y+26+r*103
            q += [box(xx,yy,70,70,'#acbfd0','#738ca4'),line(xx+35,yy,xx+35,yy+70,'#edf1f5'),line(xx,yy+35,xx+70,yy+35,'#edf1f5'),dot(xx,yy,4,BLUE)]
    return q
p=header('能反复检测出来，不等于能唯一匹配','重复窗格的角点很稳定，但它们的局部外观可能几乎相同。')
p += [t(229,151,'图像 A：选中一个窗角',24,bold=True,anchor='middle'),t(969,151,'图像 B：多个相似候选',24,bold=True,anchor='middle')]
p += windows(59,182)+windows(799,182)
sx,sy=191,208
p += [ring(sx,sy,12,GREEN)]
for dx,dy in [(827,208),(931,311),(1035,311)]:
    p += [line(sx+14,sy,dx-14,dy,ORANGE,True,True),ring(dx,dy,12,ORANGE)]
p += [box(456,283,282,91,'#fff'),t(597,319,'三个图块都像这个窗角',21,bold=True,anchor='middle'),t(597,351,'局部描述难以拉开差距',20,GRAY,anchor='middle'),
      box(59,443,504,118,'#f2f8f6'),t(83,482,'重复性：同一物理点还能找到吗？',23,GREEN,True),t(83,524,'回答的是检测在不同图像中的稳定性。',21,GRAY),
      box(635,443,504,118,'#fbf7f0'),t(659,482,'可靠性：这个点容易匹配对吗？',23,ORANGE,True),t(659,524,'稳定的周期纹理，也可能具有强歧义。',21,GRAY)]
footer(p,599,'改进方向：除了重复性，还评估描述子的可辨识度','人工构造的重复纹理与候选关系；不是模型输出。完全对称的纹理未必仅凭局部外观就可消歧。')
save('limitation-ambiguity.svg','重复性不等于描述子可靠性','图像A中的一个稳定窗角，对应图像B中的多个相似局部候选。区分检测的重复性与描述子的可辨识度。',703,p)


# 3. Local descriptor ties vs relational evidence. Not an architecture diagram.
p=header('局部外观相似时，让周围的点也参与判断','邻域关系与跨图信息可以帮助重新评估候选，而不是只比较两个孤立向量。')
p += [t(47,152,'(a) 只看局部',24,bold=True),t(48,187,'两个候选的图块很像',20,GRAY)]
for x,label in [(385,'查询点'),(784,'候选 1'),(1080,'候选 2')]:
    p += [box(x-40,140,80,75,'#e6edf4'),line(x-30,191,x+27,159,BLUE),dot(x,177,7,BLUE),t(x,248,label,21,GRAY,anchor='middle')]
p += [line(432,175,733,175,ORANGE,True,True),line(432,205,1030,205,ORANGE,True,True),line(36,277,1164,277,'#d8dfe6'),t(47,319,'(b) 加入上下文',24,bold=True),t(48,354,'比较点与周围结构的关系',20,GRAY)]
def graph(cx,cy,kind):
    offsets=[(-50,-65),(65,-25),(30,62)] if kind!='wrong' else [(-64,12),(15,-72),(78,60)]
    q=[]
    for j,(dx,dy) in enumerate(offsets):
        q += [line(cx,cy,cx+dx,cy+dy,'#aebcca'),dot(cx+dx,cy+dy,7,ORANGE if j==0 else GRAY)]
    q += [dot(cx,cy,9,BLUE),ring(cx,cy,16,GREEN if kind=='correct' else BLUE)]
    return q
p += graph(385,435,'query')+graph(784,435,'correct')+graph(1080,435,'wrong')
p += [line(409,432,759,432,GREEN,False,True),line(409,465,1056,465,ORANGE,True,True),
      t(587,413,'上下文提供支持',20,GREEN,anchor='middle'),t(933,508,'周围关系不同',19,ORANGE,anchor='middle'),
      t(784,550,'重新评估候选 1',20,GREEN,anchor='middle'),t(1080,550,'候选 2 可被降权',20,ORANGE,anchor='middle')]
footer(p,586,'改进方向：图内聚合 + 跨图交互 + 匹配分配 / 拒绝匹配','关系示意，不是 SuperGlue 的网络结构图，也不是要求邻居距离保持不变的硬规则。')
save('limitation-context.svg','利用周围结构辅助消除局部匹配歧义','局部图块相似的两个候选，在考虑邻域关系后得到不同支持。表示上下文作用，不表示SuperGlue的具体层结构或硬距离约束。',690,p)


# 4. Detector bottleneck vs coarse-to-fine feature matching.
def lowtexture(x,y,grid=False):
    q=[box(x,y,287,157,'#f1f3f5'),box(x+16,y+22,44,114,'#bdc9d3','none'),line(x+16,y+136,x+267,y+136,'#bac7d2')]
    if grid:
        for i in range(1,8):q += [line(x+i*35,y,x+i*35,y+157,'#d2dce5')]
        for i in range(1,5):q += [line(x,y+i*31,x+287,y+i*31,'#d2dce5')]
        q += [box(x+140,y+62,35,31,'#bee0d8',GREEN,'stroke-width="2.5"')]
    else:
        q += [dot(x+16,y+22,5,BLUE),dot(x+60,y+22,5,BLUE),dot(x+60,y+136,5,BLUE),box(x+113,y+42,91,68,'none',ORANGE,'stroke-dasharray="6 5"')]
    return q
p=header('候选点没被检测出来，后面的匹配器就无从选择','从独立检测的稀疏点集，转向两图交互后的粗到细匹配。')
p += [t(43,151,'(a) 先检测，再匹配',24,bold=True)]+lowtexture(47,177)+lowtexture(479,177)
p += [line(340,254,469,254,ORANGE,True,True),t(407,225,'区域内缺点',18,ORANGE,anchor='middle'),
      t(824,222,'点集没有覆盖这里',24,ORANGE,True),t(824,266,'匹配器只能处理收到的候选',20,GRAY),t(824,304,'提高匹配能力，也不等于补点',20,GRAY),
      line(36,374,1164,374,'#d8dfe6'),t(43,419,'(b) 特征交互，粗到细匹配',24,bold=True)]
p += lowtexture(47,449,True)+lowtexture(479,449,True)
p += [line(221,526,619,526,GREEN,False,True),t(407,483,'粗网格候选',19,GREEN,anchor='middle'),line(779,526,825,526,GREEN,False,True),
      box(849,463,114,114,'#f4f8fa'),box(875,489,61,61,'none','#a5b6c6'),dot(905,519,5,BLUE),dot(912,513,4,GREEN),line(905,519,912,513,GREEN,False,True),
      t(988,505,'局部细化',23,GREEN,True),t(988,546,'得到更精细坐标',19,GRAY)]
footer(p,652,'改进方向：解除对独立稀疏检测点的依赖，而不是承诺处处都能匹配','受 LoFTR 思路启发的机制示意；弱纹理仍需上下文信息，完全无信息或不可见区域仍可能无法匹配。')
save('limitation-detector.svg','稀疏检测瓶颈与粗到细匹配','对比弱纹理区域未被检测器选入点集，与在粗网格上交互匹配再局部细化的路径。不声称完全空白或遮挡区域可以可靠匹配。',756,p)


# 5. Continuous coordinates and why averaging two peaks can be wrong.
p=header('从整数像素，到更精细的位置估计','亚像素细化引入连续坐标；但“做一次平均”并不自动意味着更准确。')
for x,label in [(211,'(a) 离散点与连续坐标'),(601,'(b) 单峰：可以局部细化'),(990,'(c) 双峰：均值可能落空')]:
    p += [t(x,150,label,23,bold=True,anchor='middle')]
for x in [407,796]:p += [line(x,174,x,519,'#e0e5ea')]
gx,gy,step=88,193,48
for i in range(6):
    p += [line(gx+i*step,gy,gx+i*step,gy+240,'#d6dfe7'),line(gx,gy+i*step,gx+240,gy+i*step,'#d6dfe7')]
ix,iy=gx+2.5*step,gy+2.5*step
tx,ty=ix+.35*step,iy+.2*step
p += [box(ix-24,iy-24,48,48,'#e0ecf5',BLUE),dot(ix,iy,6,BLUE),ring(tx,ty,7,GREEN),line(ix,iy,tx,ty,GREEN,False,True),
      t(211,470,'整数峰 (2, 2)',21,BLUE,anchor='middle'),t(211,504,'示意真值 (2.35, 2.20)',20,GREEN,anchor='middle')]
for panel,ox in [(1,455),(2,846)]:
    oy=408; ww=270; hh=190
    p += [line(ox,oy,ox+ww+8,oy,GRAY,arrow=True),line(ox,oy,ox,oy-hh-14,GRAY,arrow=True),t(ox+ww,oy+29,'位置 $x$',18,GRAY,anchor='end'),t(ox-5,oy-hh-23,'响应（示意）',18,GRAY)]
    values=[]
    for j in range(141):
        v=j/140*4
        a=exp(-((v-2.35)/.62)**2) if panel==1 else .91*(exp(-((v-1)/.39)**2)+exp(-((v-3)/.39)**2))
        values.append((ox+v/4*ww,oy-a*hh))
    p += [f'<polyline points="{" ".join(f"{x:.2f},{y:.2f}" for x,y in values)}" fill="none" stroke="{BLUE}" stroke-width="2.5"/>']
    for v in range(5):
        a=exp(-((v-2.35)/.62)**2) if panel==1 else .91*(exp(-((v-1)/.39)**2)+exp(-((v-3)/.39)**2))
        p += [dot(ox+v/4*ww,oy-a*hh,4,BLUE)]
    vx=ox+(2.35 if panel==1 else 2)/4*ww
    p += [line(vx,oy-190,vx,oy,GREEN if panel==1 else ORANGE,True),
          t(ox+ww/2,470,'利用局部响应估计峰位置' if panel==1 else '两峰等权 → 均值落在中间',20,GREEN if panel==1 else ORANGE,anchor='middle'),
          t(ox+ww/2,504,'无需把坐标限制在整数上' if panel==1 else '中间却可能没有有效响应',20,GRAY,anchor='middle')]
p += [t(48,561,'蓝点：整数采样 / 整数位置    绿标记：连续位置    橙虚线：双峰均值',20,GRAY)]
footer(p,592,'改进方向：局部坐标细化，并用严格定位误差检验收益','网格坐标与曲线均为人工示意；不是 SuperPoint 原生亚像素输出，也不是细化效果的实验结果。')
save('limitation-subpixel.svg','亚像素细化与双峰平均的局限','整数像素位置与连续真值的差异；单峰局部细化；双峰等权平均可能落在无有效响应的中间位置。所有曲线均为教学示意。',696,p)
print('Generated five limitation figures.')
