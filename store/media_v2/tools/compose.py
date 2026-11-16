"""Store screenshots for 2.0: Hebrew headline in the brand font + the framed real v2 capture, for every store size,
and the Google Play feature graphic. Input: <work>/raw/*.png from shots_raw.py. Output: store/media_v2/screenshots/.
usage: python3 compose.py [set names]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
from playwright.sync_api import sync_playwright
from PIL import Image

RAW = os.path.join(WORK, 'raw')
OUT = os.path.join(MEDIA, 'screenshots')
# folder: (width, height, file prefix)
SETS = {
 'appstore_iphone69': (2868, 1320, 'iphone69'),
 'appstore_iphone65': (2778, 1284, 'iphone65'),
 'play_phone': (1920, 1080, 'play_phone'),
 'play_tablet7': (1920, 1200, 'play_tablet7'),
 'play_tablet10': (2560, 1600, 'play_tablet10'),
}
# strongest first: (raw capture, headline before, highlighted words, headline after, background colours)
ITEMS = [
 ('fight', 'קרבות אונליין ', 'מטורפים', '', '#2b6bff', '#0b1b5c'),
 ('crown', 'שלושה על שלושה: ', 'קרב על הכתר', '', '#ff2b5a', '#5c0b22'),
 ('chest', 'פתחו תיבות וגלו ', 'לוחמים אגדיים', '', '#ff8a00', '#5c1d0b'),
 ('lobby', 'שחקו ביחד ', 'עם חברים', '', '#14b86a', '#0b4a2c'),
 ('fighters', 'אספו ושדרגו ', '27 לוחמים', '', '#00a3ff', '#0b315c'),
 ('modes', '', '4 מצבי קרב', ' לבחירה', '#7b2bff', '#1c0b5c'),
 ('pass', 'כרטיס עונה ', 'מלא פרסים', '', '#c22bff', '#3d0b5c'),
 ('road', 'טפסו בליגות ', 'ואספו גביעים', '', '#ffb800', '#5c3d0b'),
]
FONT64 = b64(FONT)
CSS = """@font-face{font-family:SP;src:url(data:font/ttf;base64,%s)}*{margin:0;box-sizing:border-box}""" % FONT64


def page(img, a, hi, b, c1, c2, W, H):
    iw, ih = Image.open(img).size
    head = H * 0.17                                             # headline band
    fw = min(W * 0.9, (H - head - H * 0.055) * iw / ih)          # the framed shot keeps the capture's aspect
    return f"""<!doctype html><html dir="rtl"><head><style>{CSS}
body{{width:{W}px;height:{H}px;overflow:hidden;font-family:SP;display:flex;flex-direction:column;align-items:center;
 background:radial-gradient(ellipse at 50% 38%,{c1} 0%,{c2} 62%,#070a24 100%)}}
.rays{{position:absolute;inset:0;background:repeating-conic-gradient(from 0deg at 50% 45%,rgba(255,255,255,.07) 0 6deg,transparent 6deg 18deg);
 -webkit-mask:radial-gradient(circle at 50% 45%,#000 0,transparent 70%)}}
h1{{position:relative;height:{head}px;display:flex;align-items:center;font-size:{head*0.6}px;line-height:1;color:#fff;letter-spacing:.5px;
 text-shadow:0 {H*0.006}px 0 #0a0e33,0 0 {H*0.03}px rgba(0,0,0,.45);-webkit-text-stroke:{H*0.004}px #0a0e33;paint-order:stroke fill;white-space:nowrap}}
h1 span{{white-space:pre}}h1 em{{font-style:normal;color:#ffd23f}}
.fr{{position:relative;width:{fw}px;border-radius:{H*0.035}px;padding:{H*0.009}px;background:linear-gradient(160deg,#ffe680,#ffb703 40%,#ff8a00);
 box-shadow:0 {H*0.02}px {H*0.05}px rgba(0,0,0,.55)}}
.fr img{{display:block;width:100%;border-radius:{H*0.028}px}}
</style></head><body><div class="rays"></div><h1><span>{a}<em>{hi}</em>{b}</span></h1><div class="fr"><img src="file://{img}"></div></body></html>"""


def feature(W=1024, H=500):
    art = os.path.join(HERE, 'keyart.webp')
    return f"""<!doctype html><html dir="rtl"><head><style>{CSS}
body{{width:{W}px;height:{H}px;overflow:hidden;font-family:SP;background:#0b1040 url(file://{art}) center 88%/cover}}
.sh{{position:absolute;inset:0;background:linear-gradient(180deg,rgba(7,10,36,0) 52%,rgba(7,10,36,.6) 72%,rgba(7,10,36,.95) 100%)}}
.t{{position:absolute;left:0;right:0;bottom:{H*0.035}px;text-align:center;line-height:1;white-space:nowrap}}
h1{{font-size:{H*0.19}px;color:#ffd23f;-webkit-text-stroke:{H*0.014}px #0a0e33;paint-order:stroke fill;text-shadow:0 {H*0.014}px 0 #0a0e33,0 0 {H*0.06}px rgba(0,0,0,.6)}}
h2{{font-size:{H*0.07}px;color:#fff;margin-top:{H*0.012}px;-webkit-text-stroke:{H*0.008}px #0a0e33;paint-order:stroke fill;font-weight:400}}
</style></head><body><div class="sh"></div><div class="t"><h1>מיני פייטר</h1><h2>קרבות אונליין עם כל החברים</h2></div></body></html>"""


def save_jpg(pg, path):
    tmp = path + '.png'; pg.screenshot(path=tmp)
    Image.open(tmp).convert('RGB').save(path, 'JPEG', quality=92, optimize=True, subsampling=0); os.remove(tmp)


if __name__ == '__main__':
    only = sys.argv[1].split(',') if len(sys.argv) > 1 else None
    tmp = os.path.join(WORK, 'compose.html'); os.makedirs(WORK, exist_ok=True)
    with sync_playwright() as p:
        br = p.chromium.launch(args=['--allow-file-access-from-files', '--force-color-profile=srgb'])
        for folder, (W, H, pre) in SETS.items():
            if only and folder not in only: continue
            os.makedirs(os.path.join(OUT, folder), exist_ok=True)
            pg = br.new_page(viewport={'width': W, 'height': H})
            for i, (n, a, hi, b, c1, c2) in enumerate(ITEMS, 1):
                open(tmp, 'w', encoding='utf8').write(page(os.path.join(RAW, n + '.png'), a, hi, b, c1, c2, W, H))
                pg.goto('file://' + tmp); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(250)
                # a headline wider than the picture is made smaller until it fits with a margin (never clipped)
                pg.evaluate("W=>{const h=document.querySelector('h1'),s=h.firstElementChild;let f=parseFloat(getComputedStyle(h).fontSize);while(s.getBoundingClientRect().width>W*.9&&f>10){f*=.97;h.style.fontSize=f+'px';}}", W)
                o = os.path.join(OUT, folder, '%s_%02d_%s_%dx%d.jpg' % (pre, i, n, W, H)); save_jpg(pg, o); print(o, flush=True)
            pg.close()
        if not only or 'feature' in only:
            os.makedirs(os.path.join(OUT, 'play_feature'), exist_ok=True)
            pg = br.new_page(viewport={'width': 1024, 'height': 500})
            open(tmp, 'w', encoding='utf8').write(feature()); pg.goto('file://' + tmp); pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(400)
            o = os.path.join(OUT, 'play_feature', 'play_feature_1024x500.jpg'); save_jpg(pg, o); print(o)
        br.close()
