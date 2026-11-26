"""Release a version that is Pending Developer Release to the App Store (the owner asked for it)."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jwt, requests
from p8 import normalize
API = 'https://api.appstoreconnect.apple.com'
def req(m, p, body=None):
    now = int(time.time())
    t = jwt.encode({'iss': os.environ['ASC_ISSUER_ID'], 'iat': now, 'exp': now + 1100, 'aud': 'appstoreconnect-v1'},
                   normalize(os.environ['ASC_KEY_P8']), algorithm='ES256', headers={'kid': os.environ['ASC_KEY_ID'], 'typ': 'JWT'})
    r = requests.request(m, API + p, headers={'Authorization': 'Bearer ' + t, 'Content-Type': 'application/json'},
                         data=json.dumps(body) if body else None, timeout=60)
    print('LIVE', m, p.split('?')[0], r.status_code, '' if r.status_code < 300 and m == 'GET' else r.text[:400].replace('\n', ' '))
    return r
want = os.environ.get('VERSION', '2.0.0')
def states():
    return [(x['id'], x['attributes']['versionString'], x['attributes']['appStoreState'])
            for x in req('GET', '/v1/apps/6832263179/appStoreVersions?limit=5').json()['data']]
st = states(); print('LIVE before', [s[1:] for s in st])
v = next(s for s in st if s[1] == want)
if v[2] != 'PENDING_DEVELOPER_RELEASE':
    print('LIVE not pending developer release: ' + v[2])
    sys.exit(0 if os.environ.get('QUIET') else 1)
r = req('POST', '/v1/appStoreVersionReleaseRequests', {'data': {'type': 'appStoreVersionReleaseRequests',
        'relationships': {'appStoreVersion': {'data': {'type': 'appStoreVersions', 'id': v[0]}}}}})
if r.status_code >= 300:
    sys.exit(1)
for i in range(6):
    time.sleep(15); st = states(); print('LIVE after', [s[1:] for s in st])
    if next(s for s in st if s[1] == want)[2] != 'PENDING_DEVELOPER_RELEASE': break
