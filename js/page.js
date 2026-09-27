(()=>{
'use strict';
const $=s=>document.querySelector(s);
const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
// HUD
const hudYear=$('#hudYear'),hudEra=$('#hudEra');
let shownYear=2026,yearAnim=0;
function setHud(step){
  hudEra.textContent=step.dataset.era;
  const target=+step.dataset.year,text=step.dataset.yeartext||String(target);
  cancelAnimationFrame(yearAnim);
  if(reduce||Math.abs(target-shownYear)<1){hudYear.textContent=text;shownYear=target;return}
  const from=shownYear,t0=performance.now(),dur=Math.min(1400,300+Math.abs(target-from)*12);
  const tick=now=>{const k=Math.min(1,(now-t0)/dur),e=1-Math.pow(1-k,3);const v=Math.round(from+(target-from)*e);hudYear.textContent=k<1?v:text;if(k<1)yearAnim=requestAnimationFrame(tick);else shownYear=target};
  yearAnim=requestAnimationFrame(tick);
}

// steps + dots
const steps=[...document.querySelectorAll('.step')];
const dots=$('#dots');
steps.forEach((s,i)=>{const b=document.createElement('button');b.type='button';b.setAttribute('aria-label',s.dataset.title);b.innerHTML=`<span>${s.dataset.title}</span>`;b.onclick=()=>s.scrollIntoView({behavior:reduce?'auto':'smooth',block:'center'});dots.appendChild(b)});
const dotBtns=[...dots.children];
function activate(step){
  steps.forEach(s=>s.classList.toggle('is-active',s===step));
  dotBtns.forEach((b,i)=>b.classList.toggle('on',steps[i]===step));
  window.__scene=step.dataset.scene;window.dispatchEvent(new CustomEvent('kb-scene',{detail:step.dataset.scene}));setHud(step);
}
const io=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting)activate(e.target)})},{rootMargin:'-50% 0px -50% 0px',threshold:0});
steps.forEach(s=>io.observe(s));
activate(steps[0]);

// progress bar
const prog=$('#prog');
addEventListener('scroll',()=>{const h=document.documentElement;prog.style.width=(100*h.scrollTop/(h.scrollHeight-h.clientHeight))+'%'},{passive:true});

