"""Extract every numbered figure from arXiv:1712.07629v4. Requires Poppler/Pillow.
Usage: python3 scripts/extract-superpoint-figures.py /path/to/paper.pdf
"""
from pathlib import Path
from PIL import Image
import subprocess, sys, tempfile
OUT=Path(__file__).resolve().parents[1]/'public/media/superpoint'
FIGURES=[
(1,1,'correspondence',(.50,.282,.895,.535)),
(2,2,'training',(.077,.039,.895,.211)),
(3,3,'network',(.504,.074,.894,.221)),
(4,4,'synthetic',(.079,.051,.895,.213)),
(5,5,'adaptation',(.079,.061,.899,.240)),
(6,5,'homographies',(.50,.300,.895,.375)),
(7,6,'iterations',(.505,.087,.897,.300)),
(8,8,'matching',(.080,.089,.899,.477)),
(9,11,'dataset',(.085,.080,.465,.195)),
(10,11,'categories',(.50,.083,.898,.274)),
(11,11,'noise-level',(.50,.345,.90,.485)),
(12,11,'noise-type',(.50,.568,.90,.698)),
(13,12,'blob',(.095,.298,.452,.55)),
(14,12,'adaptation-count',(.51,.088,.89,.265)),
(15,13,'matching-extra',(.080,.080,.898,.837)),
]
if __name__=='__main__':
 with tempfile.TemporaryDirectory() as tmp:
  for page in sorted(set(f[1] for f in FIGURES)):
   root=str(Path(tmp)/'page')
   subprocess.run(['/usr/bin/pdftoppm','-f',str(page),'-l',str(page),'-singlefile','-r','260','-png',sys.argv[1],root],check=True)
   im=Image.open(root+'.png')
   for n,p,name,box in FIGURES:
    if p!=page: continue
    crop=im.crop(tuple(round(v*im.size[i%2]) for i,v in enumerate(box)))
    path=OUT/f'paper-fig{n}-{name}.webp'
    crop.save(path,quality=95,method=6)
    print(path.name,crop.size)
