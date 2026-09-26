"""Original scientific-style diagrams. Run with Python 3; no dependencies."""
from html import escape
from pathlib import Path
from math import sqrt

OUT = Path(__file__).resolve().parents[1] / 'public/media/superpoint'
INK, GRAY, BLUE, ORANGE, GREEN = '#202a35', '#657282', '#306ba3', '#c37a30', '#288379'


def text(x, y, value, size=22, color=INK, weight=400, anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(value)}</text>'


def rect(x, y, w, h, fill='white', stroke='#d8dfe6', radius=3, extra=''):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}" {extra}/>'


def line(x1, y1, x2, y2, color=GRAY, width=2, extra=''):
    return f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="{width}" {extra}/>'


def arrow(x1, y1, x2, y2, color=GRAY, both=False):
    return line(x1, y1, x2, y2, color, 2.3,
                f'marker-end="url(#{color[1:]})"' + (f' marker-start="url(#{color[1:]}-start)"' if both else ''))


def path(points, color=GRAY):
    return f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.3" marker-end="url(#{color[1:]})"/>'


def dot(x, y, r=5, color=GREEN, extra=''):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" {extra}/>'


def save(name, title, desc, width, height, p):
    markers = ''.join(
        f'<marker id="{c[1:]}{suffix}" markerWidth="7" markerHeight="7" refX="{ref}" refY="3.5" orient="auto"><path d="{d}" fill="{c}"/></marker>'
        for c in [GRAY, BLUE, ORANGE, GREEN]
        for suffix, ref, d in [('', '6', 'M0,0 L7,3.5 L0,7 Z'), ('-start', '1', 'M7,0 L0,3.5 L7,7 Z')])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">'
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc><defs>{markers}</defs>'
        f'<rect width="{width}" height="{height}" fill="white"/>'
        f'<g font-family="Noto Sans CJK SC,Microsoft YaHei,sans-serif">{"".join(p)}</g></svg>', encoding='utf-8')


# Figure 1: qualitative local SSD geometry. Contours are intentionally schematic,
# not a measured response or a SuperPoint output.
p = [text(36, 48, '为什么角点比白墙、直边更容易定位？', 31, weight=650),
     text(36, 85, '移动同一个小图块，观察外观变化与匹配误差。', 22, GRAY),
     line(36, 108, 1164, 108, '#cdd5de', 1)]
titles = ['(a) 平坦区域 · 白墙', '(b) 单一边缘 · 桌沿', '(c) 角点 · 书角']
conclusions = ['两个方向都难定位', '沿边方向仍有歧义', '两个方向都能约束']
details = ['向各个方向移动，图块依然相似', '沿边移动相似，跨边移动变化大', '沿任意方向移动，图块都会改变']
for i in range(3):
    left, cx = 36 + i * 388, 212 + i * 388
    if i:
        p += [line(left-18, 132, left-18, 748, '#e0e5ea', 1)]
    p += [text(cx, 151, titles[i], 25, weight=600, anchor='middle')]
    x, y, w, h = left+28, 177, 296, 193
    p += [rect(x, y, w, h, '#e6e9ec', '#c7cfd7')]
    if i == 1:
        p += [rect(x, y+96, w, 97, '#707d8c', 'none', 0)]
    if i == 2:
        p += [rect(x+148, y+96, 148, 97, '#707d8c', 'none', 0)]
    # Solid blue = original crop; dashed orange = displaced crop.
    p += [rect(cx-40, y+56, 80, 80, 'none', BLUE, 0, 'stroke-width="3"')]
    p += [rect(cx-3, y+56 if i == 1 else y+26, 80, 80, 'none', ORANGE, 0,
               'stroke-width="2.5" stroke-dasharray="7 5"')]
    p += [arrow(cx-75, y+159, cx+74, y+159, BLUE, both=True),
          arrow(x+24, y+47, x+24, y+137, ORANGE, both=True),
          text(cx, 404, details[i], 19, GRAY, anchor='middle'),
          text(cx, 450, '局部匹配误差 $E(\\Delta x,\\Delta y)$', 22, weight=500, anchor='middle')]
    # A flat basin, an elongated trough, and an isolated basin.
    px, py, pw, ph = left+63, 475, 226, 166
    for row in range(22):
        for col in range(30):
            u, v = (col+0.5-15)/15, (row+0.5-11)/11
            e = 0 if i == 0 else (v*v if i == 1 else (u*u+v*v)/1.45)
            e = min(1, e)
            rgb = [round(a+(b-a)*sqrt(e)) for a,b in zip((238,247,251),(55,112,161))]
            color = '#'+''.join(f'{v:02x}' for v in rgb)
            p += [rect(px+col*pw/30, py+row*ph/22, pw/30+0.2, ph/22+0.2, color, 'none', 0)]
    if i == 1:
        for d in [17,36,58,77]:
            for sign in [-1,1]:
                p += [line(px, py+83+sign*d, px+pw, py+83+sign*d, '#437aa1', 1.2)]
    if i == 2:
        for r in [17,35,54,76]:
            p += [f'<ellipse cx="{px+113}" cy="{py+83}" rx="{r*1.2}" ry="{r}" fill="none" stroke="#437aa1" stroke-width="1.2"/>']
    p += [rect(px,py,pw,ph,'none','#c7cfd7',0), dot(px+113,py+83,4,INK),
          arrow(px, py+ph+12, px+pw+10, py+ph+12),
          arrow(px-12, py+ph, px-12, py-7),
          text(px+pw+14, py+ph+19, '$\\Delta x$', 18, GRAY), text(px-23, py-14, '$\\Delta y$',18,GRAY),
          text(cx, 705, conclusions[i], 24, GREEN if i==2 else INK, 650, 'middle'),
          text(cx, 739, ['宽而平的低误差区域','沿 $\\Delta x$ 延伸的低误差谷','局部唯一的低误差中心'][i],20,GRAY,anchor='middle')]