// ---------- map ----------
const RIVER=[[121.4836186,25.0331558],[121.488403,25.0251971],[121.4890006,25.0191122],[121.488651,25.0175936],[121.488748,25.0160775],[121.4893579,25.0140543],[121.4916288,25.011029],[121.4940415,25.0097678],[121.4957471,25.0096602],[121.4974625,25.0103001],[121.4997913,25.0117512],[121.5083368,25.0210144],[121.5107134,25.021774],[121.5144172,25.0215331],[121.5199348,25.0192485],[121.5217883,25.0158432],[121.5253876,25.0120714],[121.5307963,25.0089055],[121.5320259,25.0075238],[121.5326706,25.0056724],[121.533628,25.0041124],[121.5334391,25.0031074],[121.5314904,25.0015313],[121.530883,24.9994749],[121.5308296,24.99737]].reverse(); // downstream order = flow direction
const LON0=121.486,LON1=121.540,LAT0=24.998,LAT1=25.032,MW=1000,MH=694;
const P=(lon,lat)=>[(lon-LON0)/(LON1-LON0)*MW,(LAT1-lat)/(LAT1-LAT0)*MH];
const pxPerKm=MW/((LON1-LON0)*111.32*Math.cos(25.016*Math.PI/180));
function smooth(pts){ // Catmull-Rom → cubic Bézier
  let d=`M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for(let i=0;i<pts.length-1;i++){const p0=pts[i-1]||pts[i],p1=pts[i],p2=pts[i+1],p3=pts[i+2]||p2;
    const c1=[p1[0]+(p2[0]-p0[0])/6,p1[1]+(p2[1]-p0[1])/6],c2=[p2[0]-(p3[0]-p1[0])/6,p2[1]-(p3[1]-p1[1])/6];
    d+=` C${c1[0].toFixed(1)},${c1[1].toFixed(1)} ${c2[0].toFixed(1)},${c2[1].toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`}
  return d;
}
const rpx=RIVER.map(([lo,la])=>P(lo,la));
const riverD=smooth(rpx);
function nearestDir(x,y){let best=1e9,dir=[1,0];for(let i=0;i<rpx.length-1;i++){const a=rpx[i],b=rpx[i+1];const mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2;const d=(mx-x)**2+(my-y)**2;if(d<best){best=d;const L=Math.hypot(b[0]-a[0],b[1]-a[1]);dir=[(b[0]-a[0])/L,(b[1]-a[1])/L]}}return dir}
function bridgeAcross(lon,lat,lenM){const [x,y]=P(lon,lat),[dx,dy]=nearestDir(x,y),h=lenM/1000*pxPerKm/2;return [[x-dy*h,y+dx*h],[x+dy*h,y-dx*h]]}
const PLACES=[
  {id:'kb',name:'川端橋',meta:'1937・歷史建築・2026人行自行車橋',era:'both',line:[P(121.5164,25.0221),P(121.5159,25.0192)],col:'#e8b04b',w:5,
   text:'1937年3月25日開通，長300.56公尺、寬5.2公尺，13座雙柱式拱型橋墩承托14孔鋼鈑梁。1945年改名中正橋，2015年公告為歷史建築，2026年9月21日修復為人行與自行車橋重新啟用。'},
  {id:'zz',name:'新中正橋',meta:'2019–2024・三點式鋼拱橋',era:'now',line:[P(121.51595,25.0229),P(121.51525,25.0184)],col:'#e9f0f4',w:6,
   text:'建於川端橋下游側，拱跨215公尺、拱高50公尺，國內最大跨度三點式鋼拱橋。2023年10月8日第一階段通車，2024年3月16日雙向通車，2024年11月17日水源快速道路匝道開通後完工。'},
  {id:'yf',name:'永福橋',meta:'上游',era:'now',br:[121.5275,25.0110,420],col:'#7f93a8',w:4,text:'川端橋上游方向的下一座跨河橋，連接臺北公館與永和福和路一帶。'},
  {id:'fh',name:'福和橋',meta:'上游',era:'now',br:[121.5305,25.0077,420],col:'#7f93a8',w:4,text:'位於新店溪大彎東段，連接臺北與永和福和路。'},
  {id:'hz',name:'華中橋',meta:'下游',era:'now',br:[121.4958,25.0103,560],col:'#7f93a8',w:4,text:'川端橋下游方向的跨河橋，連接臺北萬華與中和。新店溪在此附近轉向北流，匯入淡水河。'},
  {id:'kishu',name:'紀州庵',meta:'1917 開設支店・今紀州庵文學森林',era:'both',pt:[121.52062,25.02153],col:'#e8b04b',
   text:'日本料亭紀州庵1917年在川端町開設支店，平松家擁有三、四艘屋形船、每艘可乘三十人。今為「紀州庵文學森林」，與川端橋、楊三郎美術館串成日治藝文廊道。'},
  {id:'yang',name:'網溪別墅／楊三郎美術館',meta:'1919・市定古蹟',era:'both',pt:[121.51691,25.01605],col:'#e8b04b',
   text:'楊仲佐1919年所建宅第，植菊千餘株，曾單日湧入五千人賞菊；楊仲佐也在1932年率領中和庄民請願建橋。今為楊三郎美術館，位於永和博愛街，就在川端橋永和端附近。'},
  {id:'ying',name:'螢橋',meta:'地名',era:'both',pt:[121.51452,25.02536],col:'#b6ff5a',text:'螢橋一帶因昔日夏夜螢火而得名，今有螢橋國小、螢橋國中等沿用此名，位於川端橋臺北端西北側。'},
  {id:'water',name:'臺北水道水源地',meta:'日治時期・今自來水園區',era:'both',pt:[121.53036,25.01338],col:'#8fb3cf',text:'日治時期臺北水道的取水與唧筒設施所在地，位於新店溪大彎東岸、川端橋上游方向；今為自來水園區。'},
  {id:'guting',name:'捷運古亭站',meta:'今日',era:'now',pt:[121.52273,25.02669],col:'#8fb3cf',text:'川端橋臺北端東北方的捷運站，舊地名「古亭」。戰後川端町一帶併入古亭區，今屬中正區。'},
  {id:'tpc',name:'捷運台電大樓站',meta:'今日',era:'now',pt:[121.52849,25.02042],col:'#8fb3cf',text:'位於師大路、汀州路一帶，步行可達紀州庵與新店溪河濱。'},
  {id:'gg',name:'捷運公館站',meta:'今日',era:'now',pt:[121.53426,25.01484],col:'#8fb3cf',text:'新店溪大彎東側的公館商圈，永福橋、福和橋由此跨向永和。'},
];
function renderMap(){
  const m=$('#mapSvg');let s='';
  s+=`<defs><pattern id="mgrid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40,0 H0 V40" fill="none" stroke="rgba(255,255,255,.035)"/></pattern></defs>`;
  s+=`<rect width="${MW}" height="${MH}" fill="#0c1426"/><rect width="${MW}" height="${MH}" fill="url(#mgrid)"/>`;
  // district labels
  const lab=(lon,lat,t,sz=15,op=.5,cls='')=>{const [x,y]=P(lon,lat);return `<text class="${cls}" x="${x.toFixed(0)}" y="${y.toFixed(0)}" text-anchor="middle" font-size="${sz}" fill="#fff" opacity="${op}" font-family="Noto Serif TC,serif" font-weight="700" letter-spacing="3">${t}</text>`};
  s+=`<g class="eranow">${lab(121.5130,25.0290,'臺北市 中正區')}${lab(121.4990,25.0285,'萬華區',14,.4)}${lab(121.5130,25.0110,'新北市 永和區',17,.55)}${lab(121.4990,25.0025,'中和區',14,.4)}${lab(121.5380,25.0020,'文山區',13,.35)}${lab(121.5360,25.0200,'大安區',13,.35)}</g>`;
  s+=`<g class="era1930">${lab(121.5150,25.0295,'臺北市（川端町・古亭町一帶）',14,.5)}${lab(121.5130,25.0110,'中和庄 溪洲',17,.55)}${lab(121.4990,25.0285,'艋舺',14,.4)}</g>`;
  // 川端町 (approximate)
  const kz=[[121.5118,25.0222],[121.5128,25.0262],[121.5215,25.0258],[121.5238,25.0205],[121.5196,25.0197],[121.5150,25.0217]].map(([a,b])=>P(a,b));
  s+=`<g class="era1930"><path d="M${kz.map(p=>p.map(v=>v.toFixed(1)).join(',')).join(' L')} Z" fill="#e8b04b" fill-opacity=".12" stroke="#e8b04b" stroke-dasharray="4 4" stroke-opacity=".6"/>${lab(121.5178,25.0243,'川端町（範圍示意）',13,.9)}</g>`;
  // river
  s+=`<path d="${riverD}" fill="none" stroke="#1d3a33" stroke-width="${(0.62*pxPerKm).toFixed(0)}" stroke-linecap="round" stroke-linejoin="round"/>`;
  s+=`<path d="${riverD}" fill="none" stroke="#24587a" stroke-width="${(0.30*pxPerKm).toFixed(0)}" stroke-linecap="round" stroke-linejoin="round"/>`;
  s+=`<path id="riverFlow" d="${riverD}" fill="none" stroke="#9fd0ee" stroke-opacity=".55" stroke-width="2" stroke-dasharray="4 40" stroke-linecap="round"/>`;
  {const [x,y]=P(121.5040,25.0170);s+=`<text x="${x}" y="${y}" transform="rotate(47 ${x} ${y})" text-anchor="middle" font-size="15" fill="#9fd0ee" font-family="Noto Serif TC,serif" letter-spacing="6">新店溪 ⟶</text>`}
  {const [x,y]=P(121.4868,25.0300);s+=`<text x="${x+18}" y="${y-8}" font-size="12" fill="#9fd0ee" opacity=".8" font-family="Noto Sans TC,sans-serif">往淡水河</text>`}
  {const [x,y]=P(121.5300,25.0000);s+=`<text x="${x-10}" y="${y+22}" font-size="12" fill="#9fd0ee" opacity=".8" font-family="Noto Sans TC,sans-serif" text-anchor="end">自新店方向流來</text>`}
  // ferry (1930s)
  {const a=P(121.5128,25.0184),b=P(121.5133,25.0226);s+=`<g class="era1930"><path id="ferryLine" d="M${a[0]},${a[1]} Q${a[0]-26},${(a[1]+b[1])/2} ${b[0]},${b[1]}" fill="none" stroke="#ffd27a" stroke-width="2.2" stroke-dasharray="6 5"/><text x="${a[0]-34}" y="${(a[1]+b[1])/2+4}" text-anchor="end" font-size="13" fill="#ffd27a" font-family="Noto Sans TC,sans-serif">網溪渡（約略位置）</text></g>`}
  // art corridor (now)
  {const k=P(121.52062,25.02153),t1=P(121.5164,25.0221),t2=P(121.5159,25.0192),y=P(121.51691,25.01605);s+=`<g class="eranow"><path id="corridor" d="M${k[0]},${k[1]} L${t1[0]},${t1[1]} L${t2[0]},${t2[1]} L${y[0]},${y[1]}" fill="none" stroke="#f5d68f" stroke-width="2" stroke-dasharray="3 8" stroke-linecap="round"/></g>`}
  // bridges & pins
  PLACES.forEach((p,i)=>{
    const cls=p.era==='both'?'':(p.era==='now'?'eranow':'era1930');
    let line=p.line||(p.br?bridgeAcross(...p.br):null);
    const tab=`tabindex="0" role="button" aria-label="${p.name}"`;
    if(line){
      const [a,b]=line,mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2;
      const labelLeft=p.id==='zz';
      s+=`<g class="pin ${cls}" data-i="${i}" ${tab}><line x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}" stroke="#000" stroke-opacity=".5" stroke-width="${p.w+4}" stroke-linecap="round"/><line x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}" stroke="${p.col}" stroke-width="${p.w}" stroke-linecap="round"/><circle class="dot" cx="${mx.toFixed(1)}" cy="${my.toFixed(1)}" r="14" fill="transparent"/><text x="${(mx+(labelLeft?-16:16)).toFixed(0)}" y="${(my+(p.id==='kb'?-10:4)).toFixed(0)}" text-anchor="${labelLeft?'end':'start'}" font-size="${p.id==='kb'?16:13}" fill="${p.col}" font-weight="700" font-family="Noto Sans TC,sans-serif" style="paint-order:stroke;stroke:#0c1426;stroke-width:4px">${p.name}</text></g>`;
    }else{
      const [x,y]=P(...p.pt);
      s+=`<g class="pin ${cls}" data-i="${i}" ${tab}><circle class="halo" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="7" fill="none" stroke="${p.col}" stroke-opacity=".6"/><circle class="dot" cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="6" fill="${p.col}" stroke="#0c1426" stroke-width="2"/><text x="${(x+11).toFixed(0)}" y="${(y+4).toFixed(0)}" font-size="13" fill="#e9e4d8" font-family="Noto Sans TC,sans-serif" style="paint-order:stroke;stroke:#0c1426;stroke-width:4px">${p.name}</text></g>`;
    }
  });
  // compass & scale
  s+=`<g transform="translate(${MW-50},${MH-110})"><circle r="20" fill="rgba(0,0,0,.35)" stroke="rgba(255,255,255,.25)"/><path d="M0,-15 L6,4 L0,0 L-6,4 Z" fill="#e8b04b"/><text y="-24" text-anchor="middle" font-size="12" fill="#fff" font-family="Noto Sans TC,sans-serif">N</text></g>`;
  const sb=0.5*pxPerKm;s+=`<g transform="translate(${MW-30-sb},${MH-40})"><rect width="${sb.toFixed(1)}" height="5" fill="#e9e4d8"/><rect width="${(sb/2).toFixed(1)}" height="5" fill="#556"/><text y="-6" font-size="12" fill="#c5c9d3" font-family="Noto Sans TC,sans-serif">0</text><text x="${sb.toFixed(1)}" y="-6" text-anchor="end" font-size="12" fill="#c5c9d3" font-family="Noto Sans TC,sans-serif">500 m</text></g>`;
  s+=`<text x="12" y="${MH-12}" font-size="11" fill="#8f97a8" font-family="Noto Sans TC,sans-serif">河道中心線 © OpenStreetMap contributors（簡化）｜範圍與河寬為示意</text>`;
  m.innerHTML=s;
  const info=$('#mapInfo');
  const show=(g)=>{const p=PLACES[+g.dataset.i];m.querySelectorAll('.pin').forEach(x=>x.classList.toggle('sel',x===g));info.innerHTML=`<div class="meta">${p.meta}</div><h3>${p.name}</h3><p>${p.text}</p><div class="map-legend"><span><i style="background:#e8b04b"></i>日治遺構</span><span><i style="background:#e9f0f4"></i>新中正橋</span><span><i style="background:#f5d68f;height:2px"></i>日治藝文廊道</span><span><i style="background:#ffd27a;height:2px"></i>渡船路線</span></div>`};
  m.querySelectorAll('.pin').forEach(g=>{g.addEventListener('click',()=>show(g));g.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();show(g)}})});
  show(m.querySelector('.pin[data-i="0"]'));
  document.querySelectorAll('.seg').forEach(b=>b.addEventListener('click',()=>{m.dataset.era=b.dataset.era;document.querySelectorAll('.seg').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));const sel=m.querySelector('.pin.sel');if(sel&&getComputedStyle(sel).pointerEvents==='none')show(m.querySelector('.pin[data-i="0"]'))}));
}
renderMap();

