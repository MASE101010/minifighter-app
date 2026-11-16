"""Raw captures of the real v2 game for the store screenshots (no marketing frame yet).
usage: python3 shots_raw.py [names]     -> <work>/raw/<name>.png at 2868x1320 (956x440 at 3x, an iPhone in landscape)
UI screens are opened through MF2UI. The fights are real matches (see lib.FIGHT_JS); the frame with the most going on
is kept, so the shot is mid-action without anyone choosing a frame by hand."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
from playwright.sync_api import sync_playwright

W, H, D = 956, 440, 3
OUT = os.path.join(WORK, 'raw')
PARTY = ("setTimeout(()=>{const st=document.querySelector('#v2root .m2-stage');st.dataset.mf2pt='x';MF2.ui.partyStage(st,{active:true,max:3,code:'ABC234',mode:'trio',"
         "members:[{id:1,name:'מיכאל',fighter:'michael',you:true,leader:true},{id:2,name:'שירן',fighter:'shiran',ready:true},{id:3,name:'אלין',fighter:'alin',ready:true}]})},300)")
DROP = ("MF2.drops=()=>({pending:1,open:null,next:{winsToday:1,at:[1,3,5],questsBonus:true}});MF2.finishDrop=()=>({ok:true});"
        "MF2.openDrop=()=>({id:'t1',steps:[1,2,3,4,5],final:5,rewards:[{type:'coins',amount:260},{type:'pp',amount:95},{type:'gems',amount:18},{type:'fighter',fighter:'boss',name:'',rarity:5}]});")
UI = {
 'lobby': ("MF2UI.go('lobby');" + PARTY, 2600),
 'fighters': ("MF2UI.go('fighters',{id:'michael'})", 1600),
 'modes': ("MF2UI.go('modes')", 1600),
 'pass': ("MF2UI.go('shop',{tab:'pass'})", 1800),
 'road': ("MF2UI.go('road')", 1800),
}
# name: (mode, arena, seed, the player's fighter, frames to watch, the special the player fires in a loop)
FIGHTS = {
 'fight': ('duo', 'volcano', 11, 'michael', 900, 'D>J'),
 'crown': ('trio', 'sky', 5, 'michael', 900, 'D^J'),
}


def ui_shot(b, name):
    js, wait = UI[name]
    ctx, pg = open_game(b, W, H, D)
    pg.evaluate(js); pg.wait_for_timeout(wait)
    pg.screenshot(path=os.path.join(OUT, name + '.png')); ctx.close()


def chest_shot(b):
    """Open a legendary chest by tapping, keep the reveal of the new fighter once its entrance animation is over.
    Stepped with the virtual clock, so the animation state does not depend on how fast this machine draws."""
    ctx, pg = open_game(b, W, H, D, extra_init=VCLOCK_JS)
    vc = VClock(pg)
    pg.evaluate(DROP + "MF2UI.go('lobby');MF2UI.drop()"); vc.skip(45)
    for i in range(40):
        if pg.evaluate("!!document.querySelector('.v2 .dfrev')"): break
        pg.mouse.click(W / 2, H / 2); vc.skip(20)
    else: raise SystemExit('the fighter reveal never appeared')
    vc.until("document.querySelector('.v2 .dfrev.on')", 90); vc.skip(55); vc.advance(1000 / 30)
    pg.screenshot(path=os.path.join(OUT, 'chest.png')); ctx.close()


def fight_shot(b, name):
    mode, bg, seed, fighter, n, code = FIGHTS[name]
    ctx, pg = open_game(b, W, H, D, extra_init=VCLOCK_JS)
    pg.mouse.click(5, 5); pg.wait_for_timeout(300)
    vc = VClock(pg)
    start_match(pg, vc, mode, bg, seed, fighter)
    vc.until("G.cd===0", 400); vc.skip(50)                    # the FIGHT! banner is gone
    pg.evaluate("c=>{window.__n=0;__vt.direct(()=>{__fight.keep({});if(++__n%75===20)__fight.special(c);})}", code)
    best, tmp = -1, os.path.join(OUT, name + '_tmp.png')
    for i in range(n):
        vc.skip(1)
        s = pg.evaluate("__fight.score()")
        if s > best + 1:                                       # clearly better than what we have: keep this frame
            vc.pg.evaluate("new Promise(r=>__vt.real.raf(()=>__vt.real.raf(r)))")
            pg.screenshot(path=tmp); os.replace(tmp, os.path.join(OUT, name + '.png')); best = s
            print(' ', name, 'frame', i, 'score', s, flush=True)
    ctx.close()


if __name__ == '__main__':
    only = sys.argv[1].split(',') if len(sys.argv) > 1 else None
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        b = launch(p)
        for name in list(UI) + ['chest'] + list(FIGHTS):
            if only and name not in only: continue
            if name in UI: ui_shot(b, name)
            elif name == 'chest': chest_shot(b)
            else: fight_shot(b, name)
            print('raw', name, flush=True)
        b.close()
