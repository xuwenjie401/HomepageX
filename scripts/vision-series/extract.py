"""Reproduce reviewed figure crops. PDFs stay outside the repository.
PYTHONPATH=/path/to/pymupdf python3 scripts/vision-series/extract.py /path/to/papers [paper ...]
"""
import argparse,json,hashlib
from pathlib import Path
import pymupdf as fitz
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('pdf_dir',type=Path);p.add_argument('papers',nargs='*');a=p.parse_args()
sources=json.loads((Path(__file__).parent/'sources.json').read_text())
for key,source in sources.items():
 if a.papers and key not in a.papers:continue
 pdf=a.pdf_dir/(key+'.pdf');doc=fitz.open(pdf)
 if source.get('sha256') and hashlib.sha256(pdf.read_bytes()).hexdigest()!=source['sha256']:raise ValueError(f'Wrong PDF version: {key}')
 out=ROOT/'public/media'/source['article'];out.mkdir(parents=True,exist_ok=True)
 for fig in source['figures']:
  if fig.get('omit'):continue
  page=doc[fig['page']-1];w,h=page.rect.width,page.rect.height
  clip=fitz.Rect(*[v*(w if i%2==0 else h) for i,v in enumerate(fig['box'])])
  pix=page.get_pixmap(matrix=fitz.Matrix(3.3,3.3),clip=clip,alpha=False)
  im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
  dest=out/f"{key}-{fig['id']}.webp";im.save(dest,quality=94,method=6)
  print(dest.relative_to(ROOT),im.size)
