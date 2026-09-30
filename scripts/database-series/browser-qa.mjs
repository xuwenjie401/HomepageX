/** Real desktop/mobile browser checks. Screenshots and reports must stay external.
 * DATABASE_QA_PLAYWRIGHT may point to an installed Playwright module URL.
 * node scripts/database-series/browser-qa.mjs http://127.0.0.1:4322 /tmp/database-qa
 */
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import path from 'node:path';
const {chromium}=await import(process.env.DATABASE_QA_PLAYWRIGHT || 'playwright');
const [base,out]=process.argv.slice(2);
if(!base || !out || !path.isAbsolute(out)) throw new Error('Supply origin and absolute external QA directory');
await mkdir(out,{recursive:true});
const slugs=['01-foundations','02-relational','03-indexes','04-spatial','05-graph','06-temporal','07-vector','08-multi-model','09-system-design'];
const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
const rows=[];
for(const width of [1440,390]){
 const page=await browser.newPage({viewport:{width,height:960},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(const slug of slugs){
  await page.goto(`${base}/HomepageX/blog/modern-databases/${slug}/`,{waitUntil:'networkidle'});
  await page.evaluate(async()=>{await document.fonts.ready;await Promise.all([...document.querySelectorAll('.prose img')].map(async im=>{im.loading='eager';await im.decode();}));});
  const metrics=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,figures:document.querySelectorAll('.prose figure').length,math:document.querySelectorAll('.prose [role=math]').length,imagesOk:[...document.querySelectorAll('.prose img')].every(im=>im.naturalWidth>0),toc:!!document.querySelector('.article-toc'),open:document.querySelector('.article-toc')?.open,headings:document.querySelectorAll('.prose h2,.prose h3').length}));
  if(metrics.width!==width || metrics.scrollWidth>width || !metrics.imagesOk || !metrics.toc) throw new Error(JSON.stringify({slug,width,metrics}));
  const toc=page.locator('.article-toc');
  if(width===390){
   if(metrics.open)throw new Error('Mobile TOC must initially be collapsed');
   await toc.locator('summary').click();
   await toc.locator('a').nth(4).click();
   await page.waitForTimeout(220);
   if(await toc.evaluate(x=>x.open))throw new Error('Mobile TOC did not collapse after navigation');
  }else{
   await toc.locator('a').nth(6).click();
   await page.waitForTimeout(220);
   const active=await toc.locator('[aria-current="location"]').count();
   if(active!==1)throw new Error('No unique active TOC heading');
  }
  const anchored=await page.evaluate(()=>!!document.getElementById(decodeURIComponent(location.hash.slice(1))));
  if(!anchored)throw new Error('TOC target absent');
  await page.evaluate(()=>scrollTo(0,0));
  await page.waitForTimeout(120);
  await page.screenshot({path:path.join(out,`${slug}-${width}.png`)});
  if(['03-indexes','06-temporal','07-vector','09-system-design'].includes(slug)){
   await page.locator('.prose figure').nth(2).scrollIntoViewIfNeeded();
   await page.waitForTimeout(200);
   await page.waitForFunction(()=>{
    const hs=[...document.querySelectorAll('.prose h2,.prose h3,.prose h4')];
    const expected=hs.filter(h=>h.getBoundingClientRect().top<=120).at(-1)||hs[0];
    const active=document.querySelector('.article-toc a[aria-current="location"]');
    return active && decodeURIComponent(active.hash.slice(1))===expected.id;
   });
   await page.screenshot({path:path.join(out,`${slug}-figure-${width}.png`)});
  }
  rows.push({slug,...metrics,tocNavigation:true});
 }
 if(errors.length)throw new Error(errors.join('\n'));
 await page.goto(`${base}/HomepageX/blog/modern-databases/`,{waitUntil:'networkidle'});
 const index=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,links:[...document.querySelectorAll('a')].map(x=>x.getAttribute('href'))}));
 if(index.scrollWidth>width || !slugs.every(s=>index.links.some(h=>h?.includes(s))))throw new Error('Series index missing article or overflowing');
 await page.screenshot({path:path.join(out,`series-${width}.png`)});
 await page.close();
}
// Inspect text bounds inside every SVG. This also catches cropped labels that XML checks miss.
const meta=JSON.parse(await readFile(new URL('./illustrations.json',import.meta.url),'utf8'));
const svgPage=await browser.newPage({viewport:{width:1000,height:500}});const svgIssues=[];
for(const key of Object.keys(meta)){
 await svgPage.goto(`${base}/HomepageX/media/modern-databases/${key}.svg`);
 await svgPage.evaluate(()=>document.fonts.ready);
 const issue=await svgPage.evaluate(()=>[...document.querySelectorAll('text')].flatMap(el=>{
  const r=el.getBoundingClientRect();return r.left < -1 || r.right > 1001 || r.top < -1 || r.bottom > 501 ? [{text:el.textContent,rect:{x:r.x,y:r.y,width:r.width,height:r.height}}] : [];
 }));
 if(issue.length)svgIssues.push({key,issue});
}
await browser.close();
await writeFile(path.join(out,'browser-report.json'),JSON.stringify({pages:rows,svgIssues},null,2));
console.log(JSON.stringify({article_viewports:rows.length,widths:[1440,390],svg_checked:Object.keys(meta).length,svgIssues},null,2));
if(svgIssues.length)process.exitCode=1;
