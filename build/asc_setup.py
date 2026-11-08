"""Fill the App Store page for Mini Fighter through the App Store Connect API (safe to run again).
Texts (he + en-US), category, age rating, screenshots, review notes, free price, and the
premium_all in-app purchase. Every step is independent: a failure is reported and the rest continue.
App Privacy answers are not in the public API and are filled in the browser."""
import hashlib, json, os, sys, time, traceback
import jwt, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p8 import normalize

API = 'https://api.appstoreconnect.apple.com'
BUNDLE = 'com.sapirproductions.minifighter'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT = []


def token():
    now = int(time.time())
    return jwt.encode({'iss': os.environ['ASC_ISSUER_ID'], 'iat': now, 'exp': now + 1100, 'aud': 'appstoreconnect-v1'},
                      normalize(os.environ['ASC_KEY_P8']), algorithm='ES256', headers={'kid': os.environ['ASC_KEY_ID'], 'typ': 'JWT'})


class ApiError(Exception):
    pass


def call(method, path, body=None):
    url = path if path.startswith('http') else API + (path if path.startswith('/v') else '/v1' + path)
    r = requests.request(method, url, headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'},
                         data=json.dumps(body) if body is not None else None, timeout=120)
    if r.status_code >= 300:
        raise ApiError(f'{method} {path} -> {r.status_code}: {r.text[:800]}')
    return r.json() if r.text else {}


def step(name):
    def wrap(fn):
        try:
            res = fn(); REPORT.append(('OK', name, res or ''))
        except Exception as e:
            REPORT.append(('FAIL', name, str(e)[:600])); traceback.print_exc()
    return wrap


