"""Frame-exact takes of the real v2 game for the store videos (see vclock.js): every frame is one 1/30 s step of the
game's own clocks, so the footage is smooth however slow this machine draws.
usage: python3 video_capture.py <appstore|play> [take names]
  appstore -> 1920x886 (960x443 at 2x, iPhone landscape)     play -> 1920x1080 (960x540 at 2x)
Each take goes to <work>/takes_<target>/<take>/f00000.jpg ... with meta.json: marks (frame numbers of the moments the
edit cuts on) and the sound effects the game played, by frame (the audio is rendered later from that list)."""
import json, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
import shots_raw as SR
from playwright.sync_api import sync_playwright

SIZES = {'appstore': (960, 443, 2), 'play': (960, 540, 2)}
FPS = 30
RESULT = ("MF2.lastResult={mode:'trio',outcome:'win',place:null,trophyDelta:12,trophiesBefore:628,trophiesAfter:640,coins:36,pp:18,passXp:80,fighter:'michael',"
          "stats:{kos:4,damage:1840,hits:73},players:[{name:'מיכאל',fighter:'michael',isYou:true,team:0,damage:1840,kos:4,hits:73,score:2390},"
          "{name:'שירן',fighter:'shiran',isYou:false,team:0,damage:1210,kos:2,hits:51,score:1560},{name:'אלין',fighter:'alin',isYou:false,team:0,damage:980,kos:1,hits:44,score:1200}],"
          "mvp:{name:'מיכאל',fighter:'michael',isYou:true,title:'שחקן המשחק',why:'הכי הרבה נזק בקרב'}};MF2UI.go('results')")


class Take:
    def __init__(self, browser, target, name, rich=True):
        self.w, self.h, dpr = SIZES[target]
        self.dir = os.path.join(WORK, 'takes_' + target, name); shutil.rmtree(self.dir, ignore_errors=True); os.makedirs(self.dir)
        self.name = name; self.marks = {}; self.sfx = []; self._played = 0
        self.ctx, self.pg = open_game(browser, self.w, self.h, dpr, rich=rich, extra_init=VCLOCK_JS)
        self.pg.mouse.click(3, 3); self.pg.wait_for_timeout(400)          # the first gesture unlocks the game's sound engine
        self.pg.evaluate("MF2UI.go('lobby')"); self.pg.wait_for_timeout(600)
        self.vc = VClock(self.pg, FPS)
        self._played = self.pg.evaluate("MF2SFX.info().played")

    def _sfx(self):
        r = self.pg.evaluate("(()=>{const i=MF2SFX.info();return [i.played,i.log]})()")
        n = r[0] - self._played
        if n > 0: self.sfx += [[self.vc.n, x] for x in r[1][-n:]]
        self._played = r[0]

    def shoot(self, frames=1):
        for _ in range(frames):
            self.vc.frame(os.path.join(self.dir, 'f%05d.jpg' % self.vc.n)); self._sfx()

    def skip(self, frames):
        self.vc.skip(frames); self._played = self.pg.evaluate("MF2SFX.info().played")

    def mark(self, k): self.marks[k] = self.vc.n; print('   mark', k, self.vc.n, flush=True)

    def until(self, cond, max_frames=900):
        for _ in range(max_frames):
            if self.pg.evaluate('()=>{try{return !!(' + cond + ')}catch(e){return false}}'): return
            self.shoot()
        raise RuntimeError(self.name + ': never became true: ' + cond)

    def skip_until(self, cond, max_frames=1800):
        for _ in range(max_frames):
            if self.pg.evaluate('()=>{try{return !!(' + cond + ')}catch(e){return false}}'): return
            self.skip(1)
        raise RuntimeError(self.name + ': never became true: ' + cond)

    def js(self, s, arg=None): return self.pg.evaluate(s, arg)

    def done(self):
        json.dump({'frames': self.vc.n, 'fps': FPS, 'marks': self.marks, 'sfx': self.sfx}, open(os.path.join(self.dir, 'meta.json'), 'w'), ensure_ascii=False)
        self.ctx.close(); print('take', self.name, self.vc.n, 'frames', flush=True)


