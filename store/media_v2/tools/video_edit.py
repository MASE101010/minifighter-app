"""Cut the store videos from the takes of video_capture.py: App Store app preview (1920x886) and Google Play promo
master (1920x1080). Hard cuts on the beat of the game's fight music (150 bpm: 12 frames a beat), short Hebrew captions
in the brand font, sound = the game's own music file + the game's own sound effects, rendered by the game's sound
engine (MF2SFX.render) from the list of effects that really played in each take.
usage: python3 video_edit.py [video names]"""
import base64, json, os, subprocess, sys, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
from playwright.sync_api import sync_playwright
from PIL import Image, ImageFilter, ImageEnhance

FPS = 30
OUT = os.path.join(MEDIA, 'video')
SFX_DIR = os.path.join(os.path.dirname(WEB), 'v2web', 'm')


def seg(take, mark, off, n, cap=None, y=.3, d=0):
    return dict(take=take, mark=mark, off=off, n=n, cap=cap, y=y, d=d)


# caption: *...* is the highlighted part. y = vertical centre of the caption as a fraction of the footage height
# (chosen per scene so it never covers the fighters or the lobby hero). d = frames before the caption appears.
PREVIEW = [
 seg('duel', 'lobby', 8, 48, 'מיני פייטר *2.0*', .88),
 seg('duel', 'arena', -36, 36),
 seg('duel', 'fight', -12, 120, 'קרבות אונליין *מטורפים*', .3, 40),
 seg('duel', 'fight', 108, 84, 'מהלכים מיוחדים *לכל לוחם*'),
 seg('duel', 'ko', -44, 84),
 seg('trio', 'fight', 70, 120, 'שלושה על שלושה: *קרב על הכתר*', .3),
 seg('results', 'show', 14, 48),
 seg('chest', 'tap', 40, 60, 'פתחו תיבות *וגלו לוחמים*', .9),
 seg('chest', 'fighter', -22, 72),
 seg('ui', 'fighters', 20, 48, '*27 לוחמים* לאסוף ולשדרג', .9),
 seg('ui', 'modes', 6, 36, '*4 מצבי קרב*', .9),
 seg('ui', 'pass', 4, 48, 'כרטיס עונה *מלא פרסים*', .9),
 seg('ui', 'road', 4, 30, 'טפסו *בליגות*', .9),
 seg('ui', 'lobby', 6, 54, '*מיני פייטר*  שחקו עכשיו', .88),
]
PROMO = [
 seg('duel', 'lobby', 0, 72, 'מיני פייטר *2.0*', .88),
 seg('duel', 'arena', -48, 48),
 seg('duel', 'fight', -12, 132, 'קרבות אונליין *מטורפים*', .3, 40),
 seg('duel', 'fight', 120, 96, 'מהלכים מיוחדים *לכל לוחם*'),
 seg('duel', 'ko', -44, 96),
 seg('trio', 'fight', 70, 168, 'שלושה על שלושה: *קרב על הכתר*', .3),
 seg('duo', 'fight', 16, 144, 'זוגות: *שניים על שניים*'),
 seg('results', 'show', 6, 72),
 seg('chest', 'tap', 28, 96, 'פתחו תיבות *וגלו לוחמים*', .9),
 seg('chest', 'items', -66, 48),
 seg('chest', 'fighter', -22, 96),
 seg('chest', 'summary', 6, 48),
 seg('ui', 'fighters', 6, 84, '*27 לוחמים* לאסוף ולשדרג', .9),
 seg('ui', 'modes', 6, 48, '*4 מצבי קרב* לבחירה', .9),
 seg('ui', 'pass', 4, 72, 'כרטיס עונה *מלא פרסים*', .9),
 seg('ui', 'road', 4, 60, 'טפסו בליגות *ואספו גביעים*', .9),
 seg('ui', 'lobby', 6, 84, '*מיני פייטר*  שחקו עכשיו', .88),
]
# name: (width, height, cut, takes folder, poster frame = (take, mark, offset) or None)
VIDEOS = {
 'appstore_preview_1920x886': (1920, 886, PREVIEW, 'appstore', ('duel', 'fight', 180)),
 'play_promo_1920x1080': (1920, 1080, PROMO, 'play', None),
}


