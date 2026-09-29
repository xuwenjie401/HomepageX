"""Post-build integrity checks for the five Aria research articles (stdlib + Pillow).
Check generated HTML, not merely Astro's exit status: content errors may be logged
while Astro still writes an empty article page and exits successfully.
"""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
import json,re,xml.etree.ElementTree as ET
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent
sources=json.loads((HERE/'sources.json').read_text())
own=json.loads((HERE/'illustrations.json').read_text())
class Page(HTMLParser):
 def __init__(self):super().__init__();self.ids=[];self.images=[];self.links=[];self.math=0;self.figures=0;self.headings=0;self.errors=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.ids.append(a['id'])
  if tag=='img':self.images.append(a)
  if tag=='a':self.links.append(a)
  if tag=='figure':self.figures+=1
  if tag in ('h2','h3','h4'):self.headings+=1
  if a.get('role')=='math':self.math+=1
  if a.get('data-mml-node')=='merror':self.errors.append(a)
counts=[]
for slug in list(dict.fromkeys(s['article'] for s in sources.values())):
 src=(ROOT/'src/content/blog/3d-perception-and-project-aria'/(slug+'.md')).read_text()
 assert '<!-- figure:' not in src,('Unresolved marker',slug)
 expected=sum(not f.get('omit') for s in sources.values() if s['article']==slug for f in s['figures'])+sum(v['article']==slug for v in own.values())
 path=ROOT/'dist/blog/3d-perception-and-project-aria'/slug/'index.html';html=path.read_text();p=Page();p.feed(html)
 assert p.figures==expected,(slug,'figures',p.figures,expected)
 assert p.headings>15 and p.math>8 and not p.errors,(slug,'Missing body or invalid math')
 assert len(p.ids)==len(set(p.ids)),(slug,'Duplicate anchors')
 for im in p.images:
  assert im.get('alt') and im.get('width') and im.get('height'),(slug,'Image attributes',im)
  url=im['src'];assert url.startswith('/HomepageX/media/'),url
  file=ROOT/'public'/url.removeprefix('/HomepageX/')
  assert file.is_file(),file
  if file.suffix=='.svg':
   e=ET.parse(file).getroot();dims=(int(e.attrib['width']),int(e.attrib['height']))
   assert 'data-mml-node="merror"' not in file.read_text(),file
  else:
   with Image.open(file) as img:dims=img.size;img.verify()
  assert dims==(int(im['width']),int(im['height'])),(file,dims,im)
  assert any(a.get('href')==url and a.get('target')=='_blank' for a in p.links),(slug,'Missing full-size link',url)
 for a in p.links:
  href=a.get('href','')
  if href.startswith('#'):assert unquote(href[1:]) in p.ids,(slug,'Bad anchor',href)
  if href.startswith('/HomepageX/blog/'):
   dest=unquote(urlsplit(href).path).removeprefix('/HomepageX/');assert (ROOT/'dist'/dest/'index.html').exists(),(slug,href)
 counts.append({'slug':slug,'figures':p.figures,'math':p.math,'headings':p.headings,'bytes':path.stat().st_size})
print(json.dumps(counts,ensure_ascii=False,indent=2))
print('PASS: figure coverage, dimensions, alt/full-size links, local article links, anchors and rendered math.')
