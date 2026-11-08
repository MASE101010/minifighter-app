"""Temporary App Store signing for a cloud build (no Mac or iPhone needed).
  create:  new Apple Distribution certificate + App Store profile via the API, writes signing.p12 and
           the profile into ~/Library/MobileDevice/Provisioning Profiles, prints outputs for GitHub.
  cleanup: deletes that profile and revokes that certificate (ids from signing_ids.json).
Revoking a distribution certificate does not affect apps already uploaded or on the store."""
import base64, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jwt, requests
from p8 import normalize
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

API = 'https://api.appstoreconnect.apple.com/v1'
BUNDLE = 'com.sapirproductions.minifighter'
IDS = os.path.join(os.environ.get('RUNNER_TEMP', '/tmp'), 'signing_ids.json')


def call(method, path, body=None, ok=(200, 201, 204)):
    now = int(time.time())
    tok = jwt.encode({'iss': os.environ['ASC_ISSUER_ID'], 'iat': now, 'exp': now + 1100, 'aud': 'appstoreconnect-v1'},
                     normalize(os.environ['ASC_KEY_P8']), algorithm='ES256', headers={'kid': os.environ['ASC_KEY_ID'], 'typ': 'JWT'})
    r = requests.request(method, API + path, headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'},
                         data=json.dumps(body) if body else None, timeout=60)
    if r.status_code not in ok:
        raise SystemExit(f'{method} {path} -> {r.status_code}\n{r.text[:2000]}')
    return r.json() if r.text else {}


def create():
    run = os.environ.get('GITHUB_RUN_NUMBER', 'local')
    # old CI leftovers (a cancelled run) would block new certificates
    for c in call('GET', '/certificates?filter[certificateType]=DISTRIBUTION&limit=50')['data']:
        if c['attributes'].get('displayName', '').startswith('MF-CI') or c['attributes'].get('name', '').startswith('MF-CI'):
            call('DELETE', f"/certificates/{c['id']}", ok=(204, 404, 409))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    csr = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, f'MF-CI {run}'),
        x509.NameAttribute(NameOID.EMAIL_ADDRESS, 'social@sapirfamily.co.il')])).sign(key, hashes.SHA256())
    cert = call('POST', '/certificates', {'data': {'type': 'certificates', 'attributes': {
        'certificateType': 'DISTRIBUTION', 'csrContent': csr.public_bytes(serialization.Encoding.PEM).decode()}}})['data']
    der = base64.b64decode(cert['attributes']['certificateContent'])
    pw = os.urandom(12).hex()
    p12 = pkcs12.serialize_key_and_certificates(b'mf', key, x509.load_der_x509_certificate(der), None,
                                                serialization.BestAvailableEncryption(pw.encode()))
    open(os.path.join(os.environ['RUNNER_TEMP'], 'signing.p12'), 'wb').write(p12)

    bid = call('GET', f'/bundleIds?filter[identifier]={BUNDLE}')['data']
    bid = next(b['id'] for b in bid if b['attributes']['identifier'] == BUNDLE)
    for p in call('GET', f'/bundleIds/{bid}/profiles?limit=50')['data']:
        if p['attributes']['name'].startswith('MF-CI'):
            call('DELETE', f"/profiles/{p['id']}", ok=(204, 404, 409))
    name = f'MF-CI AppStore {run}'
    prof = call('POST', '/profiles', {'data': {'type': 'profiles', 'attributes': {'name': name, 'profileType': 'IOS_APP_STORE'},
                'relationships': {'bundleId': {'data': {'type': 'bundleIds', 'id': bid}},
                                  'certificates': {'data': [{'type': 'certificates', 'id': cert['id']}]}}}})['data']
    d = os.path.expanduser('~/Library/MobileDevice/Provisioning Profiles')
    os.makedirs(d, exist_ok=True)
    uuid = prof['attributes']['uuid']
    open(os.path.join(d, uuid + '.mobileprovision'), 'wb').write(base64.b64decode(prof['attributes']['profileContent']))
    json.dump({'cert': cert['id'], 'profile': prof['id']}, open(IDS, 'w'))
    with open(os.environ['GITHUB_OUTPUT'], 'a') as o:
        o.write(f'p12_password={pw}\nprofile_name={name}\nprofile_uuid={uuid}\n')
    print('certificate', cert['id'], '| profile', name, uuid)


def cleanup():
    if not os.path.exists(IDS):
        return print('nothing to clean')
    ids = json.load(open(IDS))
    call('DELETE', f"/profiles/{ids['profile']}", ok=(204, 404, 409))
    call('DELETE', f"/certificates/{ids['cert']}", ok=(204, 404, 409))
    print('temporary profile and certificate removed')


{'create': create, 'cleanup': cleanup}[sys.argv[1]]()
