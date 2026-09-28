/* ============================================================
   default-theme shell — lang-toggle · canvas net · Three.js hero ·
   scroll-reveal · GSAP count-up · hash router.
   Generic: no domain data, no domain function calls.
   Derived from docs/showcase/assets/js/01-core.js (shell portions only).
   ============================================================ */

/* ---------------- language toggle (VI default) ---------------- */
function curLang(){ return document.documentElement.classList.contains('lang-en') ? 'en' : 'vi'; }
function setLang(l){
  l = (l === 'en') ? 'en' : 'vi';
  document.documentElement.classList.toggle('lang-en', l === 'en');
  document.documentElement.classList.toggle('lang-vi', l === 'vi');
  var be = document.getElementById('btn-en'), bv = document.getElementById('btn-vi');
  if(be) be.classList.toggle('active', l === 'en');
  if(bv) bv.classList.toggle('active', l === 'vi');
  document.documentElement.lang = l;
  try{ localStorage.setItem('fap-lang', l); }catch(e){}
  // optional: re-render domain widgets if present (no-op when absent)
  var ov = document.getElementById('fap-dialog');
  if(ov && ov.classList.contains('open') && ov.dataset.kind && window.openDialog)
    window.openDialog(ov.dataset.kind, ov.dataset.id);
  if(window._renderModGrid) window._renderModGrid();
  if(window._injectModcardEngs) window._injectModcardEngs();
  if(window._mountDiagrams) window._mountDiagrams();
}
(function(){ try{ var s = localStorage.getItem('fap-lang'); if(s) setLang(s); }catch(e){} })();

/* honor prefers-reduced-motion across canvas + reveal */
var REDUCED = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

/* ---------------- scroll reveal ---------------- */
var io = new IntersectionObserver(function(entries){
  entries.forEach(function(e){
    if(!e.isIntersecting) return;
    e.target.classList.add('in');
    io.unobserve(e.target);
  });
},{threshold:.14});
document.querySelectorAll('.reveal').forEach(function(el){ io.observe(el); });

/* ---------------- hero background: 3D constellation (Three.js) ----------------
   Tries a WebGL module-network scene; falls back to the 2D canvas constellation
   when Three.js / WebGL is unavailable or prefers-reduced-motion is set. */
var HERO_COLORS = ['#38bdf8','#34d399','#ff6b3d','#a78bfa','#fbbf24'];

function init2DNet(){
  var c = document.getElementById('net'); if(!c) return;
  var x = c.getContext('2d'), W,H,pts,raf;
  function size(){ W=c.width=innerWidth; H=c.height=Math.max(innerHeight, 700); init(); }
  function init(){
    var n = Math.min(64, Math.floor(W/26)); pts = [];
    for(var i=0;i<n;i++) pts.push({x:Math.random()*W, y:Math.random()*H, vx:(Math.random()-.5)*.28, vy:(Math.random()-.5)*.28, c:HERO_COLORS[i%HERO_COLORS.length]});
  }
  function draw(){
    x.clearRect(0,0,W,H);
    for(var i=0;i<pts.length;i++){
      var p=pts[i]; p.x+=p.vx; p.y+=p.vy;
      if(p.x<0||p.x>W)p.vx*=-1; if(p.y<0||p.y>H)p.vy*=-1;
      x.beginPath(); x.arc(p.x,p.y,1.6,0,6.28); x.fillStyle=p.c; x.globalAlpha=.8; x.fill();
      for(var j=i+1;j<pts.length;j++){
        var q=pts[j], dx=p.x-q.x, dy=p.y-q.y, d=Math.sqrt(dx*dx+dy*dy);
        if(d<128){ x.globalAlpha=(1-d/128)*.22; x.strokeStyle=p.c; x.lineWidth=1; x.beginPath(); x.moveTo(p.x,p.y); x.lineTo(q.x,q.y); x.stroke(); }
      }
    }
    x.globalAlpha=1; if(!REDUCED) raf=requestAnimationFrame(draw);
  }
  size(); draw();
  addEventListener('resize', function(){ cancelAnimationFrame(raf); size(); draw(); });
  document.addEventListener('visibilitychange', function(){ if(document.hidden){cancelAnimationFrame(raf);} else if(!REDUCED){draw();} });
}

