"""Make store/iap_products.json from the game's product list (minifighter-source docs/STORE_PRODUCTS.md).
Run locally after STORE_PRODUCTS.md changes, then commit the json:
    python3 build/iap_catalog.py /home/claude/minifighter-source/docs/STORE_PRODUCTS.md [--check-meta]
--check-meta also loads game/src/v2/meta.js with node and checks that ids, types and prices match the code.
The store scripts (asc_iap.py, play_iap.py) read only the json, so the workflows need no access to the game repo.
premium_all is not in the json: it is live on both stores and stays as it is."""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'store', 'iap_products.json')

# English store texts (the doc has Hebrew only). Apple: name <= 30, description <= 45. Google: name <= 55, description <= 200.
EN_FIGHTER = {'elroei': 'Elroei', 'alin': 'Alin', 'elaor': 'Elaor', 'hop': 'Hop', 'fox': 'Fox', 'tiger': 'Tiger',
              'hatul': 'Hatul', 'lito': 'Lito', 'raz': 'Dragon', 'noa': 'Kim', 'sheleg': 'Frozen', 'lehava': 'Lehava',
              'barak': 'Barak', 'sela': 'The Mountain', 'maya': 'Ninjati', 'tal': 'The Professor', 'virus': 'The Virus',
              'boss': 'The Shadow'}
EN_GEMS = {1: 'Handful of Gems', 2: 'Bag of Gems', 3: 'Box of Gems', 4: 'Crate of Gems', 5: 'Mountain of Gems'}
EN_SKIN = {'michael_h': ('Skin: Hanukkah Michael', 'Hanukkah skin for Michael: a blue and white hero suit'),
           'tuli_h': ('Skin: Hanukkah Tuli', 'Hanukkah skin for Tuli: a blue sweater and a knitted hat'),
           'hop_h': ('Skin: Festive Hop', 'Hanukkah skin for Hop: a shiny blue coat')}


def cells(line):
    return [c.strip().strip('`').strip() for c in line.strip().strip('|').split('|')]


def parse(md):
    rows, head = [], None
    for line in md.splitlines():
        if not line.startswith('|'):
            head = None; continue
        c = cells(line)
        if head is None:
            head = [h.lower() for h in c]; continue
        if set(''.join(c)) <= set('-: '):
            continue
        if head[:2] != ['id', 'type'] or 'ils' not in head:
            continue
        r = dict(zip(head, c))
        if r['id'] == 'premium_all':
            continue
        rows.append(r)
    return rows


