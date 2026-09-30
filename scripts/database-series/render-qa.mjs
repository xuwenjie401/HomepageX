/** Rasterize the published SVGs and create contact sheets outside the repository. */
import sharp from 'sharp';
import {readFile,mkdir} from 'node:fs/promises';
import path from 'node:path';
const target=process.argv[2];
if(!target || !path.isAbsolute(target)) throw new Error('Supply an absolute external QA directory');
await mkdir(target,{recursive:true});
const meta=JSON.parse(await readFile(new URL('./illustrations.json',import.meta.url),'utf8'));
const keys=Object.keys(meta);
for(const key of keys) await sharp(new URL(`../../public/media/modern-databases/${key}.svg`,import.meta.url).pathname).png().toFile(path.join(target,`${key}.png`));
for(let i=0;i<keys.length;i+=6){
 const images=await Promise.all(keys.slice(i,i+6).map(async(key,j)=>({input:await sharp(path.join(target,`${key}.png`)).resize(900,450).toBuffer(),left:(j%2)*900,top:Math.floor(j/2)*450})));
 await sharp({create:{width:1800,height:1350,channels:3,background:'white'}}).composite(images).png().toFile(path.join(target,`sheet-${i/6+1}.png`));
}
console.log(`Rendered ${keys.length} figures and ${Math.ceil(keys.length/6)} sheets to ${target}`);
