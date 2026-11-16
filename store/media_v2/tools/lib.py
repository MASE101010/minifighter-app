"""Shared helpers for the 2.0 store media tools: open the v2 web build in headless Chromium with a rich local
save, fully offline, and (for the videos) step the page with Chrome's virtual time so every frame is exact.
Nothing here changes the game: the page is the shipped build, driven through its own MF2 / MF2UI interface."""
import base64, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
MEDIA = os.path.dirname(HERE)                                   # store/media_v2
ROOT = os.path.dirname(os.path.dirname(MEDIA))                  # the app repository
WEB = os.path.abspath(os.environ.get('MF_WEB', os.path.join(ROOT, 'game', 'v2web')))   # the split v2 build
WORK = os.path.abspath(os.environ.get('MF_WORK', os.path.join(MEDIA, '.work')))        # raw captures (not committed)
FONT = os.path.join(HERE, 'SapirPop-Hebrew3.ttf')
URL = 'file://' + os.path.join(WEB, 'index.html')

CFG = {"keys": [{"U": ["KeyW"], "Dn": ["KeyS"], "L": ["KeyA"], "R": ["KeyD"], "A": ["KeyJ"], "J": ["KeyK"], "D": ["KeyL"]},
                {"U": ["ArrowUp"], "Dn": ["ArrowDown"], "L": ["ArrowLeft"], "R": ["ArrowRight"], "A": ["Comma"], "J": ["Period"], "D": ["Slash"]}],
       "tmoves": "swipe", "v3": 1, "musVol": .7, "sfxVol": .8}
SEED = {'qk2_unlocked': '["boss","virus"]', 'qk2_stage': '7', 'qk2_cfg': json.dumps(CFG), 'qk2_premium': '1',
        'qk2_ads': '{"sessions":41,"lastAO":1762900000000,"lastI":1762900500000}', 'qk2_adunlock': '{"boss":5,"virus":2}'}

# no proxy and no DNS: the page cannot reach the rooms server, ads or fonts, so matches fill with the game's bots
LAUNCH_ARGS = ['--no-proxy-server', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1',
               '--autoplay-policy=no-user-gesture-required', '--force-color-profile=srgb', '--disable-lcd-text',
               '--allow-file-access-from-files']

EVENTS = r"""(()=>{window.__ev=[];const t=setInterval(()=>{if(window.MF2&&MF2.on&&!window.__hooked){window.__hooked=1;
 ['mm','result'].forEach(ev=>MF2.on(ev,d=>{let c;try{c=JSON.parse(JSON.stringify(d===undefined?null:d))}catch(e){c=String(d)}__ev.push({ev,d:c})}));clearInterval(t);}},20);})();"""

# A long-time player's save: most fighters owned and levelled, coins, gems, pass progress. Player name in Hebrew.
RICH = r"""(()=>{const S=MF2._.S,ids=Object.keys(MF2.state().fighters);let k=0;
 for(const id of ids){const f=S.fighters[id]||(S.fighters[id]={u:false,lvl:1,pp:0,tr:0,best:0});if(k++<23||id==='michael'||id==='shiran'||id==='tuli'){f.u=true;f.lvl=3+(k*7)%7;f.tr=80+(k*53)%260;f.best=f.tr+20;}}
 S.name='מיכאל';S.coins=12450;S.gems=860;S.level=Math.max(S.level||1,18);if(S.fighters.michael){S.fighters.michael.lvl=9;S.fighters.michael.tr=640;}
 try{S.pass.xp=5200;S.pass.prem=true;S.pass.claimed=[1,2,3,4,5,6,7,8,9,10,11];S.pass.pclaimed=[1,2,3,4,5,6,7,8,9];}catch(e){}
 try{const q=S.quests.list;q[0].prog=1;q[1].prog=9;q[2].prog=44;}catch(e){}
 MF2._.changed();
 try{MF2._.setIAP({native:true,ready:true,listed:()=>true,price:id=>({mf_pass_premium:'₪19.90'})[id]||'₪9.90'});}catch(e){}})()"""


def launch(p):
    return p.chromium.launch(args=LAUNCH_ARGS)


def open_game(browser, w, h, dpr, rich=True, extra_init=''):
    """New context + page with the seeded save, on the lobby. Returns (ctx, page)."""
    ctx = browser.new_context(viewport={'width': w, 'height': h}, device_scale_factor=dpr, is_mobile=True, has_touch=True,
                              locale='he-IL')
    pg = ctx.new_page(); pg.add_init_script(EVENTS)
    if extra_init: pg.add_init_script(extra_init)
    pg.goto(URL); pg.wait_for_timeout(300)
    pg.evaluate("it=>{localStorage.clear();for(const k in it)localStorage.setItem(k,it[k]);}", SEED)
    pg.reload(); pg.wait_for_timeout(2500)
    pg.wait_for_function("window.MF2&&typeof MF2.state==='function'&&window.__hooked", timeout=15000)
    if 'tester' in pg.url or pg.evaluate("!!MF2.tester"):
        raise SystemExit('tester mode is on: refusing to capture')
    pg.evaluate("try{MF2.ackWelcome&&MF2.ackWelcome()}catch(e){};document.querySelectorAll('.v2 .scrim').forEach(e=>e.remove())")
    if rich: pg.evaluate(RICH)
    return ctx, pg


def b64(path):
    return base64.b64encode(open(path, 'rb').read()).decode()


