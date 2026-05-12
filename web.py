from aiohttp import web

import database

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Listo</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600&family=DM+Serif+Display&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#FAF8F5;--card:#fff;--accent:#7F77DD;--adim:rgba(127,119,221,.1);--text:#1C1917;--muted:#78716C;--faint:#A8A29E;--border:rgba(0,0,0,.09);--sh:0 1px 8px rgba(0,0,0,.06);--sh2:0 6px 24px rgba(0,0,0,.11);--r:12px;--rs:8px}
[data-dark]{--bg:#111;--card:#1C1917;--text:#F5F0E8;--muted:#A8A29E;--faint:#57534E;--border:rgba(255,255,255,.08);--sh:0 1px 8px rgba(0,0,0,.4);--sh2:0 6px 24px rgba(0,0,0,.6)}
html,body{height:100%;background:var(--bg);color:var(--text);font-family:'DM Sans',sans-serif;font-size:14px;transition:background .25s,color .25s}
.shell{display:flex;flex-direction:column;height:100vh}
.hdr{display:flex;align-items:center;justify-content:space-between;padding:10px 24px;border-bottom:1px solid var(--border);background:var(--bg);position:sticky;top:0;z-index:50;flex-shrink:0}
.hinfo{display:flex;align-items:center;gap:10px}
.av{width:36px;height:36px;border-radius:50%;background:var(--accent);color:#fff;font-weight:600;font-size:15px;display:flex;align-items:center;justify-content:center;flex-shrink:0;overflow:hidden}
.av img{width:100%;height:100%;object-fit:cover}
.hname{font-size:15px;font-weight:600;color:var(--text);line-height:1.2}
.hsub{font-size:11px;color:var(--muted)}
.hbtns{display:flex;gap:2px}
.ib{width:32px;height:32px;border:none;background:transparent;cursor:pointer;border-radius:var(--rs);font-size:16px;display:flex;align-items:center;justify-content:center;color:var(--muted);transition:background .15s}
.ib:hover{background:var(--adim)}
.nav{display:flex;padding:0 24px;border-bottom:1px solid var(--border);background:var(--bg);overflow-x:auto;scrollbar-width:none;flex-shrink:0}
.nav::-webkit-scrollbar{display:none}
.nt{padding:9px 16px;border:none;background:transparent;cursor:pointer;font-family:'DM Sans',sans-serif;font-size:13px;font-weight:500;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap;transition:color .15s,border-color .15s}
.nt.on{color:var(--accent);border-bottom-color:var(--accent)}
.body{display:flex;flex:1;overflow:hidden}
.main{flex:1;overflow-y:auto;padding:20px 24px}
.tab{display:none}
.tab.on{display:block}
/* Pills */
.pills{display:flex;gap:6px;overflow-x:auto;margin-bottom:16px;scrollbar-width:none}
.pills::-webkit-scrollbar{display:none}
.pl{padding:5px 13px;border-radius:100px;border:1.5px solid var(--border);background:var(--card);font-size:12px;font-weight:500;cursor:pointer;white-space:nowrap;color:var(--muted);transition:all .15s;font-family:'DM Sans',sans-serif}
.pl:hover{border-color:var(--accent);color:var(--accent)}
.pl.on{background:var(--accent);border-color:var(--accent);color:#fff}
/* Grid & Cards */
.grid{columns:2 260px;column-gap:14px}
.card{break-inside:avoid;background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:14px;margin-bottom:14px;cursor:pointer;transition:border-color .15s,box-shadow .15s}
.card:hover{border-color:var(--accent);box-shadow:var(--sh)}
.card.sel{border-color:var(--accent);border-width:1.5px}
.cc{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);margin-bottom:5px}
.ct{font-family:'DM Serif Display',serif;font-size:16px;line-height:1.3;color:var(--text);margin-bottom:6px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.cs{font-size:12px;line-height:1.55;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:9px}
.ctags{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:9px}
.tag{padding:2px 8px;border-radius:100px;background:var(--adim);color:var(--accent);font-size:11px;font-weight:500}
.cft{display:flex;align-items:center;justify-content:space-between}
.cdate{font-size:11px;color:var(--faint)}
.cbtns{display:flex;gap:2px}
.cb{width:26px;height:26px;border:none;background:transparent;cursor:pointer;border-radius:6px;font-size:13px;color:var(--faint);transition:background .12s,color .12s;display:flex;align-items:center;justify-content:center}
.cb:hover{background:var(--adim);color:var(--accent)}
.cb.del:hover{background:rgba(220,50,50,.1);color:#dc3232}
/* Drawer */
.drw{width:0;border-left:1px solid var(--border);background:var(--card);display:flex;flex-direction:column;flex-shrink:0;overflow:hidden;transition:width .3s cubic-bezier(.4,0,.2,1)}
.drw.open{width:320px}
.dh{padding:16px 18px;border-bottom:1px solid var(--border);flex-shrink:0;display:flex;align-items:flex-start;gap:10px}
.dh-t{flex:1;min-width:0}
.dcat{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);margin-bottom:4px}
.dtitle{font-family:'DM Serif Display',serif;font-size:18px;line-height:1.3;color:var(--text)}
.db{flex:1;overflow-y:auto;padding:16px 18px}
.ds{margin-bottom:18px}
.dsl{font-size:10px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);margin-bottom:9px;display:flex;align-items:center;gap:8px}
.dsl::after{content:'';flex:1;height:1px;background:var(--border)}
.dbul{font-size:13px;line-height:1.6;color:var(--text);padding-left:14px;position:relative;margin-bottom:5px}
.dbul::before{content:'▪';position:absolute;left:0;color:var(--accent);font-size:10px;top:3px}
.eg{margin-bottom:12px}
.egn{font-size:11px;font-weight:600;color:var(--muted);margin-bottom:5px}
.er{font-size:12px;color:var(--muted);padding:5px 0;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px}
.er:last-child{border:none}
.er::before{content:'•';color:var(--accent);flex-shrink:0}
.el{color:var(--accent);text-decoration:none;font-size:10px;padding:2px 6px;border-radius:4px;background:var(--adim);margin-left:auto;flex-shrink:0}
.df{padding:12px 18px;border-top:1px solid var(--border);flex-shrink:0;display:flex;gap:6px}
.dbtn{flex:1;padding:7px 6px;border-radius:var(--rs);border:1px solid var(--border);background:transparent;font-family:'DM Sans',sans-serif;font-size:11px;font-weight:500;cursor:pointer;color:var(--muted);transition:border-color .15s,color .15s}
.dbtn:hover{border-color:var(--accent);color:var(--accent)}
.dbtn.dd:hover{border-color:#dc3232;color:#dc3232}
/* Graph */
#tab-graph{padding:0!important;overflow:hidden}
#tab-graph.on{display:flex;flex-direction:column;height:100%}
.graph-wrap{flex:1;position:relative;overflow:hidden}
#graph-svg{width:100%;height:100%;cursor:grab}
#graph-svg:active{cursor:grabbing}
.graph-node-entry{cursor:pointer}
.graph-node-tag{cursor:pointer}
.graph-tooltip{position:absolute;background:var(--card);border:1px solid var(--border);border-radius:var(--rs);padding:8px 12px;font-size:12px;pointer-events:none;box-shadow:var(--sh2);max-width:200px;z-index:10;display:none}
.graph-legend{position:absolute;bottom:16px;left:16px;background:var(--card);border:1px solid var(--border);border-radius:var(--rs);padding:12px 14px;font-size:11px;color:var(--muted)}
.graph-legend-row{display:flex;align-items:center;gap:8px;margin-bottom:4px}
.graph-legend-row:last-child{margin:0}
.graph-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.graph-controls{position:absolute;top:16px;right:16px;display:flex;flex-direction:column;gap:4px}
.gc-btn{width:32px;height:32px;background:var(--card);border:1px solid var(--border);border-radius:var(--rs);font-size:18px;cursor:pointer;display:flex;align-items:center;justify-content:center;color:var(--muted)}
.gc-btn:hover{border-color:var(--accent);color:var(--accent)}
/* Search */
.sw{position:relative;max-width:560px}
.si{width:100%;padding:12px 16px 12px 42px;border:1.5px solid var(--border);border-radius:var(--r);font-family:'DM Sans',sans-serif;font-size:14px;background:var(--card);color:var(--text);outline:none;margin-bottom:20px;transition:border-color .2s}
.si:focus{border-color:var(--accent)}
.sic{position:absolute;left:13px;top:16px;font-size:17px;pointer-events:none}
/* CmdK */
.cmdk{position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:200;display:none;align-items:flex-start;justify-content:center;padding-top:15vh}
.cmdk.open{display:flex}
.cmdk-box{width:min(560px,90vw);background:var(--card);border-radius:var(--r);overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,.3)}
.cmdk-in{width:100%;padding:16px 20px;border:none;border-bottom:1px solid var(--border);font-family:'DM Sans',sans-serif;font-size:16px;background:transparent;color:var(--text);outline:none}
.cmdk-res{max-height:380px;overflow-y:auto}
.cmdk-item{padding:12px 20px;cursor:pointer;border-bottom:1px solid var(--border);transition:background .12s}
.cmdk-item:last-child{border:none}
.cmdk-item:hover{background:var(--adim)}
.cmdk-t{font-size:14px;font-weight:500;color:var(--text);margin-bottom:2px}
.cmdk-m{font-size:12px;color:var(--muted)}
/* Stats */
.sgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin-bottom:18px}
.sc{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:18px}
.sl{font-size:11px;color:var(--muted);font-weight:500;margin-bottom:6px}
.sv{font-family:'DM Serif Display',serif;font-size:36px;color:var(--text);line-height:1}
.sec{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:18px;margin-bottom:14px}
.sec-t{font-size:11px;font-weight:600;color:var(--muted);letter-spacing:.05em;text-transform:uppercase;margin-bottom:14px}
.br{display:flex;align-items:center;gap:10px;margin-bottom:9px}
.bl{font-size:13px;color:var(--text);width:120px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bt{flex:1;height:5px;background:var(--border);border-radius:100px;overflow:hidden}
.bf{height:100%;background:var(--accent);border-radius:100px;transition:width 1s cubic-bezier(.4,0,.2,1)}
.bc{font-size:11px;color:var(--faint);width:20px;text-align:right;flex-shrink:0}
/* Resurface */
.rh{text-align:center;padding:32px 0 24px}
.rh h2{font-family:'DM Serif Display',serif;font-size:26px;color:var(--text);margin-bottom:8px}
.rh p{font-size:13px;color:var(--muted)}
.rb{display:block;margin:24px auto 0;padding:11px 30px;background:var(--accent);color:#fff;border:none;border-radius:100px;font-family:'DM Sans',sans-serif;font-size:13px;font-weight:500;cursor:pointer;transition:opacity .2s}
.rb:hover{opacity:.85}
/* Digests */
.digest-timeline{position:relative;padding-left:24px}
.digest-timeline::before{content:'';position:absolute;left:6px;top:0;bottom:0;width:1.5px;background:var(--border)}
.digest-card{position:relative;background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:18px 20px;margin-bottom:20px;border-left:3px solid var(--accent)}
.digest-card.quarterly{border-left-color:#F4845F}
.digest-card::before{content:'';position:absolute;left:-21px;top:20px;width:10px;height:10px;border-radius:50%;background:var(--accent);border:2px solid var(--bg)}
.digest-card.quarterly::before{background:#F4845F}
.digest-type{font-size:10px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--accent);margin-bottom:4px}
.digest-card.quarterly .digest-type{color:#F4845F}
.digest-period{font-family:'DM Serif Display',serif;font-size:17px;color:var(--text);margin-bottom:10px}
.digest-body{font-size:13px;line-height:1.7;color:var(--muted);white-space:pre-wrap}
/* Token */
.tscr{min-height:100vh;display:flex;align-items:center;justify-content:center;background:var(--bg);padding:24px}
.tcrd{background:var(--card);border:1px solid var(--border);border-radius:20px;padding:44px 36px;max-width:360px;width:100%;text-align:center;box-shadow:var(--sh2)}
.tcrd .logo{font-size:48px;margin-bottom:10px}
.tcrd h1{font-family:'DM Serif Display',serif;font-size:36px;color:var(--text);margin-bottom:6px}
.tsub{font-size:13px;color:var(--muted);margin-bottom:26px;line-height:1.5}
.ti{width:100%;padding:11px 14px;border:1.5px solid var(--border);border-radius:var(--rs);font-family:'DM Sans',sans-serif;font-size:14px;background:var(--bg);color:var(--text);outline:none;margin-bottom:10px;transition:border-color .2s}
.ti:focus{border-color:var(--accent)}
.tb{width:100%;padding:12px;background:var(--accent);color:#fff;border:none;border-radius:var(--rs);font-family:'DM Sans',sans-serif;font-size:14px;font-weight:500;cursor:pointer;transition:opacity .2s}
.tb:hover{opacity:.9}
.th{margin-top:14px;font-size:11px;color:var(--faint)}
/* Utils */
.empty{text-align:center;padding:56px 24px;color:var(--muted)}
.ei{font-size:40px;margin-bottom:12px}
.empty h3{font-family:'DM Serif Display',serif;font-size:20px;color:var(--text);margin-bottom:6px}
.empty p{font-size:13px;max-width:280px;margin:0 auto;line-height:1.5}
.spin{width:28px;height:28px;border:2.5px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite;margin:40px auto}
@keyframes spin{to{transform:rotate(360deg)}}
.end{text-align:center;padding:24px;font-size:12px;color:var(--faint)}
.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%) translateY(60px);background:var(--text);color:var(--bg);padding:9px 20px;border-radius:100px;font-size:12px;font-weight:500;z-index:999;transition:transform .3s;white-space:nowrap;pointer-events:none}
.toast.show{transform:translateX(-50%) translateY(0)}
.hidden{display:none!important}
</style>
</head>
<body>

<div id="tscr" class="tscr hidden">
  <div class="tcrd">
    <div class="logo">🧠</div>
    <h1>Listo</h1>
    <p class="tsub">Your AI second brain.<br>Enter your token to see your saves.</p>
    <input id="ti" class="ti" placeholder="Paste your token..." type="text">
    <button class="tb" onclick="submitToken()">Open my brain →</button>
    <p class="th">Get your token by sending /mypage to @listo_brain_bot</p>
  </div>
</div>

<div id="app" class="shell hidden">
  <div class="hdr">
    <div class="hinfo">
      <div class="av" id="av">🧠</div>
      <div>
        <div class="hname" id="hname">Listo</div>
        <div class="hsub" id="hsub">your second brain</div>
      </div>
    </div>
    <div class="hbtns">
      <button class="ib" onclick="openCmdK()" title="Search ⌘K">🔍</button>
      <button class="ib" onclick="toggleDark()" id="dbtn">🌙</button>
      <button class="ib" onclick="signOut()" title="Sign out">🚪</button>
    </div>
  </div>

  <div class="nav">
    <button class="nt on" onclick="sw('browse',this)">Browse</button>
    <button class="nt" onclick="sw('search',this)">Search</button>
    <button class="nt" onclick="sw('graph',this)">Graph 🕸</button>
    <button class="nt" onclick="sw('resurface',this)">Resurface ✨</button>
    <button class="nt" onclick="sw('stats',this)">Stats</button>
    <button class="nt" onclick="sw('digests',this)">Digests</button>
  </div>

  <div class="body">
    <div class="main" id="main-scroll">
      <div id="tab-browse" class="tab on">
        <div class="pills" id="pills"></div>
        <div id="browse"></div>
      </div>
      <div id="tab-search" class="tab">
        <div class="sw"><span class="sic">🔍</span><input class="si" id="sinput" placeholder="Search your saves..." oninput="debounce(this.value)"></div>
        <div id="sr"></div>
      </div>
      <div id="tab-graph" class="tab">
        <div class="graph-wrap" id="graph-wrap">
          <svg id="graph-svg"></svg>
          <div class="graph-tooltip" id="gtt"></div>
          <div class="graph-legend" id="glegend"></div>
          <div class="graph-controls">
            <button class="gc-btn" onclick="graphZoom(1.3)" title="Zoom in">+</button>
            <button class="gc-btn" onclick="graphZoom(0.77)" title="Zoom out">−</button>
            <button class="gc-btn" onclick="graphReset()" title="Reset">⟳</button>
          </div>
        </div>
      </div>
      <div id="tab-resurface" class="tab">
        <div class="rh"><h2>From your past saves 🕰️</h2><p>Things saved more than 30 days ago — rediscover them</p></div>
        <div id="resurface"></div>
        <button class="rb" onclick="loadResurface()">Resurface again ✨</button>
      </div>
      <div id="tab-stats" class="tab"><div id="stats"></div></div>
      <div id="tab-digests" class="tab"><div id="digests"></div></div>
    </div>

    <div class="drw" id="drw">
      <div class="dh">
        <div class="dh-t">
          <div class="dcat" id="dcat"></div>
          <div class="dtitle" id="dtitle"></div>
        </div>
        <button class="ib" onclick="closeDrw()" style="flex-shrink:0">✕</button>
      </div>
      <div class="db" id="db"></div>
      <div class="df">
        <button class="dbtn" id="dtg" onclick="openTg()">↗ Telegram</button>
        <button class="dbtn" onclick="shareE()">🔗 Share</button>
        <button class="dbtn dd" onclick="delFromDrw()">🗑 Delete</button>
      </div>
    </div>
  </div>
</div>

<!-- CmdK -->
<div class="cmdk" id="cmdk" onclick="closeCmdK()">
  <div class="cmdk-box" onclick="event.stopPropagation()">
    <input class="cmdk-in" id="cmdk-in" placeholder="Search your saves..." oninput="cmdkSearch(this.value)">
    <div class="cmdk-res" id="cmdk-res"></div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<script>
const API='https://listo-production.up.railway.app';
const EM={Travel:'🌍',Books:'📚',AI:'🤖',Fashion:'🧥',Beauty:'💄',Movies:'🎬',Knitting:'🧶',Food:'🍽️',Tech:'💻',LifeHack:'💡',Psychology:'🧠',Health:'💪',Finance:'💰',Design:'🎨',Language:'💬',Nature:'🌿',Music:'🎵',Photography:'📷',Parenting:'👶',Other:'📌'};
const FC={Travel:'#5BB8A0',Books:'#7F77DD',AI:'#4A90D9',Fashion:'#F5A623',Beauty:'#E87C6A',Movies:'#9B59B6',Knitting:'#E91E8C',Food:'#E67E22',Tech:'#2ECC71',LifeHack:'#F1C40F',Psychology:'#8E44AD',Health:'#27AE60',Finance:'#2980B9',Design:'#E74C3C',Language:'#1ABC9C',Nature:'#7DBE31',Music:'#FF5722',Photography:'#607D8B',Parenting:'#FF9800',Other:'#9B9B9B'};

let token='',act=null,folder='All',offset=0,more=true,busy=false,timer=null,ckTimer=null;
let dark=localStorage.getItem('ld')==='1';
let allEntries=[];
let gSim=null,gZoom=null,gTransform=d3.zoomIdentity;

window.onload=()=>{
  if(dark){document.body.setAttribute('data-dark','');document.getElementById('dbtn').textContent='☀️'}
  const p=new URLSearchParams(location.search);
  token=p.get('token')||localStorage.getItem('lt')||'';
  if(!token){show('tscr');return}
  localStorage.setItem('lt',token);
  if(p.get('token'))history.replaceState({},'',location.pathname);
  show('app');init();
};

function submitToken(){token=document.getElementById('ti').value.trim();if(!token)return;localStorage.setItem('lt',token);hide('tscr');show('app');init()}
function signOut(){localStorage.removeItem('lt');token='';location.reload()}
function show(id){document.getElementById(id).classList.remove('hidden')}
function hide(id){document.getElementById(id).classList.add('hidden')}
function toggleDark(){dark=!dark;localStorage.setItem('ld',dark?'1':'');document.body.toggleAttribute('data-dark',dark);document.getElementById('dbtn').textContent=dark?'☀️':'🌙';if(gSim)buildGraph(allEntries)}

async function init(){
  loadMe();buildPills();loadBrowse();
  document.addEventListener('keydown',e=>{
    if((e.metaKey||e.ctrlKey)&&e.key==='k'){e.preventDefault();openCmdK()}
    if(e.key==='Escape'){closeCmdK();closeDrw()}
  });
  const ms=document.getElementById('main-scroll');
  ms.addEventListener('scroll',()=>{if(ms.scrollTop+ms.clientHeight>=ms.scrollHeight-400&&!busy&&more&&document.getElementById('tab-browse').classList.contains('on'))loadBrowse()});
}

async function loadMe(){
  try{
    const r=await fetch(`${API}/api/me?token=${token}`);if(!r.ok)return;
    const d=await r.json();const n=d.first_name||'You';
    document.getElementById('hname').textContent=`${n}'s Brain 🧠`;
    document.title=`${n}'s Listo`;
    const parts=[];
    if(d.username)parts.push(`@${d.username}`);
    if(d.total_saves!=null)parts.push(`${d.total_saves} saves`);
    if(d.first_save_date){const dt=new Date(d.first_save_date);parts.push(`since ${dt.toLocaleString('en',{month:'long',year:'numeric'})}`)}
    document.getElementById('hsub').textContent=parts.join(' · ')||'your second brain';
    const av=document.getElementById('av');
    if(d.avatar_url){av.innerHTML=`<img src="${d.avatar_url}" onerror="this.parentNode.textContent='${esc(n[0].toUpperCase())}'">` }else{av.textContent=n[0].toUpperCase()}
  }catch(e){}
}

async function buildPills(){
  try{
    const r=await fetch(`${API}/api/entries?token=${token}&limit=200`);if(!r.ok)return;
    const data=await r.json();
    allEntries=data;
    const folders=[...new Set(data.map(e=>e.folder).filter(Boolean))].sort();
    const row=document.getElementById('pills');row.innerHTML='';
    [['All',true],...folders.map(f=>[f,false])].forEach(([f,a])=>{
      const b=document.createElement('button');b.className='pl'+(a?' on':'');
      b.textContent=f==='All'?'All':`${EM[f]||'📌'} ${f}`;
      b.onclick=()=>{document.querySelectorAll('.pl').forEach(x=>x.classList.remove('on'));b.classList.add('on');folder=f;offset=0;more=true;document.getElementById('browse').innerHTML='';loadBrowse()};
      row.appendChild(b);
    });
  }catch(e){}
}

async function loadBrowse(){
  if(busy||!more)return;busy=true;
  const el=document.getElementById('browse');
  if(offset===0)el.innerHTML='<div class="spin"></div>';
  try{
    let url=`${API}/api/entries?token=${token}&limit=20&offset=${offset}`;
    if(folder!=='All')url+=`&folder=${encodeURIComponent(folder)}`;
    const r=await fetch(url);if(r.status===403){show('tscr');hide('app');busy=false;return}
    const data=await r.json();
    if(offset===0){
      el.innerHTML='';
      if(!data.length){el.innerHTML=`<div class="empty"><div class="ei">🌱</div><h3>Nothing here yet</h3><p>Send a photo or video to @listo_brain_bot to get started!</p></div>`;busy=false;return}
      const g=document.createElement('div');g.className='grid';g.id='grid';el.appendChild(g);
    }
    const grid=document.getElementById('grid');
    data.forEach((e,i)=>grid.appendChild(mkCard(e,i)));
    offset+=data.length;
    if(data.length<20){more=false;const end=document.createElement('div');end.className='end';end.textContent="You've seen everything 🧠";el.appendChild(end)}
  }catch(e){if(offset===0)el.innerHTML='<div class="empty"><p>Could not load.</p></div>'}
  busy=false;
}

function mkCard(e,idx=0){
  const d=document.createElement('div');d.className='card';
  const emoji=EM[e.folder]||'📌';
  const tags=ptags(e.tags).slice(0,4).map(t=>`<span class="tag">${esc(t)}</span>`).join('');
  const sum=ssum(e.summary);
  d.innerHTML=`<div class="cc">${emoji} ${esc(e.folder||'Other')}</div>
    <div class="ct">${esc(e.title||'Untitled')}</div>
    ${sum?`<div class="cs">${esc(sum)}</div>`:''}
    ${tags?`<div class="ctags">${tags}</div>`:''}
    <div class="cft"><span class="cdate">${fmtDate(e.created_at)}</span>
    <div class="cbtns">
      <button class="cb" onclick="event.stopPropagation();cpShare(${e.id})" title="Share">🔗</button>
      <button class="cb del" onclick="event.stopPropagation();delCard(${e.id},this)" title="Delete">🗑</button>
    </div></div>`;
  d.onclick=()=>openDrw(e,d);return d;
}

function openDrw(e,card){
  document.querySelectorAll('.card').forEach(c=>c.classList.remove('sel'));
  if(card)card.classList.add('sel');
  act=e;
  document.getElementById('dcat').textContent=`${EM[e.folder]||'📌'} ${e.folder||'Other'}`;
  document.getElementById('dtitle').textContent=e.title||'Untitled';
  document.getElementById('dtg').style.display=e.tg_message_link?'':'none';
  const body=document.getElementById('db');body.innerHTML='';
  if(e.summary){
    const s=document.createElement('div');s.className='ds';
    s.innerHTML=`<div class="dsl">📋 Summary</div>`;
    e.summary.split(/\\.\\s+/).filter(x=>x.trim()).slice(0,5).forEach(t=>{s.innerHTML+=`<div class="dbul">${esc(t.trim().replace(/\\.$/,''))}.</div>`});
    body.appendChild(s);
  }
  const en=pEn(e.enrichment);
  if(en){
    const defs=[
      ['places','📍 Places',p=>p.name+(p.type?` — ${p.type}`:''),p=>`https://maps.google.com/?q=${enc(p.name)}`],
      ['books','📚 Books',b=>b.author?`${b.title} by ${b.author}`:b.title,b=>`https://www.goodreads.com/search?q=${enc(b.title)}`],
      ['movies_tv','🎬 Movies & TV',m=>m.title,m=>`https://www.imdb.com/find?q=${enc(m.title)}`],
      ['fashion','🧥 Fashion',f=>f.brand,f=>`https://www.google.com/search?q=${enc(f.brand)}`],
      ['beauty_skincare','💄 Beauty',b=>b.brand?`${b.product} by ${b.brand}`:b.product,b=>`https://www.google.com/search?q=${enc(b.product)}`],
      ['health_products','💊 Health',h=>h.price?`${h.name} — ${h.price}`:h.name,h=>`https://www.google.com/search?q=${enc(h.name)}`],
      ['knitting','🧶 Knitting',k=>k.creator?`${k.pattern} by ${k.creator}`:k.pattern,k=>`https://www.ravelry.com/search#query=${enc(k.pattern)}`],
      ['websites','🌐 Websites',w=>w.name,w=>w.url||`https://www.google.com/search?q=${enc(w.name)}`],
      ['ai_terms','🤖 AI Terms',a=>a.explanation?`${a.term} — ${a.explanation}`:a.term,a=>`https://www.google.com/search?q=${enc(a.term)}`],
      ['social_handles','👤 Handles',s=>s.handle,s=>`https://www.google.com/search?q=${enc(s.handle)}`],
      ['other','📦 Other',o=>o.entity,o=>`https://www.google.com/search?q=${enc(o.entity)}`],
    ];
    const has=defs.some(([k])=>(en[k]||[]).length);
    if(has){
      const s=document.createElement('div');s.className='ds';s.innerHTML=`<div class="dsl">🔍 Extracted</div>`;
      defs.forEach(([key,label,gT,gU])=>{
        const items=en[key];if(!items||!items.length)return;
        const g=document.createElement('div');g.className='eg';g.innerHTML=`<div class="egn">${label}</div>`;
        items.forEach(item=>{const txt=gT(item);if(!txt)return;g.innerHTML+=`<div class="er"><span>${esc(txt)}</span><a href="${gU(item)}" target="_blank" class="el">↗</a></div>`});
        s.appendChild(g);
      });
      body.appendChild(s);
    }
  }
  const tags=ptags(e.tags);
  if(tags.length){
    const s=document.createElement('div');s.className='ds';
    s.innerHTML=`<div class="dsl">🏷 Tags</div><div class="ctags">${tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>`;
    body.appendChild(s);
  }
  document.getElementById('drw').classList.add('open');
}

function closeDrw(){document.getElementById('drw').classList.remove('open');document.querySelectorAll('.card').forEach(c=>c.classList.remove('sel'));act=null}
function openTg(){if(act?.tg_message_link)window.open(act.tg_message_link,'_blank')}
async function shareE(){if(!act)return;await clip(`${API}/api/share/${act.id}`);toast('Link copied! 📋')}
async function cpShare(id){await clip(`${API}/api/share/${id}`);toast('Link copied! 📋')}
async function delCard(id,btn){
  if(!confirm('Delete this save?'))return;
  try{
    await fetch(`${API}/api/entries/${id}?token=${token}`,{method:'DELETE'});
    const c=btn?.closest?.('.card');
    if(c){c.style.opacity='0';c.style.transform='scale(.95)';c.style.transition='.2s';setTimeout(()=>c.remove(),200)}
    toast('Deleted ✓');
  }catch(e){toast('Could not delete')}
}
async function delFromDrw(){if(!act)return;if(!confirm('Delete this save?'))return;await delCard(act.id,null);closeDrw()}

// ── GRAPH ──
async function loadGraph(){
  const wrap=document.getElementById('graph-wrap');
  if(!allEntries.length){
    try{const r=await fetch(`${API}/api/entries?token=${token}&limit=200`);const d=await r.json();allEntries=d}catch(e){}
  }
  buildGraph(allEntries);
}

function buildGraph(entries){
  const svg=document.getElementById('graph-svg');
  svg.innerHTML='';
  if(!entries.length){svg.innerHTML='<text x="50%" y="50%" text-anchor="middle" fill="var(--muted)" font-size="14" font-family=\'DM Sans\'>No saves yet to build a graph</text>';return}

  const W=svg.clientWidth||800,H=svg.clientHeight||500;
  const S=d3.select(svg);

  const nodes=[];const links=[];const tagMap={};
  entries.forEach(e=>{
    nodes.push({id:`e_${e.id}`,type:'entry',entry:e,label:e.title||'Untitled',folder:e.folder||'Other'});
    ptags(e.tags).forEach(tag=>{
      if(!tagMap[tag]){tagMap[tag]={id:`t_${tag}`,type:'tag',label:tag};nodes.push(tagMap[tag])}
      links.push({source:`e_${e.id}`,target:`t_${tag}`});
    });
  });

  const gEl=S.append('g').attr('id','g-root');

  gZoom=d3.zoom().scaleExtent([.1,4]).on('zoom',ev=>{gTransform=ev.transform;gEl.attr('transform',ev.transform)});
  S.call(gZoom).call(gZoom.transform,gTransform);

  const link=gEl.append('g').selectAll('line').data(links).join('line')
    .attr('stroke',dark?'rgba(255,255,255,.12)':'rgba(0,0,0,.08)').attr('stroke-width',1);

  const node=gEl.append('g').selectAll('g').data(nodes).join('g')
    .attr('cursor','pointer')
    .call(d3.drag().on('start',dragStart).on('drag',dragged).on('end',dragEnd));

  node.each(function(d){
    const g=d3.select(this);
    if(d.type==='entry'){
      g.append('circle').attr('r',7).attr('fill',FC[d.folder]||'#9B9B9B').attr('stroke','var(--bg)').attr('stroke-width',2);
    }else{
      g.append('circle').attr('r',14).attr('fill','rgba(241,196,15,.15)').attr('stroke','#F1C40F').attr('stroke-width',1.5);
      g.append('text').text(d.label).attr('text-anchor','middle').attr('dy','0.35em').attr('font-size',9).attr('font-family','DM Sans').attr('fill',dark?'#F5F0E8':'#1C1917').attr('pointer-events','none');
    }
  });

  const tt=document.getElementById('gtt');
  node.on('mouseover',function(ev,d){
    if(d.type==='entry'){
      tt.style.display='block';
      tt.innerHTML=`<strong>${esc(d.label)}</strong><br><span style="font-size:11px;color:var(--muted)">${EM[d.folder]||'📌'} ${d.folder}</span>`;
      tt.style.left=(ev.offsetX+14)+'px';tt.style.top=(ev.offsetY-10)+'px';
    }
  }).on('mousemove',function(ev){
    tt.style.left=(ev.offsetX+14)+'px';tt.style.top=(ev.offsetY-10)+'px';
  }).on('mouseout',()=>{tt.style.display='none'})
  .on('click',function(ev,d){
    if(d.type==='entry'){openDrw(d.entry,null)}
    else{
      node.selectAll('circle').attr('opacity',.25);
      link.attr('opacity',.08);
      const connected=new Set(links.filter(l=>l.source.id===d.id||l.target.id===d.id).map(l=>l.source.id===d.id?l.target.id:l.source.id));
      connected.add(d.id);
      node.filter(n=>connected.has(n.id)).selectAll('circle').attr('opacity',1);
      link.filter(l=>l.source.id===d.id||l.target.id===d.id).attr('opacity',1);
      setTimeout(()=>{node.selectAll('circle').attr('opacity',1);link.attr('opacity',1)},2000);
    }
  });

  gSim=d3.forceSimulation(nodes)
    .force('link',d3.forceLink(links).id(d=>d.id).distance(80).strength(.5))
    .force('charge',d3.forceManyBody().strength(-200))
    .force('center',d3.forceCenter(W/2,H/2))
    .force('collision',d3.forceCollide(20))
    .on('tick',()=>{
      link.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
      node.attr('transform',d=>`translate(${d.x},${d.y})`);
    });

  const usedFolders=[...new Set(entries.map(e=>e.folder).filter(Boolean))];
  const leg=document.getElementById('glegend');
  leg.innerHTML=`<div style="font-size:10px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--faint);margin-bottom:8px">Legend</div>`;
  usedFolders.slice(0,8).forEach(f=>{
    leg.innerHTML+=`<div class="graph-legend-row"><div class="graph-dot" style="background:${FC[f]||'#9B9B9B'}"></div><span>${EM[f]||'📌'} ${f}</span></div>`;
  });
  leg.innerHTML+=`<div class="graph-legend-row"><div class="graph-dot" style="background:rgba(241,196,15,.4);border:1.5px solid #F1C40F"></div><span>Tag</span></div>`;
}

function dragStart(ev,d){if(!ev.active)gSim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y}
function dragged(ev,d){d.fx=ev.x;d.fy=ev.y}
function dragEnd(ev,d){if(!ev.active)gSim.alphaTarget(0);d.fx=null;d.fy=null}
function graphZoom(factor){const svg=d3.select('#graph-svg');svg.transition().duration(300).call(gZoom.scaleBy,factor)}
function graphReset(){const svg=d3.select('#graph-svg');svg.transition().duration(500).call(gZoom.transform,d3.zoomIdentity)}

// ── CMDK ──
function openCmdK(){document.getElementById('cmdk').classList.add('open');setTimeout(()=>document.getElementById('cmdk-in').focus(),60)}
function closeCmdK(){document.getElementById('cmdk').classList.remove('open');document.getElementById('cmdk-in').value='';document.getElementById('cmdk-res').innerHTML=''}
function cmdkSearch(q){clearTimeout(ckTimer);ckTimer=setTimeout(async()=>{
  const el=document.getElementById('cmdk-res');
  if(!q.trim()){el.innerHTML='';return}
  try{
    const r=await fetch(`${API}/api/entries?token=${token}&q=${encodeURIComponent(q)}&limit=15`);
    const data=await r.json();el.innerHTML='';
    data.forEach(e=>{
      const item=document.createElement('div');item.className='cmdk-item';
      item.innerHTML=`<div class="cmdk-t">${esc(e.title||'Untitled')}</div><div class="cmdk-m">${EM[e.folder]||'📌'} ${esc(e.folder||'Other')} · ${fmtDate(e.created_at)}</div>`;
      item.onclick=()=>{closeCmdK();openDrw(e,null)};
      el.appendChild(item);
    });
    if(!data.length)el.innerHTML='<div style="padding:20px;text-align:center;color:var(--muted);font-size:13px">No results</div>';
  }catch(e){}
},300)}

// ── SEARCH ──
function debounce(q){clearTimeout(timer);timer=setTimeout(()=>doSearch(q),380)}
async function doSearch(q){
  const el=document.getElementById('sr');
  if(!q.trim()){el.innerHTML='';return}
  el.innerHTML='<div class="spin"></div>';
  try{
    const r=await fetch(`${API}/api/entries?token=${token}&q=${encodeURIComponent(q)}&limit=20`);
    const data=await r.json();el.innerHTML='';
    if(!data.length){el.innerHTML=`<div class="empty"><div class="ei">🔍</div><h3>No results</h3></div>`;return}
    const g=document.createElement('div');g.className='grid';
    data.forEach((e,i)=>g.appendChild(mkCard(e,i)));el.appendChild(g);
  }catch(e){}
}

// ── RESURFACE ──
async function loadResurface(){
  const el=document.getElementById('resurface');el.innerHTML='<div class="spin"></div>';
  try{
    const r=await fetch(`${API}/api/resurface?token=${token}`);const data=await r.json();el.innerHTML='';
    if(!data.length){el.innerHTML=`<div class="empty"><p>No saves older than 30 days yet!</p></div>`;return}
    const g=document.createElement('div');g.className='grid';
    data.forEach((e,i)=>g.appendChild(mkCard(e,i)));el.appendChild(g);
  }catch(e){el.innerHTML='<div class="empty"><p>Could not load.</p></div>'}
}

// ── STATS ──
async function loadStats(){
  const el=document.getElementById('stats');el.innerHTML='<div class="spin"></div>';
  try{
    const r=await fetch(`${API}/api/stats?token=${token}`);const d=await r.json();el.innerHTML='';
    const grid=document.createElement('div');grid.className='sgrid';
    grid.innerHTML=`<div class="sc"><div class="sl">Total saves</div><div class="sv">${d.total||0}</div></div>
      <div class="sc"><div class="sl">This week</div><div class="sv">${d.this_week||0}</div></div>
      <div class="sc"><div class="sl">Top folder</div><div class="sv" style="font-size:20px;margin-top:4px">${EM[d.top_folder]||'📌'} ${esc(d.top_folder||'—')}</div></div>`;
    el.appendChild(grid);
    if(d.top_tags?.length){
      const s=document.createElement('div');s.className='sec';
      s.innerHTML=`<div class="sec-t">Top Tags</div>`;
      const max=d.top_tags[0]?.count||1;
      d.top_tags.forEach(t=>{s.innerHTML+=`<div class="br"><div class="bl">${esc(t.tag)}</div><div class="bt"><div class="bf" style="width:0" data-w="${Math.round(t.count/max*100)}%"></div></div><div class="bc">${t.count}</div></div>`});
      el.appendChild(s);
      setTimeout(()=>el.querySelectorAll('.bf').forEach(b=>{b.style.transition='width 1s';b.style.width=b.dataset.w}),50);
    }
  }catch(e){el.innerHTML='<div class="empty"><p>Could not load stats.</p></div>'}
}

// ── DIGESTS ──
async function loadDigests(){
  const el=document.getElementById('digests');el.innerHTML='<div class="spin"></div>';
  try{
    const r=await fetch(`${API}/api/digests?token=${token}`);
    if(!r.ok){el.innerHTML=`<div class="empty"><div class="ei">📬</div><h3>No digests yet</h3><p>Your first weekly digest arrives every Sunday morning. Keep saving!</p></div>`;return}
    const data=await r.json();el.innerHTML='';
    if(!data.length){el.innerHTML=`<div class="empty"><div class="ei">📬</div><h3>No digests yet</h3><p>Your first weekly digest arrives every Sunday morning. Keep saving!</p></div>`;return}
    const timeline=document.createElement('div');timeline.className='digest-timeline';
    data.forEach(d=>{
      const card=document.createElement('div');
      card.className=`digest-card${d.type==='quarterly'?' quarterly':''}`;
      const typeLabel=d.type==='quarterly'?'🔄 Quarterly Review':'📅 Weekly Digest';
      card.innerHTML=`<div class="digest-type">${typeLabel}</div>
        <div class="digest-period">${esc(d.period_label||d.created_at)}</div>
        <div class="digest-body">${esc(d.content||'')}</div>`;
      timeline.appendChild(card);
    });
    el.appendChild(timeline);
  }catch(e){el.innerHTML=`<div class="empty"><div class="ei">📬</div><h3>No digests yet</h3><p>Your first weekly digest arrives every Sunday morning.</p></div>`}
}

function sw(name,btn){
  document.querySelectorAll('.nt').forEach(t=>t.classList.remove('on'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('on'));
  btn.classList.add('on');document.getElementById(`tab-${name}`).classList.add('on');
  closeDrw();
  if(name==='stats')loadStats();
  if(name==='resurface')loadResurface();
  if(name==='digests')loadDigests();
  if(name==='graph')loadGraph();
}

function ptags(t){if(!t)return[];return t.split(/\\s+/).filter(x=>x.startsWith('#'))}
function pEn(e){if(!e)return null;if(typeof e==='object')return e;try{return JSON.parse(e)}catch{return null}}
function ssum(s){if(!s)return'';const p=s.split('. ');return p.length>1?p.slice(1).join('. ').slice(0,140):s.slice(0,140)}
function fmtDate(d){if(!d)return'';return new Date(d).toLocaleDateString('en',{month:'short',day:'numeric',year:'numeric'})}
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function enc(s){return encodeURIComponent(s||'')}
async function clip(txt){try{await navigator.clipboard.writeText(txt)}catch{const t=document.createElement('textarea');t.value=txt;document.body.appendChild(t);t.select();document.execCommand('copy');t.remove()}}
function toast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2500)}
</script>
</body>
</html>"""


async def handle_root(request: web.Request) -> web.Response:
    raise web.HTTPFound("/app")


async def handle_app(request: web.Request) -> web.Response:
    return web.Response(text=HTML_PAGE, content_type="text/html")


def _get_token(request: web.Request) -> str:
    return request.rel_url.query.get("token", "")


async def handle_entries(request: web.Request) -> web.Response:
    token = _get_token(request)
    user_id = database.get_user_by_token(token)
    if user_id is None:
        return web.json_response({"error": "forbidden"}, status=403)
    folder = request.rel_url.query.get("folder", None)
    query = request.rel_url.query.get("q", None)
    try:
        limit = int(request.rel_url.query.get("limit", 20))
        offset = int(request.rel_url.query.get("offset", 0))
    except ValueError:
        limit, offset = 20, 0
    entries = database.get_entries_web(user_id, folder=folder, query=query,
                                       limit=limit, offset=offset)
    return web.json_response(entries)


async def handle_stats(request: web.Request) -> web.Response:
    token = _get_token(request)
    user_id = database.get_user_by_token(token)
    if user_id is None:
        return web.json_response({"error": "forbidden"}, status=403)
    stats = database.get_web_stats(user_id)
    return web.json_response(stats)


async def handle_delete(request: web.Request) -> web.Response:
    token = _get_token(request)
    user_id = database.get_user_by_token(token)
    if user_id is None:
        return web.json_response({"error": "forbidden"}, status=403)
    try:
        entry_id = int(request.match_info["id"])
    except (KeyError, ValueError):
        return web.json_response({"error": "invalid id"}, status=400)
    deleted = database.delete_entry(entry_id, user_id)
    if not deleted:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response({"ok": True})


async def handle_me(request: web.Request) -> web.Response:
    token = _get_token(request)
    profile = database.get_user_profile(token)
    if profile is None:
        return web.json_response({"error": "forbidden"}, status=403)
    return web.json_response({
        "first_name":      profile["first_name"],
        "username":        profile["username"],
        "avatar_url":      profile["avatar_url"],
        "first_save_date": profile["first_save_date"],
        "total_saves":     profile["total_saves"],
    })


async def handle_share(request: web.Request) -> web.Response:
    try:
        entry_id = int(request.match_info["id"])
    except (KeyError, ValueError):
        return web.json_response({"error": "invalid id"}, status=400)
    entry = database.get_entry_public(entry_id)
    if entry is None:
        return web.json_response({"error": "not found"}, status=404)
    return web.json_response(entry)


def create_web_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_root)
    app.router.add_get("/app", handle_app)
    app.router.add_get("/api/entries", handle_entries)
    app.router.add_get("/api/stats", handle_stats)
    app.router.add_get("/api/me", handle_me)
    app.router.add_get("/api/share/{id}", handle_share)
    app.router.add_delete("/api/entries/{id}", handle_delete)
    return app
