"""Generate the article's original, dependency-free SVG explanatory figures."""
from pathlib import Path
from html import escape

OUT = Path(__file__).resolve().parents[1] / 'public/media/superpoint'
INK, MUTED, GREEN, RUST = '#292b27', '#666c63', '#376d5b', '#a84d30'


def text(x, y, value, size=22, color=INK, weight=400, anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" font-weight="{weight}" text-anchor="{anchor}">{escape(value)}</text>'


def box(x, y, w, h, fill='#fff', stroke='#d9ddd3'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}"/>'


def arrow(x1, y1, x2, y2, color=GREEN):
    return f'<path d="M{x1},{y1} L{x2},{y2}" stroke="{color}" stroke-width="2.5" fill="none" marker-end="url(#arrow)"/>'


def save(name, title, desc, height, parts):
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title><desc id="desc">{escape(desc)}</desc>
<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="{GREEN}"/></marker></defs>
<rect width="1000" height="{height}" rx="18" fill="#f0f1e9"/>
<g font-family="'Noto Sans CJK SC','Microsoft YaHei',sans-serif">{''.join(parts)}</g></svg>'''
    (OUT / name).write_text(svg)


p = [text(38, 48, '先造出监督，再把监督压进一个网络', 29, weight=650), text(38, 82, '训练时多看几次；部署时只需一次前向传播。', 20, MUTED)]
steps = [
    ('01', '合成几何图形', '程序知道角点坐标', '监督训练 → MagicPoint', GREEN),
    ('02', '没有标注的真实照片', '变换 → 检测 → 对齐 → 聚合', '生成更稳定的伪标签', RUST),
    ('03', '真实图像与变换后的图像', '伪标签教检测；单应关系教描述', '联合训练 → SuperPoint', GREEN),
]
for i, (n, title, sub, end, color) in enumerate(steps):
    y = 112 + i * 150
    p += [box(38, y, 924, 122), text(65, y + 48, n, 28, color, 700), text(133, y + 40, title, 24, weight=600), text(133, y + 78, sub, 20, MUTED), text(600, y + 66, end, 20, color, 600)]
    if i < 2:
        p += [arrow(93, y + 125, 93, y + 147)]
p += [box(38, 583, 924, 108, '#e1ebe4', '#b6cebf'), text(65, 624, '部署', 23, GREEN, 650), text(160, 624, '图像 → 共享编码器 → 关键点 + 描述子', 24, GREEN, 600), text(160, 660, '描述子匹配、RANSAC、位姿估计是后续步骤。', 20, MUTED)]
save('learning-path.svg', 'SuperPoint 的训练与部署流程', '三个训练阶段：合成监督预训练、真实图像伪标注、联合训练；部署时一次前向输出点与描述子。', 720, p)

p = [text(38, 48, '聚合之前，先让同一个点回到同一个位置', 28, weight=650), text(38, 83, '三次预测的教学示意；圆点代表检测响应，非模型实测。', 20, MUTED)]
for i in range(3):
    x = 38 + i * 322
    p += [box(x, 110, 280, 225), text(x+20, 143, ['原图坐标', '平移后的坐标', '旋转后的坐标'][i], 22, weight=600)]
    ox, oy = x+140, 245
    transforms = ['', 'translate(28,-20)', 'rotate(22)']
    p += [f'<g transform="translate({ox},{oy})"><g transform="{transforms[i]}"><path d="M-72,46 L-72,-45 L55,-45 L55,46" fill="none" stroke="#9ba69c" stroke-width="5"/>']
    for dx,dy in [(-72,-45),(55,-45)]:
        p += [f'<circle cx="{dx}" cy="{dy}" r="8" fill="{GREEN}"/>']
    if i == 1:
        p += [f'<circle cx="-12" cy="20" r="7" fill="{RUST}"/>']
    p += ['</g></g>', arrow(x+140,350,x+140,407), text(x+155,385,['恒等映射','逆平移','逆旋转'][i],19,GREEN)]
    p += [box(x,425,280,155), f'<path d="M{x+68},548 L{x+68},467 L{x+195},467 L{x+195},548" fill="none" stroke="#9ba69c" stroke-width="4"/>']
    for dx in [68,195]:
        p += [f'<circle cx="{x+dx}" cy="467" r="8" fill="{GREEN}"/>']
    if i == 1:
        p += [f'<circle cx="{x+128}" cy="532" r="7" fill="{RUST}"/>']
p += [text(38,625,'对齐后：稳定角点的响应重合，偶发响应只出现一次。',23,GREEN,600), text(38,665,'只在有效可见区域内求平均；越界区域不能当作“没有角点”。',21,MUTED)]
save('align-before-average.svg','为什么热力图必须先对齐再聚合','同一几何角点经过平移、旋转后位置不同；逆变换后稳定响应对齐，偶发响应减弱。',705,p)

p = [text(38,48,'65 个通道，回答一个 8 × 8 小格的问题',28,weight=650),text(38,83,'64 个位置 + 1 个“没有点”；不是 65 种语义类别。',21,MUTED),box(38,115,370,394),text(65,155,'一个 cell 的 8 × 8 像素',24,weight=600)]
for row in range(8):
    for col in range(8):
        x,y=83+col*34,184+row*34
        hot=row==2 and col==5
        p += [f'<rect x="{x}" y="{y}" width="32" height="32" rx="3" fill="{GREEN if hot else "#e7ebe3"}"/>']
        if hot:
            p += [text(x+16,y+23,'21',16,'#fff',600,'middle')]
p += [text(65,485,'示例：行 2、列 5 → 通道 21',19,MUTED),arrow(427,300,490,300),box(514,115,448,180),text(541,155,'在通道维做 Softmax',24,weight=600),text(541,199,'$p_0+p_1+\\cdots+p_{63}+p_{\\varnothing}=1$',23,GREEN),text(541,239,'$p_{\\varnothing}$：这个 cell 没有兴趣点',21,MUTED),arrow(738,310,738,350),box(514,370,448,139),text(541,410,'丢掉 $p_{\\varnothing}$，把 64 项排回 8 × 8',21,weight=600),text(541,451,'所有 cell 拼成全分辨率热力图',21,GREEN),text(541,484,'随后做阈值筛选与 NMS',19,MUTED)]
p += [box(38,543,924,111,'#f6e9df','#e2cbbd'),text(65,582,'注意：低分辨率特征 ≠ 只能每隔 8 像素检测一个点',23,RUST,600),text(65,619,'通道编码恢复格内像素位置；原始解码本身不预测亚像素偏移。',21,MUTED)]
save('cell-decoder.svg','65 通道检测头的像素重排','以零起始编号展示一个八乘八 cell：行二列五对应第21通道；Softmax后去掉无点通道，再重排为像素热力图。',687,p)
print('Generated 3 original SVG figures in', OUT)