def product(r):
    pid, t = r['id'], r['type'].lower()
    ils = float(re.search(r'\d+(?:\.\d+)?', r['ils']).group(0))
    if 'season' in t:
        kind, apple = 'season', 'NON_RENEWING_SUBSCRIPTION'
    elif t.startswith('non-consumable'):
        kind, apple = 'nonconsumable', 'NON_CONSUMABLE'
    elif t.startswith('consumable'):
        kind, apple = 'consumable', 'CONSUMABLE'
    else:
        raise SystemExit(f'{pid}: unknown type {t!r}')
    title = r['store title']
    gdesc = r.get('google play description') or r.get('google play / app store description')
    adesc = r.get('app store description') or r.get('google play / app store description')
    if pid.startswith('mf_gems_'):
        n = int(pid.rsplit('_', 1)[1]); gems = re.search(r'\d+', adesc).group(0)
        bonus = re.search(r'(\d+)%', adesc)
        en = (EN_GEMS[n], f'{gems} gems' + (f', {bonus.group(1)}% bonus' if bonus else ''),
              f'{gems} gems for Mini Fighter' + (f' ({bonus.group(1)}% bonus)' if bonus else ''))
        section = 'gems'
    elif pid.startswith('mf_fighter_'):
        f = EN_FIGHTER[pid[len('mf_fighter_'):]]
        en = (f'Fighter: {f}', f'Unlocks {f} forever', f'Unlocks the fighter {f} forever')
        section = 'fighters'
    elif pid.startswith('mf_skin_'):
        k = pid[len('mf_skin_'):]
        nm, ds = EN_SKIN.get(k, (f'Skin: {k}', f'A new look for a fighter'))
        en = (nm, ds.split(':')[0], ds); section = 'skins'
    elif pid == 'mf_offer_starter':
        en = ('Starter Offer', '100 gems, 800 coins, 200 power points',
              'One time pack: 100 gems, 800 coins and 200 power points'); section = 'offers'
    elif pid == 'mf_bundle_hero':
        en = ('Hero Bundle', 'Ninjati, 150 gems, 1500 coins', 'Ninjati, 150 gems and 1500 coins'); section = 'bundles'
    elif pid == 'mf_bundle_legend':
        en = ('Legend Bundle', 'Shadow, Professor, 400 gems, 4000 coins',
              'The Shadow and The Professor, 400 gems, 4000 coins and 300 power points'); section = 'bundles'
    elif pid == 'mf_pass_premium':
        en = ('Premium Season Pass', 'The premium track of the season',
              'The premium track of the current season: coins, gems, power points and chests'); section = 'pass'
    else:
        raise SystemExit(f'{pid}: no English text, add it to build/iap_catalog.py')
    p = dict(id=pid, kind=kind, appleType=apple, ils=ils, section=section, reference=f'{en[0]} ({pid})'[:64],
             he=dict(name=title, apple=adesc, play=gdesc), en=dict(name=en[0], apple=en[1], play=en[2]))
    for loc in ('he', 'en'):
        L = p[loc]
        assert len(L['name']) <= 30, (pid, loc, L['name'])
        assert len(L['apple']) <= 45, (pid, loc, L['apple'], len(L['apple']))
        assert len(L['play']) <= 200, (pid, loc)
        assert '—' not in L['name'] + L['apple'] + L['play'], (pid, 'em dash')
    return p


def check_meta(products, src):
    js = ("const C=require(process.argv[1]);const o={};for(const [id,p] of Object.entries(C.PRODUCTS))o[id]={type:p.type,ils:p.ils};"
          "console.log(JSON.stringify(o))")
    meta = json.loads(subprocess.run(['node', '-e', js, os.path.join(src, 'game', 'src', 'v2', 'meta.js')],
                                     capture_output=True, text=True, check=True).stdout)
    bad = []
    mine = {p['id']: p for p in products}
    for i in sorted(set(meta) | set(mine)):
        a, b = meta.get(i), mine.get(i)
        if not a or not b:
            bad.append(f'{i}: only in ' + ('the doc' if b else 'meta.js')); continue
        want = {'consumable': 'consumable', 'nonconsumable': 'nonconsumable', 'season': 'season'}[b['kind']]
        if a['type'] != want or abs(a['ils'] - b['ils']) > 0.001:
            bad.append(f"{i}: meta {a} vs doc {b['kind']} {b['ils']}")
    return bad


if __name__ == '__main__':
    doc = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else '/home/claude/minifighter-source/docs/STORE_PRODUCTS.md'
    products = [product(r) for r in parse(open(doc, encoding='utf8').read())]
    ids = [p['id'] for p in products]
    assert len(ids) == len(set(ids)), 'duplicate ids'
    if '--check-meta' in sys.argv:
        bad = check_meta(products, os.path.dirname(os.path.dirname(os.path.abspath(doc))))
        if bad:
            sys.exit('doc and meta.js differ:\n' + '\n'.join(bad))
        print('meta.js matches the doc')
    json.dump({'source': 'minifighter-source docs/STORE_PRODUCTS.md', 'products': products},
              open(OUT, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    for p in products:
        print(f"{p['id']:22} {p['appleType']:26} {p['ils']:6.2f}  {p['he']['name']}")
    print(len(products), 'products ->', OUT)