def caption_png(pg, text, path, W, style):
    a, hi, b = (text.split('*') + ['', ''])[:3]
    fs = 62 if style == 'pill' else 60
    box = ("background:rgba(8,12,48,.82);border:4px solid #ffc21a;border-radius:999px;padding:14px 44px 18px;box-shadow:0 8px 24px rgba(0,0,0,.5)"
           if style == 'pill' else "padding:6px 20px")
    pg.set_content(f"""<html dir="rtl"><head><style>@font-face{{font-family:SP;src:url(data:font/ttf;base64,{b64(FONT)})}}
html,body{{margin:0;background:transparent}}body{{width:{W}px;display:flex;justify-content:center;align-items:flex-start;padding:30px 0}}
#c{{font-family:SP;font-size:{fs}px;line-height:1;color:#fff;white-space:pre;{box};-webkit-text-stroke:5px #0a0e33;paint-order:stroke fill;text-shadow:0 4px 0 #0a0e33}}
em{{font-style:normal;color:#ffd23f}}</style></head><body><span id="c">{a}<em>{hi}</em>{b}</span></body></html>""")
    pg.evaluate('document.fonts.ready'); pg.wait_for_timeout(120)
    pg.locator('#c').screenshot(path=path, omit_background=True)


def timeline(cut, takes):
    """-> frames [(jpg path, segment index, frame in segment)], sound events [(seconds, name)], segment starts."""
    frames, events, starts = [], [], []
    for si, s in enumerate(cut):
        d = os.path.join(takes, s['take']); m = json.load(open(os.path.join(d, 'meta.json')))
        if s['mark'] not in m['marks']: raise SystemExit(f"take {s['take']} has no mark {s['mark']}")
        f0 = m['marks'][s['mark']] + s['off']
        if f0 < 0 or f0 + s['n'] > m['frames']: raise SystemExit(f"segment {si} ({s['take']} {s['mark']}{s['off']:+d} x{s['n']}) is outside the take (0..{m['frames']})")
        for k in range(s['n']):
            p = os.path.join(d, 'f%05d.jpg' % (f0 + k))
            if not os.path.exists(p): raise SystemExit('frame missing (not captured): ' + p)
            frames.append((p, si, k))
        t0 = len(frames) - s['n']; starts.append(t0)
        events += [((t0 + fr - f0) / FPS, name) for fr, name in m['sfx'] if f0 <= fr < f0 + s['n'] - 2]
    return frames, sorted(events), starts


def render_sfx(pg, events, seconds, path):
    """The game's sound engine renders its own effects offline (48 kHz stereo, with its compressor and limiter)."""
    ev = [[round(t + .02, 3), n, 1, 0] for t, n in events if t < seconds - .3]
    data = pg.evaluate("""async ([ev,secs])=>{const r=await MF2SFX.render('mix',{song:'none',events:ev.filter(e=>MF2SFX.has(e[1])),seconds:secs,sr:48000,master:true,music:0});
      const L=r.ch[0],R=r.ch[1]||r.ch[0],o=new Int16Array(L.length*2);for(let i=0;i<L.length;i++){o[2*i]=Math.max(-1,Math.min(1,L[i]))*32767;o[2*i+1]=Math.max(-1,Math.min(1,R[i]))*32767;}
      const u=new Uint8Array(o.buffer);let s='';for(let i=0;i<u.length;i+=32768)s+=String.fromCharCode.apply(null,u.subarray(i,i+32768));return btoa(s);}""", [ev, seconds])
    with wave.open(path, 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); w.writeframes(base64.b64decode(data))
    return len(ev)


def find_asset(prefix):
    for f in sorted(os.listdir(SFX_DIR)):
        if f.startswith(prefix + '.') and f.endswith('.mp3'): return os.path.join(SFX_DIR, f)
    raise SystemExit('game sound file not found: ' + prefix)