function _dotTexture(){
  var s=64, cv=document.createElement('canvas'); cv.width=cv.height=s;
  var g=cv.getContext('2d'), grd=g.createRadialGradient(s/2,s/2,0,s/2,s/2,s/2);
  grd.addColorStop(0,'rgba(255,255,255,1)'); grd.addColorStop(.35,'rgba(255,255,255,.55)'); grd.addColorStop(1,'rgba(255,255,255,0)');
  g.fillStyle=grd; g.fillRect(0,0,s,s);
  return new THREE.CanvasTexture(cv);
}
function initHero3D(){
  var c = document.getElementById('net');
  if(!c || !window.THREE) return false;
  var renderer;
  try{ renderer = new THREE.WebGLRenderer({canvas:c, alpha:true, antialias:true}); }
  catch(e){ return false; }
  renderer.setPixelRatio(Math.min(devicePixelRatio||1, 2));
  var scene = new THREE.Scene();
  var cam = new THREE.PerspectiveCamera(60, innerWidth/Math.max(innerHeight,700), 1, 400);
  cam.position.z = 64;
  var group = new THREE.Group(); scene.add(group);

  var N = Math.min(150, Math.max(70, Math.floor(innerWidth/12)));
  var R = 46, pos = new Float32Array(N*3), col = new Float32Array(N*3), nodes = [];
  var pal = HERO_COLORS.map(function(h){ return new THREE.Color(h); });
  for(var i=0;i<N;i++){
    var v = new THREE.Vector3((Math.random()*2-1)*R, (Math.random()*2-1)*R*0.7, (Math.random()*2-1)*R);
    nodes.push(v); pos[i*3]=v.x; pos[i*3+1]=v.y; pos[i*3+2]=v.z;
    var cc = pal[i%pal.length]; col[i*3]=cc.r; col[i*3+1]=cc.g; col[i*3+2]=cc.b;
  }
  var pgeo = new THREE.BufferGeometry();
  pgeo.setAttribute('position', new THREE.BufferAttribute(pos,3));
  pgeo.setAttribute('color', new THREE.BufferAttribute(col,3));
  var pmat = new THREE.PointsMaterial({size:2.6, map:_dotTexture(), vertexColors:true, transparent:true,
    depthWrite:false, blending:THREE.AdditiveBlending, sizeAttenuation:true, opacity:.95});
  group.add(new THREE.Points(pgeo, pmat));

  var lp=[], lc=[], TH=15, MAXL=320, cnt=0;
  for(var a=0;a<N && cnt<MAXL;a++) for(var b=a+1;b<N && cnt<MAXL;b++){
    if(nodes[a].distanceTo(nodes[b])<TH){
      lp.push(nodes[a].x,nodes[a].y,nodes[a].z, nodes[b].x,nodes[b].y,nodes[b].z);
      var ca=pal[a%pal.length]; lc.push(ca.r,ca.g,ca.b, ca.r,ca.g,ca.b); cnt++;
    }
  }
  var lgeo = new THREE.BufferGeometry();
  lgeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(lp),3));
  lgeo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(lc),3));
  var lmat = new THREE.LineBasicMaterial({vertexColors:true, transparent:true, opacity:.14, blending:THREE.AdditiveBlending, depthWrite:false});
  group.add(new THREE.LineSegments(lgeo, lmat));

  var mx=0, my=0, tx=0, ty=0, raf;
  addEventListener('mousemove', function(e){ tx=(e.clientX/innerWidth-.5); ty=(e.clientY/innerHeight-.5); });
  function resize(){ var h=Math.max(innerHeight,700); renderer.setSize(innerWidth,h,false); cam.aspect=innerWidth/h; cam.updateProjectionMatrix(); }
  resize(); addEventListener('resize', resize);
  function frame(){
    group.rotation.y += .0009; group.rotation.x += .00035;
    mx += (tx-mx)*.04; my += (ty-my)*.04;
    cam.position.x = mx*16; cam.position.y = -my*12; cam.lookAt(0,0,0);
    renderer.render(scene, cam);
    if(!REDUCED) raf=requestAnimationFrame(frame);
  }
  if(REDUCED){ renderer.render(scene, cam); }
  else { frame(); }
  document.addEventListener('visibilitychange', function(){ if(document.hidden){cancelAnimationFrame(raf);} else if(!REDUCED){frame();} });
  return true;
}
(function(){ if(!initHero3D()) init2DNet(); })();

/* ---------------- GSAP: stat count-ups + parallax glows ---------------- */
(function(){
  if(REDUCED || !window.gsap) return;
  if(window.ScrollTrigger) gsap.registerPlugin(ScrollTrigger);
  document.querySelectorAll('.stat .n').forEach(function(el){
    var raw = el.textContent.trim();
    if(!/^\d+$/.test(raw)) return;
    var target = parseInt(raw,10), obj = {v:0};
    el.textContent = '0';
    var play = function(){ gsap.to(obj, {v:target, duration:1.2, ease:'power2.out', onUpdate:function(){ el.textContent = Math.round(obj.v); }}); };
    if(window.ScrollTrigger) ScrollTrigger.create({trigger:el, start:'top 90%', once:true, onEnter:play});
    else play();
  });
  if(window.ScrollTrigger){
    ['.glow.g1','.glow.g2','.glow.g3'].forEach(function(sel,i){
      gsap.to(sel, {yPercent:(i%2?18:-18), ease:'none', scrollTrigger:{trigger:'body', start:'top top', end:'bottom bottom', scrub:1.2}});
    });
  }
})();