p += [line(36, 765, 1164, 765, '#cdd5de', 1),
      rect(43,789,24,20,'none',BLUE,0,'stroke-width="2.5"'),text(79,806,'原始图块',19,GRAY),
      rect(235,789,24,20,'none',ORANGE,0,'stroke-width="2.5" stroke-dasharray="5 3"'),text(271,806,'移动后图块',19,GRAY),
      rect(471,789,24,20,'#eef7fb','none'),text(507,806,'低误差',19,GRAY),
      rect(635,789,24,20,'#3770a1','none'),text(671,806,'高误差',19,GRAY),
      text(1157,806,'定性示意 · 非实测',19,GRAY,anchor='end'),
      text(36,850,'$E(\\Delta x,\\Delta y)=\\sum_{(x,y)\\in\\Omega}[I(x+\\Delta x,y+\\Delta y)-I(x,y)]^2$',23,INK),
      text(36,884,'求和范围是图块内的像素；下排仅示意局部误差的形状，不表示 SuperPoint 检测分数。',20,GRAY)]
save('patch-localization.svg','平坦区域、边缘和角点的定位歧义',
     '三栏定性对比原始与移动图块，以及局部平方差匹配误差：平坦区两个方向都模糊，水平边缘沿水平方向模糊，角点具有局部唯一低误差中心。',1200,914,p)


# Figure 2: explicit detection/description data paths and geometric verification.
POINTS = [(0.19,0.23),(0.72,0.18),(0.80,0.62),(0.44,0.78),(0.16,0.67),(0.51,0.43)]


def warp(a,b):
    z = .13*a + .04*b + 1
    return (.85*a + .08*b + .065)/z, (.04*a + .88*b + .065)/z


def scene(x,y,w,h,points=False,warped=False):
    # A synthetic planar motif, not an actual image or model inference.
    q = [rect(x,y,w,h,'#eef1f4','#cad2db',2)]
    pts = [warp(a,b) if warped else (a,b) for a,b in POINTS]
    poly = pts[:5]
    q += [f'<polygon points="{" ".join(f"{x+a*w},{y+b*h}" for a,b in poly)}" fill="#c3cbd4" stroke="#8b99aa" stroke-width="1.2"/>',
          line(x+pts[0][0]*w,y+pts[0][1]*h,x+pts[3][0]*w,y+pts[3][1]*h,'#a4aeba',1.2),
          line(x+pts[4][0]*w,y+pts[4][1]*h,x+pts[1][0]*w,y+pts[1][1]*h,'#a4aeba',1.2)]
    if points:
        q += [dot(x+a*w,y+b*h,3.5,GREEN) for a,b in pts]
    return q


def matches(x,y,w,h,inliers_only=False):
    iw=(w-50)/2
    q=scene(x,y,iw,h,True)+scene(x+iw+50,y,iw,h,True,True)
    for a,b in POINTS[:4]:
        c,d=warp(a,b)
        q += [line(x+a*iw,y+b*h,x+iw+50+c*iw,y+d*h,GREEN,1.8)]
    if not inliers_only:
        for i,j in [(4,2),(5,0)]:
            a,b=POINTS[i];c,d=warp(*POINTS[j])
            q += [line(x+a*iw,y+b*h,x+iw+50+c*iw,y+d*h,ORANGE,1.8,'stroke-dasharray="5 4"')]
    q += [text(x+iw/2,y+h+24,'A',18,GRAY,anchor='middle'),text(x+iw*1.5+50,y+h+24,'B',18,GRAY,anchor='middle')]
    return q


p=[text(40,49,'从两张图像，到几何一致的对应点',33,weight=650),
   text(40,89,'SuperPoint 提取局部特征；匹配器和几何验证继续完成对应关系。',23,GRAY),
   line(40,110,1400,110,'#cdd5de',1),
   text(40,153,'(a) 特征提取',25,BLUE,650),text(234,153,'对图像 A、B 分别执行 · 使用相同网络权重',22,GRAY)]