// ---------- timeline ----------
const TL=[
 ['渡船時代',[
  ['日治初期','永和舊稱「溪洲」，屬中和庄；與臺北之間以渡船往來，最大渡口為網溪渡（約今光復街底）。「網溪泛月」為中和八景之一。'],
  ['1917','料亭紀州庵於川端町河畔開設支店，平松家經營屋形船。'],
  ['1919','楊仲佐興建網溪別墅，植菊千餘株，曾創單日五千人參觀紀錄。'],
  ['1922','臺北市町名改正，新店溪畔設「川端町」。'],
  ['1923','〔傳說〕裕仁皇太子訪臺時赴網溪賞菊並下令建橋——當年報載行程未見此行。'],
  ['1932','中和庄民組請願團，楊仲佐率代表向海山郡守陳情建橋。',1]]],
 ['川端橋',[
  ['1935.03','臺北州土木課設計，辦理現場說明與競標；同年三菱重工業神戶造船所製造鋼鈑梁。'],
  ['1935.06.01','川端橋動工。',1],
  ['1937.02','竣工，工費252,000日圓；長300.56公尺、寬5.2公尺、雙線車道；13座鋼筋混凝土拱形鏤空橋墩、14孔上承式鋼鈑梁。'],
  ['1937.03.25','上午舉行開通典禮。與臺北橋、明治橋、昭和橋並列臺北四大名橋。',1]]],
 ['中正橋',[
  ['1945.11','改名「中正橋」。',1],
  ['1953','修築堤防，網溪一帶河岸景觀改變。'],
  ['1954','第一次拓寬，增加人行空間。'],
  ['1958','永和自中和鄉分出設鎮。'],
  ['1961.08.01','第二次拓寬，橋面達15.4公尺。'],
  ['1962.11–1963.05','橋身向南（永和端）延伸約100公尺。'],
  ['1968.04.15','整修伸縮縫。'],
  ['1972','第三次拓寬完成，寬24.5公尺、六車道；全長約500公尺、16墩17孔。',1],
  ['1973.07','開始收取過橋費，後因收費員偽造繳費證弊案提前停收。'],
  ['20世紀末','出現長230公分剪力裂縫，列臺北市十大危橋之首；防洪高程與耐震不足。']]],
 ['保存與改建',[
  ['2015.03','臺北市政府決定保留原橋而非拆除。'],
  ['2015.09.01','公告日治時期P1–P13號橋墩及其上鋼鈑梁為歷史建築。',1],
  ['2019.05.06','中正橋改建工程開工，雙北合計約33億元。'],
  ['2023.06.18','新橋中段拱肋（約1,800噸）頂升約29公尺合攏；鋼拱肋提升工法國內首見。'],
  ['2023.10.08','第一階段通車（臺北往新北）；11月18日開放全部車道。'],
  ['2024.03.16','第二階段通車，新橋雙向通行。',1],
  ['2024.07.20','機車專用道開放。'],
  ['2024.11.17','水源快速道路匝道開通，中正橋改建完工。'],
  ['2024–2026','川端橋復舊：拆除後期拓寬構造、整體抬升、鋼梁補強與還原漆面、等比例復刻護欄、設置景觀光雕。']]],
 ['重生',[
  ['2026.09.21','傍晚舉行川端橋修復啟用典禮，蔣萬安、侯友宜兩位市長共同主持；成為串聯紀州庵文學森林與楊三郎美術館的人行、自行車橋。',1],
  ['2026.12（預計）','中正河濱公園高空景觀橋、景觀塔與川端落霞廣場觀景平台完工。']]]
];
{
  const tl=$('#tl');let h='';TL.forEach(([era,items])=>{h+=`<div class="tl-era">${era}</div>`;items.forEach(([t,p,k])=>{h+=`<div class="tl-item${k?' key':''}"><time>${t}</time><p>${p}</p></div>`})});tl.innerHTML=h;
  const tio=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('seen');tio.unobserve(e.target)}}),{rootMargin:'0px 0px -10% 0px'});
  tl.querySelectorAll('.tl-item').forEach(x=>tio.observe(x));
}
// counters
{
  const nio=new IntersectionObserver(es=>es.forEach(e=>{if(!e.isIntersecting)return;nio.unobserve(e.target);const el=e.target,to=+el.dataset.count,dec=+(el.dataset.dec||0),t0=performance.now(),dur=reduce?1:1600;
    const fmt=v=>v.toLocaleString('zh-TW',{minimumFractionDigits:dec,maximumFractionDigits:dec,useGrouping:to>=10000});
    const tick=n=>{const k=Math.min(1,(n-t0)/dur),e2=1-Math.pow(1-k,3);el.textContent=fmt(to*e2);if(k<1)requestAnimationFrame(tick)};requestAnimationFrame(tick)}),{threshold:.4});
  document.querySelectorAll('[data-count]').forEach(x=>nio.observe(x));
}
})();
