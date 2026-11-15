"""Small App Store Connect API client shared by asc_iap.py and asc_iap_status.py (key from the environment only)."""
import hashlib, json, os, sys, time
import jwt, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p8 import normalize

API = 'https://api.appstoreconnect.apple.com'
BUNDLE = 'com.sapirproductions.minifighter'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ApiError(Exception):
    def __init__(self, msg, status=0):
        super().__init__(msg); self.status = status


_tok = {'t': None, 'at': 0}


def token():
    now = int(time.time())
    if _tok['t'] and now - _tok['at'] < 900:
        return _tok['t']
    _tok['t'] = jwt.encode({'iss': os.environ['ASC_ISSUER_ID'], 'iat': now, 'exp': now + 1100, 'aud': 'appstoreconnect-v1'},
                           normalize(os.environ['ASC_KEY_P8']), algorithm='ES256', headers={'kid': os.environ['ASC_KEY_ID'], 'typ': 'JWT'})
    _tok['at'] = now
    return _tok['t']


def call(method, path, body=None, ok404=False):
    url = path if path.startswith('http') else API + (path if path.startswith('/v') else '/v1' + path)
    for attempt in range(4):
        r = requests.request(method, url, headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'},
                             data=json.dumps(body) if body is not None else None, timeout=120)
        if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
            time.sleep(3 * (attempt + 1)); continue
        break
    if ok404 and r.status_code == 404:
        return None
    if r.status_code >= 300:
        raise ApiError(f'{method} {path} -> {r.status_code}: {r.text[:12000]}', r.status_code)
    return r.json() if r.text else {}


def all_pages(path):
    out, url = [], path
    while url:
        r = call('GET', url); out += r.get('data', []); url = r.get('links', {}).get('next')
    return out


def upload(create_path, rel_name, rel_type, rel_id, path):
    data = open(path, 'rb').read()
    typ = create_path.strip('/').split('/')[-1]
    res = call('POST', create_path, {'data': {'type': typ, 'attributes': {'fileName': os.path.basename(path), 'fileSize': len(data)},
               'relationships': {rel_name: {'data': {'type': rel_type, 'id': rel_id}}}}})['data']
    for op in res['attributes']['uploadOperations']:
        chunk = data[op['offset']:op['offset'] + op['length']]
        h = {x['name']: x['value'] for x in op.get('requestHeaders', [])}
        r = requests.request(op['method'], op['url'], headers=h, data=chunk, timeout=300)
        if r.status_code >= 300:
            raise ApiError(f'upload part -> {r.status_code}')
    call('PATCH', create_path + '/' + res['id'], {'data': {'type': res['type'], 'id': res['id'], 'attributes': {
        'uploaded': True, 'sourceFileChecksum': hashlib.md5(data).hexdigest()}}})
    return res['id']


def app_id():
    a = call('GET', f'/apps?filter[bundleId]={BUNDLE}')['data']
    if not a:
        raise SystemExit('App not found in App Store Connect')
    return a[0]['id']


def catalog():
    return json.load(open(os.path.join(ROOT, 'store', 'iap_products.json'), encoding='utf8'))['products']
