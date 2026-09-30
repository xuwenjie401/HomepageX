"""Idempotently replace figure markers with semantic, zoomable HTML figures."""
from pathlib import Path
from html import escape
import re,json
ROOT=Path(__file__).resolve().parents[2]
meta=json.loads((Path(__file__).parent/'illustrations.json').read_text())
used=[]
for p in sorted((ROOT/'src/content/blog/modern-databases').glob('*.md')):
 text=p.read_text();chapter=int(p.name[:2]);counter=[0]
 def replace(match):
  key=match.group(1);m=meta[key];assert m['chapter']==chapter,(p,key)
  counter[0]+=1;used.append(key);url=f'/HomepageX/media/modern-databases/{key}.svg'
  return f'''<!-- figure:{key}:start -->
<figure>
  <a href="{url}" target="_blank" rel="noopener"><img src="{url}" alt="{escape(m['alt'],quote=True)}" width="{m['width']}" height="{m['height']}" loading="lazy" /></a>
  <figcaption>自制图 {counter[0]} · {escape(m['caption'])} 点击可查看矢量大图。</figcaption>
</figure>
<!-- figure:{key}:end -->'''
 pattern=r'<!-- fig:([a-z-]+) -->|<!-- figure:([a-z-]+):start -->[\s\S]*?<!-- figure:\2:end -->'
 def adapt(m):
  class Match:
   def group(self,_):return m.group(1) or m.group(2)
  return replace(Match())
 text=re.sub(pattern,adapt,text);p.write_text(text);print(p.name,counter[0])
assert len(used)==len(set(used))==len(meta),(len(used),len(meta))
