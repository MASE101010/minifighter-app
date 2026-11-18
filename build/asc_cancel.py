"""Cancel a version that waits in Pending Developer Release, so a newer build can be put on it (the API form of
"Cancel this release"). Tries the calls Apple accepts for this, in order, and prints what each one answered."""
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
    print('CANCEL', m, p.split('?')[0], r.status_code, r.text[:400].replace('\n', ' '))
    return r
want = os.environ.get('VERSION', '2.0.0')
vs = req('GET', '/v1/apps/6832263179/appStoreVersions?limit=5').json()['data']
v = next(x for x in vs if x['attributes']['versionString'] == want)
vid = v['id']; print('CANCEL state', v['attributes']['appStoreState'])
if v['attributes']['appStoreState'] == 'WAITING_FOR_REVIEW':
    # take it back out of the queue (to resubmit it together with in-app purchases)
    for s_ in req('GET', '/v1/reviewSubmissions?filter[app]=6832263179&filter[state]=WAITING_FOR_REVIEW').json()['data']:
        req('PATCH', '/v1/reviewSubmissions/' + s_['id'], {'data': {'type': 'reviewSubmissions', 'id': s_['id'], 'attributes': {'canceled': True}}})
    for i in range(12):
        time.sleep(10)
        vs = req('GET', '/v1/apps/6832263179/appStoreVersions?limit=5').json()['data']
        st = [(x['attributes']['versionString'], x['attributes']['appStoreState']) for x in vs]; print('CANCEL after', st)
        if st[0][1] != 'WAITING_FOR_REVIEW': break
    for s_ in req('GET', '/v1/reviewSubmissions?filter[app]=6832263179&limit=4').json()['data']:
        print('CANCEL submission', s_['id'], s_['attributes'].get('state'))
    sys.exit(0)
if v['attributes']['appStoreState'] != 'PENDING_DEVELOPER_RELEASE':
    sys.exit(0)
r = req('GET', f'/v1/appStoreVersions/{vid}/appStoreVersionSubmission')
if r.status_code == 200 and r.json().get('data'):
    req('DELETE', '/v1/appStoreVersionSubmissions/' + r.json()['data']['id'])
else:
    req('DELETE', '/v1/appStoreVersionSubmissions/' + vid)
time.sleep(5)
vs = req('GET', '/v1/apps/6832263179/appStoreVersions?limit=5').json()['data']
print('CANCEL after', [(x['attributes']['versionString'], x['attributes']['appStoreState']) for x in vs])