p+=scene(50,203,140,96)+scene(50,333,140,96,warped=True)
p += [text(120,193,'图像 A',19,GRAY,anchor='middle'),text(120,456,'图像 B',19,GRAY,anchor='middle'),
      arrow(202,313,255,313),rect(270,265,168,100,'#f2f6fb','#91adc9'),
      text(354,307,'SuperPoint',25,BLUE,650,'middle'),text(354,340,'共享编码器',21,GRAY,anchor='middle'),
      path('438,291 467,291 467,241 498,241',BLUE),path('438,340 467,340 467,397 498,397',BLUE),
      text(580,191,'检测热力图',22,BLUE,600,'middle'),rect(505,204,150,92,'#162b40','none')]
for a,b in POINTS:
    for radius,opacity in [(14,.1),(9,.18),(5,.4),(2.5,1)]:
        p += [dot(505+a*150,204+b*92,radius,'#8fdccb',f'opacity="{opacity}"')]
p += [text(580,332,'粗网格描述子',22,BLUE,600,'middle')]
palette=['#a6c8dd','#80a8c1','#d9bd90','#7bb6b4','#c7d8e3','#b4bacb']
for r in range(4):
    for c in range(7):
        p += [rect(505+c*22,351+r*22,20,20,palette[(c*3+r*2)%6],'none',0)]
p += [arrow(671,250,715,250,BLUE),arrow(671,397,715,397,BLUE),
      rect(732,203,300,96,'#fafbfd','#cbd6e0'),
      text(882,237,'阈值 → NMS → 边界过滤',22,INK,550,'middle'),
      text(882,275,'按需保留 Top-K 个关键点',21,GRAY,anchor='middle'),
      arrow(884,300,884,349,GREEN),text(904,333,'关键点坐标',19,GREEN),
      rect(732,352,300,91,'#f2f8f6','#a9c6c0'),
      text(882,387,'按坐标插值采样描述子',22,GREEN,550,'middle'),
      text(882,421,'$\\ell_2$ 归一化',21,GRAY,anchor='middle'),
      path('1032,397 1080,397 1080,324 1109,324',GREEN),
      rect(1123,235,270,175,'#fafbfd','#cbd6e0'),
      text(1258,269,'每张图的一组局部特征',21,INK,600,'middle'),
      text(1258,304,'$\\{(x_i,y_i),s_i,\\mathbf d_i\\}$',21,GREEN,anchor='middle')]
for r in range(3):
    p += [dot(1150,329+r*24,4,BLUE)]
    for c in range(8):
        p += [rect(1166+c*25,322+r*24,22,13,palette[(r+c)%6],'none',0)]
p += [text(1258,437,'$\\mathbf d_i\\in\\mathbb R^{256}$',21,GRAY,anchor='middle'),
      line(40,490,1400,490,'#cdd5de',1),
      text(40,532,'(b) 匹配与验证',25,GREEN,650),text(267,532,'以下以平面场景的单应矩阵 $H$ 为例',22,GRAY),
      path('1393,324 1420,324 1420,563 118,563 118,622',GREEN),
      rect(42,638,156,129,'#f2f8f6','#a9c6c0'),text(120,677,'两组特征',23,GREEN,600,'middle'),
      text(120,714,'A：$K_A\\times256$',18,GRAY,anchor='middle'),text(120,745,'B：$K_B\\times256$',18,GRAY,anchor='middle'),
      arrow(201,701,236,701),rect(251,638,174,129,'#fafbfd','#cbd6e0'),
      text(338,677,'描述子匹配',23,INK,550,'middle'),text(338,714,'最近邻',21,GRAY,anchor='middle'),text(338,744,'可加双向一致性',18,GRAY,anchor='middle'),
      arrow(429,701,463,701),text(642,597,'候选匹配',23,INK,600,'middle')]
p += matches(480,628,316,146)
p += [arrow(801,701,835,701),rect(850,638,177,129,'#f2f8f6','#a9c6c0'),
      text(938,677,'RANSAC',24,GREEN,650,'middle'),text(938,712,'估计 $H$',22,GRAY,anchor='middle'),text(938,744,'按几何误差验证',18,GRAY,anchor='middle'),
      arrow(1031,701,1063,701),text(1232,597,'几何一致的内点',23,GREEN,600,'middle')]
p += matches(1080,628,306,146,True)
p += [line(485,836,525,836,GREEN,2),text(539,844,'内点示意',19,GRAY),
      line(708,836,748,836,ORANGE,2,'stroke-dasharray="5 4"'),text(762,844,'外点示意',19,GRAY),
      text(40,905,'分工边界',22,INK,650),text(180,905,'网络输出特征 → 匹配器提出对应 → 几何模型验证一致性',23,INK),
      text(40,945,'图像、热力图、向量颜色与连线均为教学示意；绿色不表示算法预先知道真值。',21,GRAY),
      text(40,978,'一般三维场景需按任务选择基础矩阵、本质矩阵或 PnP，不能一概使用 $H$。',21,GRAY)]
save('inference-pipeline.svg','SuperPoint 推理、描述子匹配与几何验证流程',
     '上半图展示两张图分别通过同一 SuperPoint 的检测和描述分支：热力图经筛选得到关键点，按坐标采样并归一化描述子。下半图展示描述子匹配产生候选，RANSAC按单应模型保留几何一致内点。所有图像和连线均为示意。',1440,1010,p)
print('Generated patch-localization.svg and inference-pipeline.svg')
