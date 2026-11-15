"""Create or update every Mini Fighter 2.0 in-app product on Google Play (safe to run again).
Source: store/iap_products.json. Uses the one-time products API (monetization.onetimeproducts); if the account
does not have it, falls back to the legacy inappproducts API. Google has no consumable flag: every product is a
one-time product and the game consumes gem packs (and a finished season's pass) after granting them.
Price: the ILS price for Israel, every other region from Google's own conversion (convertRegionPrices), new regions
from the converted USD / EUR price. Listings in Hebrew and English. The purchase option is activated.
premium_all is read (for the Hebrew language code) and never changed.
`python3 build/play_iap.py status` only prints the products."""
import json, os, sys, time, traceback
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession

PKG = 'com.sapirproductions.minifighter'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = f'https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PKG}'
STATUS_ONLY = len(sys.argv) > 1 and sys.argv[1] == 'status'
ONLY = [x for x in os.environ.get('IAP_ONLY', '').replace(',', ' ').split() if x]
OPTION = 'buy'

raw = os.environ.get('PLAY_SA', '')
if not raw.strip():
    sys.exit('PLAY_SERVICE_ACCOUNT_JSON secret is missing')
creds = service_account.Credentials.from_service_account_info(json.loads(raw), scopes=['https://www.googleapis.com/auth/androidpublisher'])
S = AuthorizedSession(creds)
del raw


class ApiError(Exception):
    def __init__(self, msg, status):
        super().__init__(msg); self.status = status


def call(method, path, body=None, params=None, ok404=False):
    for attempt in range(4):
        r = S.request(method, BASE + path, json=body, params=params, timeout=120)
        if r.status_code in (429, 500, 502, 503) and attempt < 3:
            time.sleep(4 * (attempt + 1)); continue
        break
    if ok404 and r.status_code == 404:
        return None
    if r.status_code >= 300:
        raise ApiError(f'{method} {path} -> {r.status_code}: {r.text[:2000]}', r.status_code)
    return r.json() if r.text else {}


def money(v, cur):
    units = int(v); nanos = int(round((v - units) * 1e9))
    return {'currencyCode': cur, 'units': str(units), 'nanos': nanos}


def fmt(m):
    return f"{m['currencyCode']} {int(m.get('units', 0)) + m.get('nanos', 0) / 1e9:.2f}" if m else '-'


PRODUCTS = [p for p in json.load(open(os.path.join(ROOT, 'store', 'iap_products.json'), encoding='utf8'))['products']
            if not ONLY or p['id'] in ONLY]

# which API, and which code Play uses for Hebrew (iw-IL in most accounts)
MODE, HE = 'new', 'iw-IL'
try:
    pa = call('GET', '/oneTimeProducts/premium_all', ok404=True)
    if pa:
        for l in pa.get('listings', []):
            if l['languageCode'].split('-')[0] in ('iw', 'he'):
                HE = l['languageCode']
        print('premium_all found in the one-time products API; Hebrew code', HE)
    else:
        call('GET', '/oneTimeProducts', params={'pageSize': 1})
        print('one-time products API available (premium_all not listed there)')
except ApiError as e:
    print('one-time products API not usable:', str(e)[:300]); MODE = 'legacy'
    try:
        old = call('GET', '/inappproducts/premium_all', ok404=True)
        for k in (old or {}).get('listings', {}):
            if k.split('-')[0] in ('iw', 'he'):
                HE = k
    except ApiError as e2:
        print('legacy API too:', str(e2)[:300])
print('mode', MODE)


def status():
    rows = []
    if MODE == 'new':
        tok = None
        while True:
            r = call('GET', '/oneTimeProducts', params={'pageSize': 100, **({'pageToken': tok} if tok else {})})
            for p in r.get('oneTimeProducts', []):
                il, st = None, []
                for o in p.get('purchaseOptions', []):
                    st.append(f"{o['purchaseOptionId']}:{o.get('state')}")
                    for c in o.get('regionalPricingAndAvailabilityConfigs', []):
                        if c['regionCode'] == 'IL':
                            il = c.get('price')
                rows.append((p['productId'], 'one-time', fmt(il), ' '.join(st), ','.join(l['languageCode'] for l in p.get('listings', []))))
            tok = r.get('nextPageToken')
            if not tok:
                break
    else:
        for p in call('GET', '/inappproducts').get('inappproduct', []):
            rows.append((p['sku'], p.get('purchaseType'), f"{p['defaultPrice']['currency']} {int(p['defaultPrice']['priceMicros']) / 1e6:.2f}",
                         p.get('status'), ','.join(p.get('listings', {}))))
    have = {r[0] for r in rows}
    print(f"\n{'product id':22} {'type':10} {'IL price':12} {'state':24} listings")
    for r in rows:
        print(f'PLAY {r[0]:22} {r[1]:10} {r[2]:12} {r[3]:24} {r[4]}')
    for p in PRODUCTS:
        if p['id'] not in have:
            print(f"PLAY {p['id']:22} MISSING")
    return rows