def fight_take(b, target, name, mode, bg, seed, script, lobby=None, finish_at=None, tail=75, length=None):
    """lobby (optional) -> matchmaking -> VS -> countdown -> fight. script: {frame after FIGHT: special code}."""
    t = Take(b, target, name)
    if lobby:
        t.js("MF2.select('michael');MF2.setMode('%s');MF2UI.go('lobby');" % mode + lobby); t.skip(20); t.mark('lobby'); t.shoot(90)
    t.js(FIGHT_JS)
    t.js("([m,bg,seed])=>{__fight.bg=bg;__vt.seed(seed);MF2.select('michael');MF2.setMode(m);MF2.findMatch();}", [mode, bg, seed])
    # the search itself is not filmed: the take continues when the rivals are found (the VS screen), then the last second of the countdown
    t.skip_until("__ev.some(e=>e.ev==='mm'&&e.d&&e.d.state==='found')", 1500); t.mark('found')
    t.until("typeof G!=='undefined'&&G&&G.mode!=='demo'&&!G.over&&G.fighters&&G.fighters.length>1&&!G.loading", 600); t.mark('arena')
    t.skip_until("G.cd<=64", 400); t.mark('count'); t.until("G.cd===0", 400); t.mark('fight')
    t.js("s=>{window.__n=0;window.__fin=0;__vt.direct(()=>{__n++;__fight.keep(__fin?{foeFloor:0}:{});const c=s[__n];if(c)__fight.special(c);})}", {str(k): v for k, v in script.items()})
    if finish_at:
        t.shoot(finish_at)
        # the finish: the rivals are one hit from falling, the player's next special does the rest (a real KO, with the game's own slow motion)
        t.js("()=>{__fin=1;const me=__fight.me();for(const f of G.fighters)if(f.team!==me.team&&f.alive){f.hp=Math.min(f.hp,8);f.dark=f.hp;}}")
        t.mark('finish'); t.until("G.over||G.roundT>0||G.fighters.every(f=>f.team===__fight.me().team||!f.alive)", 600); t.mark('ko'); t.shoot(tail)
    else:
        t.shoot(length)
    t.done()


def take_duel(b, target):
    fight_take(b, target, 'duel', 'duel', 'volcano', 11, {20: 'D>A', 62: 'DvA', 110: 'D^J', 170: 'D>J', 262: 'D^J', 290: 'D>J', 330: 'D>J', 370: 'D^J'},
               lobby=SR.PARTY.replace("mode:'trio'", "mode:'duel'"), finish_at=255)


def take_trio(b, target):
    fight_take(b, target, 'trio', 'trio', 'sky', 5, {25: 'D^J', 90: 'D>J', 160: 'DvA', 215: 'D^J', 270: 'D>J'}, length=300)


def take_duo(b, target):
    fight_take(b, target, 'duo', 'duo', 'japan', 3, {25: 'D>J', 85: 'D^J', 150: 'D>A', 200: 'D>J', 262: 'DvA'}, length=300)


def take_results(b, target):
    t = Take(b, target, 'results'); t.js(RESULT); t.mark('show'); t.shoot(85); t.done()


def take_chest(b, target):
    t = Take(b, target, 'chest')
    t.js(SR.DROP + "MF2UI.go('lobby');MF2UI.drop()"); t.mark('closed'); t.shoot(36)
    for i in range(40):
        if t.js("!!document.querySelector('.v2 .dfrev')"): break
        ph = t.js("document.querySelector('.v2 .drop')._drop.phase")
        if ph == 'item' and 'items' not in t.marks: t.mark('items')
        if ph == 'tap' and 'tap' not in t.marks: t.mark('tap')
        t.pg.mouse.click(t.w / 2, t.h / 2); t.shoot(14 if ph == 'item' else 11)
    else: raise SystemExit('the fighter reveal never appeared')
    t.mark('reveal'); t.until("document.querySelector('.v2 .dfrev.on')", 90); t.mark('fighter'); t.shoot(85)
    t.pg.mouse.click(t.w / 2, t.h * .3); t.shoot(8); t.mark('summary'); t.shoot(70); t.done()


def take_ui(b, target):
    t = Take(b, target, 'ui')
    t.js("MF2UI.go('fighters',{id:'michael'})"); t.skip(12); t.mark('fighters'); t.shoot(36)
    t.js("MF2UI.go('fighters',{id:'tuli'})"); t.shoot(30); t.js("MF2UI.go('fighters',{id:'boss'})"); t.shoot(36)
    t.js("MF2UI.go('modes')"); t.skip(12); t.mark('modes'); t.shoot(60)
    # the season pass and the trophy road are swiped slowly, as a player would
    swipe = "q=>{const e=document.querySelector(q);window.__sw=e;__vt.direct(()=>{if(__sw&&__sw.isConnected)__sw.scrollLeft-=%d;})}"
    t.js("MF2UI.go('shop',{tab:'pass'})"); t.skip(15); t.js(swipe % 5, '.v2 .ptrack'); t.mark('pass'); t.shoot(80)
    t.js("__vt.direct(null);MF2UI.go('road')"); t.skip(15); t.js(swipe % 7, '.v2 .road'); t.mark('road'); t.shoot(80)
    t.js("__vt.direct(null);MF2UI.go('lobby');" + SR.PARTY); t.skip(25); t.mark('lobby'); t.shoot(110); t.done()


TAKES = {'duel': take_duel, 'trio': take_trio, 'duo': take_duo, 'results': take_results, 'chest': take_chest, 'ui': take_ui}

if __name__ == '__main__':
    target = sys.argv[1]; only = sys.argv[2].split(',') if len(sys.argv) > 2 else list(TAKES)
    with sync_playwright() as p:
        b = launch(p)
        for name in only: TAKES[name](b, target)
        b.close()
