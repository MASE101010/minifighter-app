"""Attach a demo video to App Review information of the current version (replaces older attachments)."""
import hashlib, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jwt, requests
from p8 import normalize
API = 'https://api.appstoreconnect.apple.com/v1'
BUNDLE = 'com.sapirproductions.minifighter'
FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'store', 'mini_fighter_review_demo.mp4')

def call(m, p, b=None):
    now = int(time.time())
    t = jwt.encode({'iss': os.environ['ASC_ISSUER_ID'], 'iat': now, 'exp': now + 1100, 'aud': 'appstoreconnect-v1'},
                   normalize(os.environ['ASC_KEY_P8']), algorithm='ES256', headers={'kid': os.environ['ASC_KEY_ID'], 'typ': 'JWT'})
    r = requests.request(m, p if p.startswith('http') else API + p, headers={'Authorization': 'Bearer ' + t, 'Content-Type': 'application/json'},
                         data=json.dumps(b) if b else None, timeout=120)
    if r.status_code >= 300:
        sys.exit(f'{m} {p} -> {r.status_code}\n{r.text[:2000]}')
    return r.json() if r.text else {}

app = call('GET', f'/apps?filter[bundleId]={BUNDLE}')['data'][0]['id']
v = call('GET', f'/apps/{app}/appStoreVersions?filter[platform]=IOS&limit=5')['data'][0]
print('version', v['attributes']['versionString'], v['attributes']['appStoreState'])
rd = call('GET', f"/appStoreVersions/{v['id']}/appStoreReviewDetail")['data']
for a in call('GET', f"/appStoreReviewDetails/{rd['id']}/appStoreReviewAttachments")['data']:
    call('DELETE', f"/appStoreReviewAttachments/{a['id']}"); print('removed old', a['attributes']['fileName'])
data = open(FILE, 'rb').read()
res = call('POST', '/appStoreReviewAttachments', {'data': {'type': 'appStoreReviewAttachments',
      'attributes': {'fileName': os.path.basename(FILE), 'fileSize': len(data)},
      'relationships': {'appStoreReviewDetail': {'data': {'type': 'appStoreReviewDetails', 'id': rd['id']}}}}})['data']
for op in res['attributes']['uploadOperations']:
    h = {x['name']: x['value'] for x in op.get('requestHeaders', [])}
    r = requests.request(op['method'], op['url'], headers=h, data=data[op['offset']:op['offset'] + op['length']], timeout=300)
    assert r.status_code < 300, r.status_code
call('PATCH', f"/appStoreReviewAttachments/{res['id']}", {'data': {'type': 'appStoreReviewAttachments', 'id': res['id'],
     'attributes': {'uploaded': True, 'sourceFileChecksum': hashlib.md5(data).hexdigest()}}})
for i in range(20):
    st = call('GET', f"/appStoreReviewAttachments/{res['id']}")['data']['attributes'].get('assetDeliveryState', {})
    print('state', st.get('state'));
    if st.get('state') in ('COMPLETE', 'FAILED'): break
    time.sleep(6)
print('attached', os.path.basename(FILE), len(data) // 1024, 'KB')