if STATUS_ONLY:
    status(); sys.exit(0)

REPORT = []


def listings(p):
    return [{'languageCode': HE, 'title': p['he']['name'], 'description': p['he']['play']},
            {'languageCode': 'en-US', 'title': p['en']['name'], 'description': p['en']['play']}]


def ensure_new(p):
    pid, out = p['id'], []
    conv = call('POST', '/pricing:convertRegionPrices', {'price': money(p['ils'], 'ILS')})
    ver = (conv.get('regionVersion') or {}).get('version') or '2022/02'
    cfg = []
    for code, c in sorted(conv.get('convertedRegionPrices', {}).items()):
        price = money(p['ils'], 'ILS') if code == 'IL' else c['price']
        cfg.append({'regionCode': code, 'price': price, 'availability': 'AVAILABLE'})
    if not any(c['regionCode'] == 'IL' for c in cfg):
        cfg.append({'regionCode': 'IL', 'price': money(p['ils'], 'ILS'), 'availability': 'AVAILABLE'})
    other = conv.get('convertedOtherRegionsPrice') or {}
    cur = call('GET', f'/oneTimeProducts/{pid}', ok404=True)
    opt_id = OPTION
    if cur:
        buys = [o for o in cur.get('purchaseOptions', []) if 'buyOption' in o]
        if buys:
            opt_id = buys[0]['purchaseOptionId']
    opt = {'purchaseOptionId': opt_id, 'buyOption': {'legacyCompatible': True, 'multiQuantityEnabled': False},
           'regionalPricingAndAvailabilityConfigs': cfg}
    if other.get('usdPrice') and other.get('eurPrice'):
        opt['newRegionsConfig'] = {'usdPrice': other['usdPrice'], 'eurPrice': other['eurPrice'], 'availability': 'AVAILABLE'}
    body = {'packageName': PKG, 'productId': pid, 'listings': listings(p), 'purchaseOptions': [opt]}
    if cur:   # keep any other purchase option the owner added by hand
        body['purchaseOptions'] += [o for o in cur.get('purchaseOptions', []) if o['purchaseOptionId'] != opt_id]
    res = call('PATCH', f'/onetimeproducts/{pid}', body, params={'allowMissing': 'true', 'updateMask': 'listings,purchaseOptions',
               'regionsVersion.version': ver, 'latencyTolerance': 'PRODUCT_UPDATE_LATENCY_TOLERANCE_LATENCY_TOLERANT'})
    out.append(('updated' if cur else 'created') + f' (regions {len(cfg)}, version {ver})')
    st = next((o.get('state') for o in res.get('purchaseOptions', []) if o['purchaseOptionId'] == opt_id), None)
    if st != 'ACTIVE':
        call('POST', f'/oneTimeProducts/{pid}/purchaseOptions:batchUpdateStates', {'requests': [{'activatePurchaseOptionRequest': {
            'packageName': PKG, 'productId': pid, 'purchaseOptionId': opt_id,
            'latencyTolerance': 'PRODUCT_UPDATE_LATENCY_TOLERANCE_LATENCY_TOLERANT'}}]})
        out.append('activated')
    else:
        out.append('active')
    return '; '.join(out)


def ensure_legacy(p):
    pid = p['id']
    body = {'packageName': PKG, 'sku': pid, 'status': 'active', 'purchaseType': 'managedUser', 'defaultLanguage': HE,
            'defaultPrice': {'priceMicros': str(int(round(p['ils'] * 1e6))), 'currency': 'ILS'},
            'listings': {l['languageCode']: {'title': l['title'], 'description': l['description']} for l in listings(p)}}
    had = call('GET', f'/inappproducts/{pid}', ok404=True)
    call('PUT', f'/inappproducts/{pid}', body, params={'allowMissing': 'true', 'autoConvertMissingPrices': 'true'})
    return ('updated' if had else 'created') + ' (legacy API, other prices auto-converted)'


for p in PRODUCTS:
    name = f"{p['id']} (₪{p['ils']:.2f})"
    try:
        REPORT.append(('OK', name, (ensure_new if MODE == 'new' else ensure_legacy)(p)))
    except Exception as e:
        REPORT.append(('FAIL', name, str(e)[:900])); traceback.print_exc()

status()
print('\n===== SUMMARY =====')
for s, n, r in REPORT:
    print(f'[{s}] {n}: {r}')
fails = [r for r in REPORT if r[0] == 'FAIL']
print(f'{len(REPORT) - len(fails)} ok, {len(fails)} failed')
sys.exit(1 if fails else 0)
