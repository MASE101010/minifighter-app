"""Android emulator: where the real AdMob banner is on screen (dumpsys view tree) against the lobby slot the page
reports (MFSMOKE lay: fight / mode buttons, nameplate, CSS px; dpr). usage: android_banner.py dumpsys.txt log.txt"""
import json, re, sys
dump, log = open(sys.argv[1], errors='replace').read(), open(sys.argv[2], errors='replace').read()
lay = None
for line in log.splitlines():
    i = line.find('MFSMOKE {')
    if i >= 0:
        try:
            d = json.loads(line[i + 8:].strip())
            if d.get('lay'): lay = d['lay']
        except Exception:
            pass
stack, found = [], {}
for line in dump.splitlines():
    m = re.match(r'^(\s*)([\w.$]+)\{[^}]*?\s(-?\d+),(-?\d+)-(-?\d+),(-?\d+)', line)
    if not m:
        continue
    ind = len(m.group(1)); x0, y0, x1, y1 = map(int, m.group(3, 4, 5, 6))
    while stack and stack[-1][0] >= ind:
        stack.pop()
    px, py = (stack[-1][1], stack[-1][2]) if stack else (0, 0)
    ax, ay = px + x0, py + y0
    stack.append((ind, ax, ay))
    name = m.group(2)
    if name.endswith('AdView') and y1 > y0:
        found['ad'] = (ax, ay, ax + x1 - x0, ay + y1 - y0)
    if 'WebView' in name and 'web' not in found:
        found['web'] = (ax, ay, ax + x1 - x0, ay + y1 - y0)
print('views:', found, '| page:', lay and {k: lay[k] for k in ('w', 'h', 'dpr', 'ad')})
if not lay or 'ad' not in found or 'web' not in found:
    print('BANNER CHECK: no banner view on screen' + ('' if lay else ' (no lobby layout from the page)')); sys.exit(2)
s, (wx, wy) = lay['dpr'], found['web'][:2]
a = [(found['ad'][0] - wx) / s, (found['ad'][1] - wy) / s, (found['ad'][2] - wx) / s, (found['ad'][3] - wy) / s]
f, m = lay['fight'], lay['mode']
L, R = (f, m) if f[0] < m[0] else (m, f)
gl, gr = a[0] - L[2], R[0] - a[2]
dbot = a[3] - min(f[3], m[3])
pl = lay.get('plate')
pg = None if not pl else max(max(a[0], pl[0]) - min(a[2], pl[2]), max(a[1], pl[1]) - min(a[3], pl[3]))
ok = gl >= 11.5 and gr >= 11.5 and abs(dbot) <= 2 and (pg is None or pg >= 11.5)
print('BANNER CHECK', 'PASS' if ok else 'FAIL', '| banner (CSS px)', [round(v, 1) for v in a], '| gap to buttons L', round(gl, 1), 'R', round(gr, 1),
      '| bottom vs slot', round(dbot, 1), '| gap to nameplate', None if pg is None else round(pg, 1))
sys.exit(0 if ok else 1)