def upload(create_path, rel_name, rel_type, rel_id, path, extra=None):
    data = open(path, 'rb').read()
    att = {'fileName': os.path.basename(path), 'fileSize': len(data)}
    att.update(extra or {})
    res = call('POST', create_path, {'data': {'type': create_path.strip('/').split('/')[-1], 'attributes': att,
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


def section(txt, name):
    import re
    m = re.search(r'=== ' + re.escape(name) + r'[^\n]*===\n(.*?)(?:\n=== |\Z)', txt, re.S)
    return m.group(1).strip() if m else ''


HE = open(os.path.join(ROOT, 'store', 'listing_he.txt'), encoding='utf8').read()
EN = open(os.path.join(ROOT, 'store', 'listing_en.txt'), encoding='utf8').read()
L = {
    'he': dict(name='מיני פייטר - MINI FIGHTER', subtitle=section(HE, 'כותרת משנה'), promo=section(HE, 'טקסט קידום'),
               keywords=section(HE, 'מילות מפתח'), desc=section(HE, 'תיאור')),
    'en-US': dict(name='Mini Fighter - Brawl Online', subtitle=section(EN, 'Subtitle'), promo=section(EN, 'Promotional Text'),
                  keywords=section(EN, 'Keywords'), desc=section(EN, 'Description')),
}
import re as _re
_EMO = _re.compile('[\U00010000-\U0010FFFF\u2600-\u27BF\uFE0F\u200D]')
for _d in L.values():
    _d['desc'] = _re.sub(r'[ \t]+\n', '\n', _EMO.sub('', _d['desc'])).replace('\n ', '\n').strip()
NOTES = section(EN, 'App Review notes')
SITE, PRIVACY, SUPPORT = 'https://minifighter.co.il', 'https://minifighter.co.il/privacy/', 'https://minifighter.co.il/contact/'

app = call('GET', f'/apps?filter[bundleId]={BUNDLE}')['data']
if not app:
    sys.exit('App not found in App Store Connect')
APP = app[0]['id']
print('app', APP)


@step('content rights')
def _():
    call('PATCH', f'/apps/{APP}', {'data': {'type': 'apps', 'id': APP, 'attributes': {
        'contentRightsDeclaration': 'DOES_NOT_USE_THIRD_PARTY_CONTENT', 'primaryLocale': 'he'}}})


infos = call('GET', f'/apps/{APP}/appInfos')['data']
INFO = next(i for i in infos if i['attributes'].get('appStoreState') not in ('READY_FOR_SALE', 'REPLACED_WITH_NEW_INFO'))['id']


@step('category Games > Action')
def _():
    call('PATCH', f'/appInfos/{INFO}', {'data': {'type': 'appInfos', 'id': INFO, 'relationships': {
        'primaryCategory': {'data': {'type': 'appCategories', 'id': 'GAMES'}},
        'primarySubcategoryOne': {'data': {'type': 'appCategories', 'id': 'GAMES_ACTION'}}}}})


@step('app info texts (name, subtitle, privacy URL)')
def _():
    have = {l['attributes']['locale']: l['id'] for l in call('GET', f'/appInfos/{INFO}/appInfoLocalizations')['data']}
    for loc, d in L.items():
        att = {'name': d['name'], 'subtitle': d['subtitle'][:30], 'privacyPolicyUrl': PRIVACY}
        if loc in have:
            call('PATCH', f'/appInfoLocalizations/{have[loc]}', {'data': {'type': 'appInfoLocalizations', 'id': have[loc], 'attributes': att}})
        else:
            att['locale'] = loc
            call('POST', '/appInfoLocalizations', {'data': {'type': 'appInfoLocalizations', 'attributes': att,
                 'relationships': {'appInfo': {'data': {'type': 'appInfos', 'id': INFO}}}}})
    return ', '.join(L)


@step('age rating (cartoon fighting, ads, 13+)')
def _():
    ar = call('GET', f'/appInfos/{INFO}/ageRatingDeclaration')['data']['id']
    fields = dict(alcoholTobaccoOrDrugUseOrReferences='NONE', contests='NONE', gamblingSimulated='NONE',
                  horrorOrFearThemes='NONE', matureOrSuggestiveThemes='NONE', medicalOrTreatmentInformation='NONE',
                  profanityOrCrudeHumor='NONE', sexualContentGraphicAndNudity='NONE', sexualContentOrNudity='NONE',
                  violenceCartoonOrFantasy='FREQUENT_OR_INTENSE', violenceRealistic='NONE',
                  violenceRealisticProlongedGraphicOrSadistic='NONE', gunsOrOtherWeapons='NONE',
                  gambling=False, unrestrictedWebAccess=False, lootBox=False, messagingAndChat=False,
                  parentalControls=False, ageAssurance=False, userGeneratedContent=False, advertising=True,
                  healthOrWellnessTopics=False, kidsAgeBand=None, ageRatingOverrideV2='THIRTEEN_PLUS')
    bad = []
    for k, v in fields.items():
        try:
            call('PATCH', f'/ageRatingDeclarations/{ar}', {'data': {'type': 'ageRatingDeclarations', 'id': ar, 'attributes': {k: v}}})
        except ApiError as e:
            bad.append(k)
            if len(bad) == 1:
                print('age rating first error:', str(e)[:900])
    return 'not accepted: ' + ', '.join(bad) if bad else 'all fields'


vers = call('GET', f'/apps/{APP}/appStoreVersions?filter[platform]=IOS')['data']
VER = next(v for v in vers if v['attributes']['appStoreState'] in ('PREPARE_FOR_SUBMISSION', 'DEVELOPER_REJECTED', 'REJECTED', 'METADATA_REJECTED'))
VID = VER['id']


@step('version (number, copyright, auto release)')
def _():
    v = open(os.path.join(ROOT, 'version.txt')).read().strip()
    call('PATCH', f'/appStoreVersions/{VID}', {'data': {'type': 'appStoreVersions', 'id': VID, 'attributes': {
        'versionString': v, 'copyright': '2026 Michael Sapir', 'releaseType': 'AFTER_APPROVAL'}}})
    return v


VLOC = {}


@step('store texts (description, keywords, promo, URLs)')
def _():
    have = {l['attributes']['locale']: l['id'] for l in call('GET', f'/appStoreVersions/{VID}/appStoreVersionLocalizations')['data']}
    for loc, d in L.items():
        att = {'description': d['desc'], 'keywords': d['keywords'][:100], 'promotionalText': d['promo'][:170],
               'supportUrl': SUPPORT, 'marketingUrl': SITE}
        if loc in have:
            call('PATCH', f'/appStoreVersionLocalizations/{have[loc]}', {'data': {'type': 'appStoreVersionLocalizations', 'id': have[loc], 'attributes': att}})
            VLOC[loc] = have[loc]
        else:
            att['locale'] = loc
            VLOC[loc] = call('POST', '/appStoreVersionLocalizations', {'data': {'type': 'appStoreVersionLocalizations', 'attributes': att,
                             'relationships': {'appStoreVersion': {'data': {'type': 'appStoreVersions', 'id': VID}}}}})['data']['id']
    return ', '.join(VLOC)


@step('screenshots iPhone 6.9" (8 per language)')
def _():
    shots = sorted(f for f in os.listdir(os.path.join(ROOT, 'store', 'screens')) if f.endswith('.jpg'))
    done = []
    for loc, lid in VLOC.items():
        sets = call('GET', f'/appStoreVersionLocalizations/{lid}/appScreenshotSets')['data']
        s = next((x for x in sets if x['attributes']['screenshotDisplayType'] == 'APP_IPHONE_67'), None)
        if s:
            existing = call('GET', f"/appScreenshotSets/{s['id']}/appScreenshots")['data']
            if len(existing) >= len(shots):
                done.append(loc + ' (already there)'); continue
            for e in existing:
                call('DELETE', f"/appScreenshots/{e['id']}")
            sid = s['id']
        else:
            sid = call('POST', '/appScreenshotSets', {'data': {'type': 'appScreenshotSets', 'attributes': {'screenshotDisplayType': 'APP_IPHONE_67'},
                       'relationships': {'appStoreVersionLocalization': {'data': {'type': 'appStoreVersionLocalizations', 'id': lid}}}}})['data']['id']
        for f in shots:
            upload('/appScreenshots', 'appScreenshotSet', 'appScreenshotSets', sid, os.path.join(ROOT, 'store', 'screens', f))
        done.append(loc)
    return ', '.join(done)


@step('App Review info (no login, notes, contact)')
def _():
    att = {'contactFirstName': 'Michael', 'contactLastName': 'Sapir', 'contactPhone': '+972533384144',
           'contactEmail': 'social@sapirfamily.co.il', 'demoAccountRequired': False, 'notes': NOTES[:4000]}
    try:
        d = call('GET', f'/appStoreVersions/{VID}/appStoreReviewDetail')['data']
    except ApiError:
        d = None
    if d:
        call('PATCH', f"/appStoreReviewDetails/{d['id']}", {'data': {'type': 'appStoreReviewDetails', 'id': d['id'], 'attributes': att}})
    else:
        call('POST', '/appStoreReviewDetails', {'data': {'type': 'appStoreReviewDetails', 'attributes': att,
             'relationships': {'appStoreVersion': {'data': {'type': 'appStoreVersions', 'id': VID}}}}})


@step('price: free')
def _():
    pts = call('GET', f'/apps/{APP}/appPricePoints?filter[territory]=USA&limit=5')['data']
    free = next(p for p in pts if float(p['attributes']['customerPrice']) == 0)
    call('POST', '/appPriceSchedules', {
        'data': {'type': 'appPriceSchedules', 'relationships': {
            'app': {'data': {'type': 'apps', 'id': APP}},
            'baseTerritory': {'data': {'type': 'territories', 'id': 'USA'}},
            'manualPrices': {'data': [{'type': 'appPrices', 'id': '${p0}'}]}}},
        'included': [{'type': 'appPrices', 'id': '${p0}', 'attributes': {'startDate': None},
                      'relationships': {'appPricePoint': {'data': {'type': 'appPricePoints', 'id': free['id']}}}}]})


@step('availability: all countries')
def _():
    try:
        call('GET', f'/apps/{APP}/appAvailabilityV2')
        return 'already set'
    except ApiError:
        pass
    terr = []
    url = '/territories?limit=200'
    while url:
        r = call('GET', url); terr += [t['id'] for t in r['data']]; url = r.get('links', {}).get('next')
    inc = [{'type': 'territoryAvailabilities', 'id': f'${{t{i}}}', 'attributes': {'available': True},
            'relationships': {'territory': {'data': {'type': 'territories', 'id': t}}}} for i, t in enumerate(terr)]
    call('POST', '/v2/appAvailabilities', {'data': {'type': 'appAvailabilities', 'attributes': {'availableInNewTerritories': True},
         'relationships': {'app': {'data': {'type': 'apps', 'id': APP}},
                           'territoryAvailabilities': {'data': [{'type': 'territoryAvailabilities', 'id': x['id']} for x in inc]}}},
         'included': inc})
    return f'{len(terr)} territories'


IAP = {}


@step('in-app purchase premium_all (Full Version)')
def _():
    ex = call('GET', f'/v1/apps/{APP}/inAppPurchasesV2?filter[productId]=premium_all')['data']
    if ex:
        IAP['id'] = ex[0]['id']
    else:
        IAP['id'] = call('POST', '/v2/inAppPurchases', {'data': {'type': 'inAppPurchases', 'attributes': {
            'name': 'Full Version', 'productId': 'premium_all', 'inAppPurchaseType': 'NON_CONSUMABLE',
            'reviewNote': 'Main menu > "⭐ בלי פרסומות" chip (also in Settings). Removes forced ads and unlocks all fighters. Restore button on the same screen.'},
            'relationships': {'app': {'data': {'type': 'apps', 'id': APP}}}}})['data']['id']
    have = {l['attributes']['locale'] for l in call('GET', f"/v2/inAppPurchases/{IAP['id']}/inAppPurchaseLocalizations")['data']}
    for loc, nm, ds in [('he', 'גרסה מלאה', 'בלי פרסומות כפויות, כל הלוחמים פתוחים'), ('en-US', 'Full Version', 'No forced ads, all fighters unlocked')]:
        if loc not in have:
            call('POST', '/inAppPurchaseLocalizations', {'data': {'type': 'inAppPurchaseLocalizations',
                 'attributes': {'locale': loc, 'name': nm, 'description': ds},
                 'relationships': {'inAppPurchaseV2': {'data': {'type': 'inAppPurchases', 'id': IAP['id']}}}}})
    return IAP['id']


@step('in-app purchase price ≈ ₪9.90')
def _():
    if 'id' not in IAP:
        raise ApiError('no IAP')
    pts, url = [], f"/v2/inAppPurchases/{IAP['id']}/pricePoints?filter[territory]=ISR&limit=200"
    while url:
        r = call('GET', url); pts += r['data']; url = r.get('links', {}).get('next')
    best = min(pts, key=lambda p: abs(float(p['attributes']['customerPrice']) - 9.9))
    call('POST', '/inAppPurchasePriceSchedules', {
        'data': {'type': 'inAppPurchasePriceSchedules', 'relationships': {
            'inAppPurchase': {'data': {'type': 'inAppPurchases', 'id': IAP['id']}},
            'baseTerritory': {'data': {'type': 'territories', 'id': 'ISR'}},
            'manualPrices': {'data': [{'type': 'inAppPurchasePrices', 'id': '${p0}'}]}}},
        'included': [{'type': 'inAppPurchasePrices', 'id': '${p0}', 'attributes': {'startDate': None},
                      'relationships': {'inAppPurchasePricePoint': {'data': {'type': 'inAppPurchasePricePoints', 'id': best['id']}}}}]})
    return '₪' + best['attributes']['customerPrice']


@step('in-app purchase availability + review screenshot')
def _():
    if 'id' not in IAP:
        raise ApiError('no IAP')
    out = []
    try:
        terr, url = [], '/territories?limit=200'
        while url:
            r = call('GET', url); terr += [t['id'] for t in r['data']]; url = r.get('links', {}).get('next')
        call('POST', '/inAppPurchaseAvailabilities', {'data': {'type': 'inAppPurchaseAvailabilities',
             'attributes': {'availableInNewTerritories': True}, 'relationships': {
                 'inAppPurchase': {'data': {'type': 'inAppPurchases', 'id': IAP['id']}},
                 'availableTerritories': {'data': [{'type': 'territories', 'id': t} for t in terr]}}}})
        out.append('available')
    except ApiError as e:
        out.append('availability: ' + str(e)[:200])
    try:
        call('GET', f"/v2/inAppPurchases/{IAP['id']}/appStoreReviewScreenshot")['data'] or 1 / 0
        out.append('screenshot already there')
    except Exception:
        upload('/inAppPurchaseAppStoreReviewScreenshots', 'inAppPurchaseV2', 'inAppPurchases', IAP['id'],
               os.path.join(ROOT, 'store', 'iap_review.png'))
        out.append('screenshot uploaded')
    return '; '.join(out)


print('\n===== SUMMARY =====')
for s, n, r in REPORT:
    print(f'[{s}] {n}: {r}')
