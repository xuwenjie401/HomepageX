"""Validate actual built pages, original SVGs, links and formula presence."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
import re,json,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
meta=json.loads((Path(__file__).parent/'illustrations.json').read_text())
class Page(HTMLParser):
 def __init__(self):super().__init__();self.ids=[];self.images=[];self.links=[];self.math=0;self.errors=[];self.headings=0;self.figures=0;self.captions=0;self.toc=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:self.ids.append(a['id'])
  if tag=='img':self.images.append(a)
  if tag=='a':self.links.append(a)
  if tag=='figure':self.figures+=1
  if tag=='figcaption':self.captions+=1
  if tag in ('h2','h3','h4'):self.headings+=1
  if a.get('role')=='math':self.math+=1
  if a.get('data-mml-node')=='merror':self.errors.append(a)
  if 'article-toc' in a.get('class',''):self.toc=True
report=[]
for p in sorted((ROOT/'src/content/blog/modern-databases').glob('*.md')):
 src=p.read_text();ch=int(p.name[:2]);slug=p.stem;pagefile=ROOT/'dist/blog/modern-databases'/slug/'index.html'
 html=pagefile.read_text();page=Page();page.feed(html)
 expected=sum(v['chapter']==ch for v in meta.values())
 assert '<!-- fig:' not in src and 'data-mml-node="merror"' not in html,(slug,'Unrendered source or invalid formula')
 assert page.figures==page.captions==expected,(slug,'Body / figure count',page.figures,expected)
 assert page.headings>=8 and page.toc and (page.math>0 if ch not in (9,) else True),(slug,'Missing headings, math, or TOC')
 assert len(page.ids)==len(set(page.ids)),(slug,'Duplicate IDs')
 for im in page.images:
  assert im.get('alt') and im.get('width') and im.get('height'),(slug,im)
  url=im['src'];assert url.startswith('/HomepageX/media/modern-databases/'),url
  file=ROOT/'public'/url.removeprefix('/HomepageX/');e=ET.parse(file).getroot()
  assert (e.get('width'),e.get('height'))==(im['width'],im['height']),(file,'Image dimensions')
  assert any(a.get('href')==url and a.get('target')=='_blank' for a in page.links),(file,'Zoom link')
  text=file.read_text();assert not re.search(r'<text\b[^>]*>[^<]*\$',text),(file,'Raw TeX label')
  assert 'data-mml-node="merror"' not in text,file
 for a in page.links:
  href=a.get('href','')
  if href.startswith('#'):assert unquote(href[1:]) in page.ids,(slug,href)
  if href.startswith('/HomepageX/blog/'):
   path=unquote(urlsplit(href).path).removeprefix('/HomepageX/')
   assert (ROOT/'dist'/path/'index.html').is_file(),(slug,href)
 numbers=re.findall(r'<figcaption>自制图 (\d+)',src)
 assert numbers==list(map(str,range(1,expected+1))),(slug,numbers)
 report.append({'article':slug,'figures':page.figures,'headings':page.headings,'math':page.math,'source_chars':len(src)})
assert len(report)==9 and sum(r['figures'] for r in report)==48
index=(ROOT/'dist/blog/modern-databases/index.html').read_text()
assert all(f'/modern-databases/{r["article"]}/' in index for r in report)
print(json.dumps(report,ensure_ascii=False,indent=2))
print('PASS: nine built bodies, 48 figures, dimensions, alt/zoom links, numbering, cross-links, headings, TOC, math and SVG XML.')