VCLOCK_JS = open(os.path.join(HERE, 'vclock.js'), encoding='utf8').read()


class VClock:
    """Frame-exact stepping (see vclock.js). The page must have been opened with extra_init=VCLOCK_JS."""
    def __init__(self, page, fps=30):
        self.pg = page; self.fps = fps; self.n = 0
        self.cdp = page.context.new_cdp_session(page)
        page.evaluate('__vt.freeze()')

    def advance(self, ms):
        self.pg.evaluate('ms=>__vt.step(ms)', ms)

    def frame(self, path, quality=93):
        """Advance one frame and save it."""
        self.advance(1000.0 / self.fps)
        self.pg.screenshot(path=path, type='jpeg', quality=quality, animations='allow', caret='initial')
        self.n += 1

    def skip(self, frames=1):
        """Advance frames that are not captured (fast)."""
        self.pg.evaluate('([ms,n])=>__vt.skip(ms,n)', [1000.0 / self.fps, frames])

    def until(self, cond, max_frames=1800, shoot=None):
        """Advance until the JS expression is true. shoot(i) is called per frame when the frames are being captured."""
        for i in range(max_frames):
            if self.pg.evaluate('()=>{try{return !!(' + cond + ')}catch(e){return false}}'): return i
            if shoot: shoot(i)
            else: self.skip(1)
        raise RuntimeError('never became true: ' + cond)

    def release(self):
        self.pg.evaluate('__vt.thaw()')


# ---------- fights ----------
# The capture drives real matches of the shipped build: MF2.findMatch (offline, so the game fills the match with its own
# bots), the engine's own AI for every fighter, real special moves through Fighter.trySpecial. The director below only
# keeps the fight lively for the camera: mana stays high so specials are frequent, nobody dies before the planned moment.
FIGHT_JS = r"""
window.__fight={
 bg:null,
 hook(){if(window.__fight.h)return;window.__fight.h=1;const o=startGame;startGame=function(cfg){try{if(cfg&&cfg.mf2&&window.__fight.bg)cfg.bg=window.__fight.bg;}catch(e){}return o.apply(this,arguments);};},
 me(){return G&&G.humans&&G.humans[0];},
 // per frame: the player's fighter is played by the engine's AI, mana kept up, hp floors
 keep(o){o=o||{};const me=this.me();if(!me)return;if(o.auto!==false&&!me.ai)me.ai=true;
  for(const f of G.fighters){if(!f.alive)continue;if(f.mp<(o.mp||140))f.mp=o.mp||140;
   const floor=(f.team===me.team?(o.allyFloor===undefined?.45:o.allyFloor):(o.foeFloor===undefined?.2:o.foeFloor))*f.hpMax;if(f.hp<floor){f.hp=floor;f.dark=Math.max(f.dark,floor);}}},
 special(code,face){const me=this.me();if(!me||!me.alive)return false;if(!me.canAct()){me.setState('idle');}me.mp=Math.max(me.mp,300);if(face)me.face=face;else{const e=nearestEnemy(me,me.team);if(e)me.face=e.x>=me.x?1:-1;}return me.trySpecial(code);},
 state(){if(typeof G==='undefined'||!G)return null;const me=this.me();return {frame:G.frame,cd:G.cd,over:!!G.over,round:G.round,projs:G.projs.length,fx:G.fx.length,hitstop:G.hitstop,cam:G.cam,W:W,
  f:G.fighters.map(f=>({id:f.def.id,team:f.team,x:Math.round(f.x),z:Math.round(f.z),y:Math.round(f.y),st:f.state,hp:Math.round(f.hp),alive:f.alive,me:f===me}))};},
 // how much is going on in the frame (used to pick the screenshot moments)
 score(){const me=this.me();if(!me||G.cd||G.over||G.loading)return -1;let s=0;const on=x=>x>G.cam+90&&x<G.cam+W-90;
  for(const p of G.projs)if(on(p.x))s+=p.owner===me?5:2;s+=Math.min(8,G.fx.length);
  for(const f of G.fighters){if(!f.alive||!on(f.x))continue;s+=1;if(f.state==='special')s+=f===me?4:3;else if(f.state==='attack')s+=2;else if((f.state==='hurt'||f.state==='fall')&&f.team!==me.team)s+=5;else if(f.state==='lying')s-=1;}
  if(!on(me.x)||me.state==='lying'||me.state==='hurt'||me.state==='fall'||me.state==='dizzy')s-=14;if(me.state==='special'&&me.t>14)s+=8;
  if(G.hitstop>0)s+=3;const e=nearestEnemy(me,me.team);if(e&&Math.abs(e.x-me.x)<460&&on(e.x))s+=3;return s;}
};__fight.hook();
"""


def start_match(pg, vc, mode, bg=None, seed=7, fighter='michael'):
    """lobby -> matchmaking -> the fight is loaded and the countdown is about to start. Not captured."""
    pg.evaluate(FIGHT_JS)
    pg.evaluate("([m,bg,seed,f])=>{__fight.bg=bg;__vt.seed(seed);MF2.select(f);MF2.setMode(m);MF2.findMatch();}", [mode, bg, seed, fighter])
    vc.until("__ev.some(e=>e.ev==='mm'&&e.d&&e.d.state==='found')", 1500)
    vc.until("typeof G!=='undefined'&&G&&G.mode!=='demo'&&!G.over&&G.fighters&&G.fighters.length>1&&!G.loading", 600)
