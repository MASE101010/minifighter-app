"""Send an uploaded iPhone build to App Review (App Store Connect API).
Waits until Apple finishes processing the build, creates or reuses the App Store version,
sets the What's New text, attaches the build and submits. Release after approval is automatic.
Env: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8, VERSION (e.g. 1.1.0), BUILD (build number)."""
import os, sys, time, json
import jwt, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p8 import normalize

BUNDLE = 'com.sapirproductions.minifighter'
API = 'https://api.appstoreconnect.apple.com/v1'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VER, BUILD = os.environ['VERSION'], os.environ['BUILD']


def token():
    now = int(time.time())
    return jwt.encode({'iss': os.environ['ASC_ISSUER_ID'], 'iat': now, 'exp': now + 1100, 'aud': 'appstoreconnect-v1'},
                      normalize(os.environ['ASC_KEY_P8']), algorithm='ES256', headers={'kid': os.environ['ASC_KEY_ID'], 'typ': 'JWT'})


def call(method, path, body=None, ok=(200, 201, 204)):
    r = requests.request(method, API + path, headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'},
                         data=json.dumps(body) if body else None, timeout=60)
    if r.status_code not in ok:
        raise SystemExit(f'{method} {path} -> {r.status_code}\n{r.text[:1500]}')
    return r.json() if r.text else {}


def notes(lang):
    p = os.path.join(ROOT, 'release_notes', lang + '.txt')
    return open(p, encoding='utf8').read().strip()[:4000] if os.path.exists(p) else ''


app = call('GET', f'/apps?filter[bundleId]={BUNDLE}')['data']
if not app:
    raise SystemExit('App not found in App Store Connect. Create it first (guide, step 5).')
app_id = app[0]['id']

# 1. wait for the build
build_id = None
for i in range(90):  # up to ~45 minutes
    b = call('GET', f'/builds?filter[app]={app_id}&filter[version]={BUILD}&filter[preReleaseVersion.version]={VER}&limit=1')['data']
    st = b[0]['attributes']['processingState'] if b else 'NOT_YET'
    print('build', VER, BUILD, st, flush=True)
    if st == 'VALID':
        build_id = b[0]['id']; break
    if st in ('FAILED', 'INVALID'):
        raise SystemExit('Apple rejected the build while processing: ' + st)
    time.sleep(30)
if not build_id:
    raise SystemExit('Build did not finish processing in time; run the submit job again later.')

# 2. the App Store version (reuse an editable one)
EDITABLE = {'PREPARE_FOR_SUBMISSION', 'DEVELOPER_REJECTED', 'REJECTED', 'METADATA_REJECTED', 'INVALID_BINARY'}
vers = call('GET', f'/apps/{app_id}/appStoreVersions?filter[platform]=IOS&limit=10')['data']
cur = next((v for v in vers if v['attributes']['appStoreState'] in EDITABLE), None)
if any(v['attributes']['appStoreState'] in ('WAITING_FOR_REVIEW', 'IN_REVIEW') for v in vers):
    raise SystemExit('Another version is already waiting for / in review. Try again after Apple finishes it.')
REL = os.environ.get('RELEASE_TYPE', 'MANUAL')   # MANUAL: the owner releases after approval
if cur:
    vid = cur['id']
    call('PATCH', f'/appStoreVersions/{vid}', {'data': {'type': 'appStoreVersions', 'id': vid, 'attributes': {'versionString': VER, 'releaseType': REL}}})
else:
    vid = call('POST', '/appStoreVersions', {'data': {'type': 'appStoreVersions',
          'attributes': {'platform': 'IOS', 'versionString': VER, 'releaseType': REL},
          'relationships': {'app': {'data': {'type': 'apps', 'id': app_id}}}}})['data']['id']
print('version', VER, vid)

# 3. What's New (not allowed on the very first version; ignored then)
for loc in call('GET', f'/appStoreVersions/{vid}/appStoreVersionLocalizations')['data']:
    lang = 'he' if loc['attributes']['locale'].startswith('he') else 'en'
    txt = notes(lang)
    if txt:
        try:
            call('PATCH', f"/appStoreVersionLocalizations/{loc['id']}",
                 {'data': {'type': 'appStoreVersionLocalizations', 'id': loc['id'], 'attributes': {'whatsNew': txt}}})
        except SystemExit as e:
            print('whatsNew skipped for', loc['attributes']['locale'])

# 4. attach the build
call('PATCH', f'/appStoreVersions/{vid}/relationships/build', {'data': {'type': 'builds', 'id': build_id}})

if os.environ.get('SUBMIT', 'true').lower() != 'true':
    print(f'Prepared {VER} ({BUILD}): version {vid} with the build attached, release {REL}. Not submitted (SUBMIT=false).')
    sys.exit(0)

# 5. submit for review
subs = call('GET', f'/reviewSubmissions?filter[app]={app_id}&filter[platform]=IOS&filter[state]=READY_FOR_REVIEW')['data']
sid = subs[0]['id'] if subs else call('POST', '/reviewSubmissions', {'data': {'type': 'reviewSubmissions',
      'attributes': {'platform': 'IOS'}, 'relationships': {'app': {'data': {'type': 'apps', 'id': app_id}}}}})['data']['id']
try:
    call('POST', '/reviewSubmissionItems', {'data': {'type': 'reviewSubmissionItems', 'relationships': {
        'reviewSubmission': {'data': {'type': 'reviewSubmissions', 'id': sid}},
        'appStoreVersion': {'data': {'type': 'appStoreVersions', 'id': vid}}}}})
except SystemExit as e:
    if 'already' not in str(e).lower():
        raise
# 5b. 2.0 catalog: every in-app purchase of store/iap_products.json that is still READY_TO_SUBMIT goes to review
# with this version (Apple reviews them with the build). Already approved ones are skipped, so this is a no-op later.
cat = os.path.join(ROOT, 'store', 'iap_products.json')
if os.environ.get('SUBMIT_IAPS', 'true').lower() == 'true' and os.path.exists(cat):
    want = {p['id'] for p in json.load(open(cat, encoding='utf8'))['products']}
    iaps, url = [], f'/apps/{app_id}/inAppPurchasesV2?limit=200'
    while url:
        r = requests.get(url if url.startswith('http') else API + url, headers={'Authorization': 'Bearer ' + token()}, timeout=60).json()
        iaps += r.get('data', []); url = r.get('links', {}).get('next')
    for i in iaps:
        a = i['attributes']
        if a['productId'] in want and a.get('state') == 'READY_TO_SUBMIT':
            try:
                call('POST', '/inAppPurchaseSubmissions', {'data': {'type': 'inAppPurchaseSubmissions', 'relationships': {
                    'inAppPurchaseV2': {'data': {'type': 'inAppPurchases', 'id': i['id']}}}}})
                print('in-app purchase sent with the version:', a['productId'])
            except SystemExit as e:
                print('in-app purchase NOT sent:', a['productId'], str(e)[:300])

call('PATCH', f'/reviewSubmissions/{sid}', {'data': {'type': 'reviewSubmissions', 'id': sid, 'attributes': {'submitted': True}}})
st = call('GET', f'/reviewSubmissions/{sid}')['data']['attributes'].get('state')
vs = call('GET', f'/appStoreVersions/{vid}')['data']['attributes'].get('appStoreState')
print(f'Submitted {VER} ({BUILD}) for App Review: submission {st}, version {vs}, release {REL}.')
