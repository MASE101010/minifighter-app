/* Virtual clock for frame-exact captures (store media tools; injected before the game's own scripts, the game is untouched).
   Every clock the page reads (performance.now, Date, timers, requestAnimationFrame, the audio clock) comes from one
   virtual time. Until __vt.freeze() it follows real time, so the game behaves as usual. After freeze() time only moves in
   __vt.step(ms): due timers run in order, then the animation frame callbacks, and CSS animations / transitions are
   paused and moved by the same amount. One step = one video frame, however long the screenshot takes. */
(()=>{
 if(window.__vt)return;
 const R={now:performance.now.bind(performance),raf:window.requestAnimationFrame.bind(window),st:window.setTimeout.bind(window),D:Date};
 let vnow=R.now(),frozen=false,seq=1,lastReal=R.now();
 const epoch=R.D.now()-vnow;
 const timers=new Map();let rafs=new Map();
 performance.now=()=>vnow;
 const VD=function(...a){if(!new.target)return new R.D(epoch+vnow).toString();return a.length?new R.D(...a):new R.D(epoch+vnow);};
 VD.prototype=R.D.prototype;VD.now=()=>Math.floor(epoch+vnow);VD.parse=R.D.parse;VD.UTC=R.D.UTC;window.Date=VD;
 window.setTimeout=(fn,ms,...a)=>{const id=seq++;timers.set(id,{fn,at:vnow+Math.max(0,+ms||0),a,every:0,id});return id;};
 window.setInterval=(fn,ms,...a)=>{const id=seq++;const e=Math.max(1,+ms||0);timers.set(id,{fn,at:vnow+e,a,every:e,id});return id;};
 window.clearTimeout=window.clearInterval=id=>{timers.delete(id);};
 window.requestAnimationFrame=fn=>{const id=seq++;rafs.set(id,fn);return id;};
 window.cancelAnimationFrame=id=>{rafs.delete(id);};
 try{for(const C of [window.AudioContext,window.webkitAudioContext]){if(!C)continue;
  Object.defineProperty(C.prototype,'currentTime',{configurable:true,get(){return vnow/1000;}});}}catch(e){}
 const call=(fn,a)=>{try{if(typeof fn==='function')fn.apply(window,a);else (0,eval)(String(fn));}catch(e){console.error(e);}};
 function runTimers(target,sync){
  for(let guard=0;guard<20000;guard++){let best=null;
   for(const t of timers.values())if(t.at<=target&&(!best||t.at<best.at||(t.at===best.at&&t.id<best.id)))best=t;
   if(!best)break;if(best.at>vnow)vnow=best.at;
   if(best.every)best.at+=best.every;else timers.delete(best.id);
   call(best.fn,best.a);}
  vnow=target;}
 function runRafs(){const cur=rafs;rafs=new Map();for(const fn of cur.values())call(fn,[vnow]);}
 const seen=new WeakSet();
 function anims(ms){let list;try{list=document.getAnimations();}catch(e){return;}
  for(const a of list){try{
   if(!seen.has(a)){seen.add(a);if(a.playState==='running'||a.pending){a.pause();a.currentTime=Math.min(+a.currentTime||0,ms);}continue;}
   if(a.playState!=='paused')continue;
   const end=a.effect?a.effect.getComputedTiming().endTime:Infinity,t=(+a.currentTime||0)+ms*(a.playbackRate||1);
   if(isFinite(end)&&t>=end)a.finish();else a.currentTime=t;}catch(e){}}}
 // real-time pump (before freeze)
 function pump(){if(frozen)return;const r=R.now(),dt=Math.min(100,r-lastReal);lastReal=r;runTimers(vnow+dt);runRafs();R.raf(pump);}
 R.raf(pump);
 const tick=()=>new Promise(r=>R.st(r,0));
 // seeded Math.random, so a scene started with __vt.seed(n) plays the same way on every run
 let rs=0;const R0=Math.random;Math.random=()=>{if(!rs)return R0();rs|=0;rs=rs+0x6D2B79F5|0;let t=Math.imul(rs^rs>>>15,1|rs);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};
 let director=null;
 window.__vt={
  now:()=>vnow,frozen:()=>frozen,
  freeze(){frozen=true;try{for(const a of document.getAnimations()){seen.add(a);if(a.playState==='running'||a.pending)a.pause();}}catch(e){}},
  thaw(){frozen=false;try{for(const a of document.getAnimations())if(a.playState==='paused')a.play();}catch(e){}lastReal=R.now();R.raf(pump);},
  // one frame: timers, animation frame callbacks, CSS animations; resolves after two real frames so the page is painted
  async step(ms){if(director)call(director,[vnow]);runTimers(vnow+ms);await tick();runRafs();anims(ms);await new Promise(r=>R.raf(()=>R.raf(r)));return vnow;},
  // the same without waiting for a paint (frames that are not captured)
  async skip(ms,n){for(let i=0;i<(n||1);i++){if(director)call(director,[vnow]);runTimers(vnow+ms);await tick();runRafs();anims(ms);}return vnow;},
  seed(n){rs=n|0;},direct(fn){director=fn;},
  real:R};
})();