def build(name, pg_cap, pg_game):
    W, H, cut, src, poster = VIDEOS[name]
    takes = os.path.join(WORK, 'takes_' + src)
    if not os.path.isdir(takes): takes = os.path.join(WORK, 'takes_appstore')      # no native takes: the iPhone footage is centred on a blurred copy
    tmp = os.path.join(WORK, 'edit_' + name); os.makedirs(tmp, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    frames, events, starts = timeline(cut, takes); total = len(frames); secs = total / FPS
    fw, fh = Image.open(frames[0][0]).size
    boxed = (fw, fh) != (W, H)                    # footage of another aspect: centred over a blurred copy, captions in the lower band
    y0 = (H - fh) // 2
    caps = {}
    for si, s in enumerate(cut):
        if s['cap']:
            p = os.path.join(tmp, 'cap%02d.png' % si); caption_png(pg_cap, s['cap'], p, W, 'band' if boxed else 'pill'); caps[si] = Image.open(p).convert('RGBA')
    silent = os.path.join(tmp, 'video.mp4')
    ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                           '-c:v', 'libx264', '-profile:v', 'high', '-level', '4.2', '-pix_fmt', 'yuv420p', '-preset', 'medium', '-crf', '19', '-maxrate', '12M', '-bufsize', '24M',
                           '-g', '30', '-bf', '2', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-movflags', '+faststart', silent], stdin=subprocess.PIPE)
    for i, (p, si, k) in enumerate(frames):
        im = Image.open(p).convert('RGB')
        if boxed:
            bg = im.resize((W // 8, H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(6)).resize((W, H), Image.BILINEAR)
            bg = ImageEnhance.Brightness(bg).enhance(.38); bg.paste(im, ((W - fw) // 2, y0)); im = bg
        c = caps.get(si)
        if c is not None:
            n = cut[si]['n']; kk = k - cut[si]['d']; a = min(1, (kk + 1) / 5, (n - k) / 4)   # quick fade in and out inside the segment
            if a > 0:
                pop = 1 + .12 * max(0, 1 - kk / 6)                              # small pop on entry
                cc = c if pop == 1 else c.resize((round(c.width * pop), round(c.height * pop)), Image.LANCZOS)
                if a < 1: cc = cc.copy(); cc.putalpha(cc.getchannel('A').point(lambda v: int(v * a)))
                cy = H - (H - fh) // 4 - 2 if boxed else round(H * cut[si]['y'])
                im.paste(cc, ((W - cc.width) // 2, max(0, min(H - cc.height, cy - cc.height // 2))), cc)
        ff.stdin.write(im.tobytes())
    ff.stdin.close()
    if ff.wait(): raise SystemExit('ffmpeg failed encoding ' + name)
    # sound
    sfx = os.path.join(tmp, 'sfx.wav'); n_ev = render_sfx(pg_game, events, secs, sfx)
    # inputs: 0 the picture, 1 the game's fight music (looped), 2 the rendered effects, 3.. the game's sampled stingers
    ins = ['-stream_loop', '-1', '-ss', '0.15', '-i', find_asset('music_fight'), '-i', sfx]
    filt = [f'[1:a]atrim=0:{secs:.3f},volume=1.5,afade=t=in:d=0.05,afade=t=out:st={secs - 1.2:.3f}:d=1.2[m]', '[2:a]volume=0.9[s]']; mix = '[m][s]'; n_in = 3
    samples = {'victory': 'victory', 'chest_shake': 'chest'}; used = set()
    for t, nm in events:
        if nm in samples and nm not in used and t < secs - .5:
            used.add(nm); ins += ['-i', find_asset(samples[nm])]
            filt.append(f'[{n_in}:a]adelay={int(t * 1000)}:all=1,volume=0.8[x{n_in}]'); mix += f'[x{n_in}]'; n_in += 1
    filt.append(mix + f'amix=inputs={n_in - 1}:normalize=0:duration=longest,alimiter=limit=0.89,atrim=0:{secs:.3f},aresample=48000,aformat=channel_layouts=stereo[a]')
    out = os.path.join(OUT, name + '.mp4')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', silent] + ins + ['-filter_complex', ';'.join(filt), '-map', '0:v', '-map', '[a]', '-c:v', 'copy',
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2', '-t', f'{secs:.3f}', '-movflags', '+faststart', out], check=True)
    info = {'frames': total, 'seconds': round(secs, 3), 'sound_events': n_ev}
    if poster:
        take, mark, off = poster; m = json.load(open(os.path.join(takes, take, 'meta.json'))); want = m['marks'][mark] + off; pf = None
        for si, s in enumerate(cut):
            f0 = m['marks'].get(s['mark'], 0) + s['off'] if s['take'] == take else None
            if f0 is not None and f0 <= want < f0 + s['n']: pf = starts[si] + want - f0
        if pf is None: pf = starts[2] + 60
        info['poster'] = '00:00:%02d:%02d' % (pf // FPS, pf % FPS)
    json.dump(info, open(os.path.join(OUT, name + '.json'), 'w')); print(name, info, flush=True)


if __name__ == '__main__':
    only = sys.argv[1].split(',') if len(sys.argv) > 1 else list(VIDEOS)
    with sync_playwright() as p:
        b = launch(p)
        cap = b.new_page(viewport={'width': 1920, 'height': 300})
        ctx, game = open_game(b, 640, 360, 1, rich=False)
        game.mouse.click(3, 3); game.wait_for_timeout(300)
        for name in only: build(name, cap, game)
        b.close()