/* active-language field accessor: returns the *_en variant when lang-en, else VI */
function L(m, field){
  if(curLang() === 'en'){
    var en = m[field + '_en'];
    if(en !== undefined && en !== null) return en;
  }
  return m[field];
}

/* ---------------- single-file hash router ----------------
   Active ONLY in the portable build (every page wrapped in a [data-route] panel).
   In the multipage build there are no wrappers, so this no-ops and the baked
   .active nav class is left untouched. */
(function(){
  var panels = document.querySelectorAll('[data-route]');
  if(!panels.length) return;
  var navlinks = document.querySelectorAll('[data-nav]');
  function snap(panel){
    panel.querySelectorAll('.reveal:not(.in)').forEach(function(el){ el.classList.add('in'); });
  }
  function route(force){
    var h = (location.hash || '').replace(/^#\/?/,'') || 'hub';
    var active = null;
    panels.forEach(function(p){ if(p.dataset.route===h) active=p; });
    if(!active){ h='hub'; panels.forEach(function(p){ if(p.dataset.route==='hub') active=p; }); }
    panels.forEach(function(p){ p.hidden = (p!==active); });
    navlinks.forEach(function(a){ a.classList.toggle('active', a.dataset.nav===h); });
    document.body.classList.toggle('view-home', h==='hub');
    document.body.classList.toggle('view-guide', h!=='hub');
    document.body.classList.remove('side-open');
    if(active) snap(active);
    window.scrollTo(0,0);
    if(window._buildTOC) window._buildTOC();
  }
  addEventListener('hashchange', function(){ route(true); });
  route(false);
})();

/* ---------------- docs sidebar: mobile drawer ----------------
   Generic: wires data-side-toggle hamburger + scrim + Escape to slide the
   left nav panel in/out on mobile.  No domain data. */
(function(){
  var toggle = document.querySelector('[data-side-toggle]');
  if(!toggle) return;
  var scrim = document.querySelector('[data-scrim]');
  function set(open){
    document.body.classList.toggle('side-open', open);
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  toggle.addEventListener('click', function(){ set(!document.body.classList.contains('side-open')); });
  if(scrim) scrim.addEventListener('click', function(){ set(false); });
  addEventListener('keydown', function(e){ if(e.key==='Escape') set(false); });
  document.querySelectorAll('.docs-side .side-link').forEach(function(a){
    a.addEventListener('click', function(){ set(false); });
  });
})();

/* ---------------- docs "On this page" TOC + scroll-spy ----------------
   Generic: builds right-rail TOC from <h2> headings in the active panel.
   Re-runs on hash navigation via window._buildTOC.  No domain data. */
(function(){
  var layout = document.querySelector('.docs-layout');
  var tocEl = document.querySelector('[data-toc]');
  if(!layout || !tocEl) return;
  var spy = null, seq = 0;
  var smooth = (typeof REDUCED !== 'undefined' && REDUCED) ? 'auto' : 'smooth';
  function activeRoot(){
    var panel = document.querySelector('[data-route]:not([hidden])');
    return panel || layout.querySelector('.docs-main') || layout;
  }
  function build(){
    if(spy){ spy.disconnect(); spy = null; }
    var root = activeRoot();
    var items = [];
    if(root){
      root.querySelectorAll('h2').forEach(function(h){
        if(!(h.textContent || '').trim()) return;
        if(!h.id) h.id = 'toc-h-' + (seq++);
        items.push(h);
      });
    }
    if(items.length < 2){
      tocEl.innerHTML = '';
      layout.classList.remove('has-toc');
      return;
    }
    var html = '<div class="toc-h"><span class="en">On this page</span><span class="vi">Trên trang này</span></div>';
    items.forEach(function(h){
      html += '<a href="#' + h.id + '" data-toc-link="' + h.id + '">' + h.innerHTML + '</a>';
    });
    tocEl.innerHTML = html;
    layout.classList.add('has-toc');
    tocEl.querySelectorAll('a').forEach(function(a){
      a.addEventListener('click', function(e){
        e.preventDefault();
        var el = document.getElementById(a.dataset.tocLink);
        if(el) el.scrollIntoView({behavior: smooth, block: 'start'});
      });
    });
    spy = new IntersectionObserver(function(entries){
      entries.forEach(function(en){
        if(!en.isIntersecting) return;
        var id = en.target.id;
        tocEl.querySelectorAll('a').forEach(function(a){ a.classList.toggle('active', a.dataset.tocLink === id); });
      });
    }, {rootMargin: '0px 0px -70% 0px', threshold: 0});
    items.forEach(function(h){ spy.observe(h); });
  }
  window._buildTOC = build;
  build();
})();
