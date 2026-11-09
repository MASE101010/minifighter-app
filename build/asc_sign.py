"""App Store signing for a cloud build (no Mac or iPhone needed).
  create: reuses the stored Apple Distribution certificate + App Store profile (store/signing/, encrypted with a
          key derived from the App Store Connect API key secret), or creates them once via the API and stores them.
          Writes signing.p12 and installs the profile; prints outputs for GitHub.
The certificate must NOT be revoked: Apple re-checks the signature at review, and a revoked certificate makes
every uploaded build that has not been approved yet an Invalid Binary."""
import base64, hashlib, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jwt, requests
from p8 import normalize
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from cryptography.fernet import Fernet

API = 'https://api.appstoreconnect.apple.com/v1'
BUNDLE = 'com.sapirproductions.minifighter'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, 'store', 'signing')
PROFILE_NAME = 'MF AppStore'


def fernet():
    k = hashlib.sha256(('mf-signing|' + normalize(os.environ['ASC_KEY_P8'])).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(k))


def install_profile(content_b64, uuid):
    d = os.path.expanduser('~/Library/MobileDevice/Provisioning Profiles')
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, uuid + '.mobileprovision'), 'wb').write(base64.b64decode(content_b64))


def outputs(pw, uuid):
    with open(os.environ['GITHUB_OUTPUT'], 'a') as o:
        o.write(f'p12_password={pw}\nprofile_name={PROFILE_NAME}\nprofile_uuid={uuid}\n')


def call(method, path, body=None, ok=(200, 201, 204)):
    now = int(time.time())
    tok = jwt.encode({'iss': os.environ['ASC_ISSUER_ID'], 'iat': now, 'exp': now + 1100, 'aud': 'appstoreconnect-v1'},
                     normalize(os.environ['ASC_KEY_P8']), algorithm='ES256', headers={'kid': os.environ['ASC_KEY_ID'], 'typ': 'JWT'})
    r = requests.request(method, API + path, headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'},
                         data=json.dumps(body) if body else None, timeout=60)
    if r.status_code not in ok:
        raise SystemExit(f'{method} {path} -> {r.status_code}\n{r.text[:2000]}')
    return r.json() if r.text else {}


def bundle_id():
    bid = call('GET', f'/bundleIds?filter[identifier]={BUNDLE}')['data']
    return next(b['id'] for b in bid if b['attributes']['identifier'] == BUNDLE)


def profile_for(cert_id, bid):
    """Existing active profile with our name for this certificate, or a new one."""
    for p in call('GET', f'/bundleIds/{bid}/profiles?limit=50')['data']:
        a = p['attributes']
        if a['name'] == PROFILE_NAME and a.get('profileState') == 'ACTIVE':
            certs = call('GET', f"/profiles/{p['id']}/certificates")['data']
            if any(c['id'] == cert_id for c in certs):
                return p
            call('DELETE', f"/profiles/{p['id']}", ok=(204, 404, 409))
        elif a['name'].startswith('MF') :
            call('DELETE', f"/profiles/{p['id']}", ok=(204, 404, 409))
    return call('POST', '/profiles', {'data': {'type': 'profiles', 'attributes': {'name': PROFILE_NAME, 'profileType': 'IOS_APP_STORE'},
                'relationships': {'bundleId': {'data': {'type': 'bundleIds', 'id': bid}},
                                  'certificates': {'data': [{'type': 'certificates', 'id': cert_id}]}}}})['data']


def create():
    os.makedirs(STORE, exist_ok=True)
    meta_p, p12_p = os.path.join(STORE, 'meta.json'), os.path.join(STORE, 'dist.p12.enc')
    p12 = cert_id = None
    if os.path.exists(meta_p) and os.path.exists(p12_p):
        meta = json.load(open(meta_p))
        try:
            call('GET', f"/certificates/{meta['cert']}")
            p12 = fernet().decrypt(open(p12_p, 'rb').read()); cert_id = meta['cert']
            print('reusing stored certificate', cert_id)
        except SystemExit:
            print('stored certificate no longer valid, creating a new one')
    if p12 is None:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        csr = x509.CertificateSigningRequestBuilder().subject_name(x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, 'Mini Fighter CI'),
            x509.NameAttribute(NameOID.EMAIL_ADDRESS, 'social@sapirfamily.co.il')])).sign(key, hashes.SHA256())
        cert = call('POST', '/certificates', {'data': {'type': 'certificates', 'attributes': {
            'certificateType': 'DISTRIBUTION', 'csrContent': csr.public_bytes(serialization.Encoding.PEM).decode()}}})['data']
        cert_id = cert['id']
        der = base64.b64decode(cert['attributes']['certificateContent'])
        p12 = pkcs12.serialize_key_and_certificates(b'mf', key, x509.load_der_x509_certificate(der), None,
                                                    serialization.BestAvailableEncryption(b'mf-ci'))
        open(p12_p, 'wb').write(fernet().encrypt(p12))
        json.dump({'cert': cert_id}, open(meta_p, 'w'))
        with open(os.environ['GITHUB_OUTPUT'], 'a') as o:
            o.write('new_cert=true\n')
        print('created and stored new certificate', cert_id)
    open(os.path.join(os.environ['RUNNER_TEMP'], 'signing.p12'), 'wb').write(p12)
    prof = profile_for(cert_id, bundle_id())
    if 'profileContent' not in prof['attributes']:
        prof = call('GET', f"/profiles/{prof['id']}")['data']
    install_profile(prof['attributes']['profileContent'], prof['attributes']['uuid'])
    outputs('mf-ci', prof['attributes']['uuid'])
    print('profile', PROFILE_NAME, prof['attributes']['uuid'])


{'create': create}[sys.argv[1]]()
