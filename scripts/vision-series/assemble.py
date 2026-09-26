"""Render reviewed figure markers; regenerate per-article provenance inventories.
Re-run after changing crops, captions or illustrations. Does not rewrite prose.
"""
from pathlib import Path
from html import escape
import json,re
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
sources=json.loads((HERE/'sources.json').read_text())
own=json.loads((HERE/'illustrations.json').read_text())
code=json.loads((HERE/'code-sources.json').read_text())
figures={}
for key,src in sources.items():
 for fig in src['figures']:
  if fig.get('omit'):continue
  name=key+'-'+fig['id'];path=ROOT/'public/media'/src['article']/(name+'.webp')
  w,h=Image.open(path).size
  figures[name]={'article':src['article'],'width':w,'height':h,'file':name+'.webp','caption':fig['caption'],'source':src['url']+'#page='+str(fig['page']),'label':src.get('label',src['title'].split(',')[0])+' 原论文 Figure '+fig['id']}
for name,fig in own.items():figures[name]={**fig,'file':name+'.svg'}
articles=list(dict.fromkeys(v['article'] for v in sources.values()))
for slug in articles:
 p=ROOT/'src/content/blog/sparse-feature-and-visual-recognition'/(slug+'.md');t=p.read_text()
 # Collapse previous generated blocks before numbering again in reading order.
 t=re.sub(r'<!-- vision-figure: ([\w-]+) -->.*?<!-- /vision-figure -->',lambda m:'<!-- figure: '+m[1]+' -->',t,flags=re.S)
 used=[];own_count=0;sections={};section='开篇'
 for line in t.splitlines():
  if line.startswith('##'):section=line.lstrip('# ')
  m=re.search(r'<!-- figure: ([\w-]+) -->',line)
  if m:sections[m[1]]=section
 def render(m):
  global own_count
  name=m[1];f=figures[name]
  assert f['article']==slug,(name,slug)
  assert name not in used,('Duplicate figure',name)
  used.append(name)
  if 'source' not in f:own_count+=1
  label=f.get('label','自制图 '+str(own_count))
  url='/HomepageX/media/'+slug+'/'+f['file']
  cap=escape(label+' · '+f['caption'])
  if 'source' in f:cap+=' <a href="'+escape(f['source'],quote=True)+'" target="_blank" rel="noopener">原文</a>'
  return f'<!-- vision-figure: {name} -->\n<figure>\n  <a href="{url}" target="_blank" rel="noopener"><img src="{url}" width="{f["width"]}" height="{f["height"]}" alt="{escape(label+"："+f["caption"],quote=True)}" loading="lazy" /></a>\n  <figcaption>{cap}</figcaption>\n</figure>\n<!-- /vision-figure -->'
 t=re.sub(r'<!-- figure: ([\w-]+) -->',render,t)
 expected={k for k,v in figures.items() if v['article']==slug}
 assert set(used)==expected,('Figure coverage mismatch',slug,expected-set(used),set(used)-expected)
 p.write_text(t)
 doc=[f'# {slug} 素材与复现记录','',f'正文：[文章源文件](../src/content/blog/sparse-feature-and-visual-recognition/{slug}.md)。核查日期：2026-09-27。', '',f'共 {len(used)} 图：论文原图 {len(used)-own_count}，自制图 {own_count}。按正文顺序编号自制图，原图保留作者图号。','', '## 固定论文与原图清单','', '以下页码按 PDF 文件从 1 开始；裁切框在 `sources.json`，为页宽/页高归一化坐标。提图前先核对 SHA-256；不以网页后续更新的同名文件静默替换。','']
 for key,src in sources.items():
  if src['article']!=slug:continue
  doc += [f'### {src["title"]}','',f'- 来源：[固定论文]({src["url"]})',f'- 本地复现文件名：`{key}.pdf`',f'- SHA-256：`{src["sha256"]}`','','| 图号 | PDF 页 | 放置章节／省略理由 | 内容 |','| --- | --- | --- | --- |']
  for f in src['figures']:
   name=key+'-'+f['id'];loc=('省略：'+str(f['omit'])) if f.get('omit') else sections[name]
   doc.append(f'| {f["id"]} | {f["page"]} | {loc} | {f["caption"]} |')
  doc.append('')
 doc+=['## 自制图与计算假设','','程序精确生成 SVG；没有使用生成式位图，没有虚构模型输出。所有曲线、点阵和轨迹是教学输入或正文公式的计算，不能当论文性能复现。公式统一通过共享 MathJax/STIX2 渲染。','','| 正文顺序 | 文件 | 说明 |','| --- | --- | --- |']
 n=0
 for name in used:
  if name not in own:continue
  n+=1;doc.append(f'| {n} | [{name}.svg](../public/media/{slug}/{name}.svg) | {own[name]["caption"]} |')
 relevant=[v for v in code.values() if slug in v['articles']]
 if relevant:
  doc+=['','## 作者代码核查','','只做源码阅读；未宣称重跑训练或论文基准。以下提交固定本文所讨论的实现。','']
  for v in relevant:
   doc += [f'- [{v["repo"]} @ {v["sha"][:12]}](https://github.com/{v["repo"]}/tree/{v["sha"]})：'+', '.join('`'+f+'`' for f in v['files'])+'。']
 doc+=['','## 复现与验证','','依赖 Python 3、NumPy、Pillow、PyMuPDF，及仓库 Node 依赖。PDF 放在仓库外；已发布图不需要原 PDF 即可浏览。','','```bash','python3 scripts/vision-series/extract.py /absolute/path/to/papers '+ ' '.join(k for k,v in sources.items() if v['article']==slug),'python3 scripts/vision-series/figures.py','node scripts/vision-series/typeset.mjs','python3 scripts/vision-series/assemble.py','npm run build','```','','全系列检查结果见 [制作记录](vision-series-production.md)。重新裁图后应重新运行 assemble，同步真实宽高；重新画图后应先运行 typeset，再检查实际栅格渲染和页面。','']
 (ROOT/'docs'/(slug+'-assets.md')).write_text('\n'.join(doc))
 print(slug,len(used),'figures')
