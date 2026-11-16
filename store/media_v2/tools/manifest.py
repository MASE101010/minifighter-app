"""Check every store media file against the store specs and write store/media_v2/manifest.json (the only input of
build/asc_media.py and build/play_media.py: path, bytes, md5, pixel size, and for videos duration + poster frame).
Also writes the contact sheets. Needs Pillow and ffmpeg/ffprobe. Exits 1 when a file is out of spec."""
import hashlib, json, os, subprocess, sys
from PIL import Image

MEDIA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = {'appstore_iphone69': (2868, 1320, 8), 'appstore_iphone65': (2778, 1284, 8), 'play_phone': (1920, 1080, 8),
         'play_tablet7': (1920, 1200, 8), 'play_tablet10': (2560, 1600, 8), 'play_feature': (1024, 500, 1)}
bad = []


def entry(rel):
    data = open(os.path.join(MEDIA, rel), 'rb').read()
    return {'path': rel, 'bytes': len(data), 'md5': hashlib.md5(data).hexdigest()}


def probe(path):
    return json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', path], capture_output=True, text=True, check=True).stdout)


def shots():
    out = {}
    for folder, (w, h, n) in SHOTS.items():
        d = os.path.join(MEDIA, 'screenshots', folder)
        files = sorted(f for f in os.listdir(d) if f.lower().endswith(('.jpg', '.png'))) if os.path.isdir(d) else []
        if len(files) != n: bad.append(f'{folder}: {len(files)} files, expected {n}')
        out[folder] = []
        for f in files:
            im = Image.open(os.path.join(d, f)); e = entry(f'screenshots/{folder}/{f}'); e.update(width=im.width, height=im.height)
            if im.size != (w, h): bad.append(f'{f}: {im.width}x{im.height}, expected {w}x{h}')
            if im.mode not in ('RGB', 'L'): bad.append(f'{f}: mode {im.mode} (alpha is not allowed)')
            if e['bytes'] > 8 * 1024 * 1024: bad.append(f'{f}: over 8 MB')
            out[folder].append(e)
    return out


def video(rel, w, h, lo, hi):
    p = os.path.join(MEDIA, rel)
    if not os.path.exists(p): bad.append(rel + ' is missing'); return None
    j = probe(p); v = next(s for s in j['streams'] if s['codec_type'] == 'video'); a = next((s for s in j['streams'] if s['codec_type'] == 'audio'), None)
    e = entry(rel); dur = float(j['format']['duration']); e.update(width=v['width'], height=v['height'], duration=round(dur, 2))
    side = os.path.splitext(p)[0] + '.json'
    if os.path.exists(side): e['poster'] = json.load(open(side)).get('poster')
    if (v['width'], v['height']) != (w, h): bad.append(f"{rel}: {v['width']}x{v['height']}, expected {w}x{h}")
    if v['codec_name'] != 'h264' or v.get('profile') != 'High': bad.append(f"{rel}: video is {v['codec_name']} {v.get('profile')}, expected H.264 High")
    if v.get('pix_fmt') != 'yuv420p': bad.append(f"{rel}: pixel format {v.get('pix_fmt')}")
    if v['r_frame_rate'] != '30/1': bad.append(f"{rel}: frame rate {v['r_frame_rate']}, expected 30")
    if not lo <= dur <= hi: bad.append(f'{rel}: {dur:.2f} s, expected {lo} to {hi} s')
    if not a or a['codec_name'] != 'aac' or int(a['channels']) != 2 or a['sample_rate'] not in ('44100', '48000'):
        bad.append(f'{rel}: needs a stereo AAC track at 44.1 or 48 kHz')
    if e['bytes'] > 60 * 1024 * 1024: bad.append(f'{rel}: over 60 MB')
    e['video'] = f"h264 {v.get('profile')} {v['r_frame_rate']} fps {int(j['format']['bit_rate']) // 1000} kb/s"; e['audio'] = f"{a['codec_name']} {a['sample_rate']} Hz {a['channels']} ch" if a else None
    return e


def sheets(sh, vids):
    out = os.path.join(MEDIA, 'contact_sheets'); os.makedirs(out, exist_ok=True)
    for folder, files in sh.items():
        if len(files) < 2: continue
        ims = [Image.open(os.path.join(MEDIA, f['path'])).convert('RGB') for f in files]
        tw = 960; th = round(tw * ims[0].height / ims[0].width); sheet = Image.new('RGB', (2 * tw + 24, 4 * th + 40), '#111')
        for i, im in enumerate(ims): sheet.paste(im.resize((tw, th), Image.LANCZOS), (8 + (i % 2) * (tw + 8), 8 + (i // 2) * (th + 8)))
        sheet.save(os.path.join(out, f'screenshots_{folder}.jpg'), quality=85)
    for v in vids:
        if not v: continue
        name = os.path.splitext(os.path.basename(v['path']))[0]; n = 30; step = v['duration'] / n
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(MEDIA, v['path']), '-vf', f"fps=1/{step:.4f},scale=640:-1,tile=5x6:padding=6:margin=6", '-frames:v', '1', '-q:v', '4',
                        os.path.join(out, f'video_{name}.jpg')], check=True)


if __name__ == '__main__':
    sh = shots()
    pre = video('video/appstore_preview_1920x886.mp4', 1920, 886, 15, 30)
    promo = video('video/play_promo_1920x1080.mp4', 1920, 1080, 30, 60)
    if pre and not pre.get('poster'): bad.append('the app preview has no poster frame (video/appstore_preview_1920x886.json)')
    man = {'note': 'made by tools/manifest.py; do not edit by hand', 'locales': {'he': {
        'screenshots': sh,
        'previews': {'appstore_iphone69': [pre] if pre else [], 'appstore_iphone65': [pre] if pre else []},
        'play_promo_video': promo}}}
    json.dump(man, open(os.path.join(MEDIA, 'manifest.json'), 'w', encoding='utf8'), indent=1, ensure_ascii=False)
    if '--no-sheets' not in sys.argv: sheets(sh, [pre, promo])
    for folder, files in sh.items(): print(f'{folder}: {len(files)} files, {sum(f["bytes"] for f in files) // 1024} KB')
    for v in (pre, promo):
        if v: print(f"{v['path']}: {v['width']}x{v['height']}, {v['duration']} s, {v['bytes'] / 1048576:.1f} MB, {v['video']}, {v['audio']}, poster {v.get('poster')}")
    if bad:
        print('\nOUT OF SPEC:'); [print('  ' + b) for b in bad]; sys.exit(1)
    print('\nall files are in spec; manifest.json written')
