"""Print App Store status of Mini Fighter versions, builds and the in-app purchase."""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jwt, requests
from p8 import normalize
def call(p):
    now = int(time.time())
    t = jwt.encode({'iss': os.environ['ASC_ISSUER_ID'], 'iat': now, 'exp': now + 1100, 'aud': 'appstoreconnect-v1'},
                   normalize(os.environ['ASC_KEY_P8']), algorithm='ES256', headers={'kid': os.environ['ASC_KEY_ID'], 'typ': 'JWT'})
    r = requests.get('https://api.appstoreconnect.apple.com' + p, headers={'Authorization': 'Bearer ' + t}, timeout=60)
    j = r.json()
    if 'data' not in j:
        print('STATUS api error', p, r.status_code, json.dumps(j.get('errors', j))[:300])
        if os.environ.get('DIAG') != '1':
            os.environ['DIAG'] = '1'
            for q in ('/v1/apps/6832263179', '/v1/apps?limit=5', '/v1/users?limit=1'):
                r2 = requests.get('https://api.appstoreconnect.apple.com' + q, headers=r.request.headers, timeout=60); print('STATUS diag', q, r2.status_code, r2.text[:200])
        sys.exit(1)
    return j
app = call('/v1/apps?filter[bundleId]=com.sapirproductions.minifighter')['data'][0]['id']
for v in call(f'/v1/apps/{app}/appStoreVersions?limit=5')['data']:
    a = v['attributes']; print('STATUS version', a['versionString'], a['appStoreState'], a.get('appVersionState'))
for s in call(f'/v1/reviewSubmissions?filter[app]={app}&limit=5')['data']:
    print('STATUS submission', s['attributes'].get('state'), s['attributes'].get('submittedDate'))
for i in call(f'/v1/apps/{app}/inAppPurchasesV2')['data']:
    print('STATUS iap', i['attributes']['productId'], i['attributes']['state'])
for b in call(f'/v1/builds?filter[app]={app}&sort=-uploadedDate&limit=5&include=preReleaseVersion')['data']:
    a = b['attributes']; print('STATUS build', a.get('version'), a.get('processingState'), a.get('uploadedDate'), 'expired' if a.get('expired') else '')
try:
    for c in ('il', 'us'):
        r = requests.get(f'https://itunes.apple.com/lookup?id={app}&country={c}&t={int(time.time())}', timeout=30).json()['results']
        print('STATUS store', c, [(x.get('version'), x.get('currentVersionReleaseDate')) for x in r])
except Exception as e:
    print('STATUS store lookup failed', e)
