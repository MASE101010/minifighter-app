"""Create or update every Mini Fighter 2.0 in-app purchase in App Store Connect (safe to run again).
Source: store/iap_products.json (made by build/iap_catalog.py from the game's docs/STORE_PRODUCTS.md).
Per product: type, reference name, product id, review note, family sharing off for consumables, Hebrew + English
localizations, price (Apple price point closest to the ILS price, base territory Israel, other territories
equalized by Apple), availability in all territories, review screenshot. Nothing is submitted for review:
first-time purchases go to review together with the 2.0 app version (the owner / coordinator does that).
premium_all is not touched. Optional: the age rating answers for 2.0 (loot boxes), only when an editable
app info exists (a new version in Prepare for Submission)."""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asc_api import ApiError, ROOT, all_pages, app_id, call, catalog, upload

ONLY = [x for x in os.environ.get('IAP_ONLY', '').replace(',', ' ').split() if x]
DO_AGE = os.environ.get('IAP_AGE_RATING', 'true').lower() == 'true'
REPORT = []

GATE = ('Every real-money purchase first shows a parent gate ("אישור הורים"): a multiplication written in Hebrew words '
        '(for example "כמה זה שבע כפול שמונה?" = what is seven times eight), answered as a number (56). One correct answer '
        'allows one purchase; three wrong answers lock it for a minute. Restore: Shop > "שחזור רכישות" (Restore Purchases), no gate.')
WHERE = {
    'gems': 'Lobby > "חנות" (Shop) > section "יהלומים" (Gems). Consumable: gives gems, can be bought again.',
    'offers': 'Lobby > "חנות" (Shop) > section "מבצעים" (Offers), first card "מבצע פתיחה", shown until bought. Non-consumable.',
    'bundles': 'Lobby > "חנות" (Shop) > section "מבצעים" (Offers), shown while the player owns none of its fighters. Non-consumable.',
    'fighters': 'Lobby > "חנות" (Shop) > section "לוחמים" (Fighters): the cards with a shekel price at the end of the section (the cards before them cost in-game gems). Non-consumable, unlocks that fighter forever.',
    'skins': 'Lobby > "חנות" (Shop) > section "סקינים" (Skins) > tap a skin card: the sheet has a gem button and a shekel button (the real-money purchase). Non-consumable, changes only how a fighter looks.',
    'pass': 'Lobby > "כרטיס עונה" (Season Pass) > premium button. Non-renewing: unlocks the premium reward track of the current 28-day season; it can be bought again for the next season and is restorable.',
}
NOTE_END = ' Nothing random is sold for money: chests are bought only with in-game coins or gems, and their odds are shown in the game and at https://minifighter.co.il/odds/'


def step(name, fn):
    try:
        r = fn(); REPORT.append(('OK', name, r or '')); return r
    except Exception as e:
        REPORT.append(('FAIL', name, str(e)[:900])); traceback.print_exc(); return None


APP = app_id()
print('app', APP)
TERR = None


def territories():
    global TERR
    if TERR is None:
        TERR = [t['id'] for t in all_pages('/territories?limit=200')]
    return TERR


def existing():
    out = {}
    for i in all_pages(f'/v1/apps/{APP}/inAppPurchasesV2?limit=200'):
        out[i['attributes']['productId']] = i
    return out


HAVE = existing()


def screenshot_for(p):
    for name in (p['id'] + '.png', p['section'] + '.png'):
        f = os.path.join(ROOT, 'store', 'iap_review', name)
        if os.path.exists(f):
            return f
    return os.path.join(ROOT, 'store', 'iap_review.png')


def ensure(p):
    pid, out = p['id'], []
    note = (WHERE[p['section']] + ' ' + GATE + NOTE_END)[:4000]
    cur = HAVE.get(pid)
    if cur:
        iid = cur['id']; a = cur['attributes']
        if a.get('inAppPurchaseType') != p['appleType']:
            out.append(f"TYPE MISMATCH: store has {a.get('inAppPurchaseType')}, doc wants {p['appleType']} (Apple cannot change a type; delete it in App Store Connect and run again)")
        att = {'name': p['reference'], 'reviewNote': note}
        if p['appleType'] == 'CONSUMABLE' and a.get('familySharable'):
            att['familySharable'] = False
        if a.get('name') != att['name'] or a.get('reviewNote') != note or 'familySharable' in att:
            call('PATCH', f'/v2/inAppPurchases/{iid}', {'data': {'type': 'inAppPurchases', 'id': iid, 'attributes': att}})
            out.append('updated')
        else:
            out.append('exists')
    else:
        att = {'name': p['reference'], 'productId': pid, 'inAppPurchaseType': p['appleType'], 'reviewNote': note}
        if p['appleType'] == 'CONSUMABLE':
            att['familySharable'] = False
        iid = call('POST', '/v2/inAppPurchases', {'data': {'type': 'inAppPurchases', 'attributes': att,
                   'relationships': {'app': {'data': {'type': 'apps', 'id': APP}}}}})['data']['id']
        out.append('created')
    # localizations
    locs = {l['attributes']['locale']: l for l in call('GET', f'/v2/inAppPurchases/{iid}/inAppPurchaseLocalizations?limit=50')['data']}
    for loc, key in (('he', 'he'), ('en-US', 'en')):
        nm, ds = p[key]['name'], p[key]['apple']
        if loc in locs:
            la = locs[loc]['attributes']
            if la.get('name') != nm or la.get('description') != ds:
                call('PATCH', f"/inAppPurchaseLocalizations/{locs[loc]['id']}", {'data': {'type': 'inAppPurchaseLocalizations',
                     'id': locs[loc]['id'], 'attributes': {'name': nm, 'description': ds}}})
                out.append(loc + ' text updated')
        else:
            call('POST', '/inAppPurchaseLocalizations', {'data': {'type': 'inAppPurchaseLocalizations',
                 'attributes': {'locale': loc, 'name': nm, 'description': ds},
                 'relationships': {'inAppPurchaseV2': {'data': {'type': 'inAppPurchases', 'id': iid}}}}})
            out.append(loc + ' text added')
    # price: nearest Israeli price point
    pts = all_pages(f'/v2/inAppPurchases/{iid}/pricePoints?filter[territory]=ISR&limit=200')
    if not pts:
        raise ApiError('no ISR price points returned (Paid Apps agreement not active?)')
    best = min(pts, key=lambda x: abs(float(x['attributes']['customerPrice']) - p['ils']))
    now = None
    try:
        mp = call('GET', f'/v1/inAppPurchasePriceSchedules/{iid}/manualPrices?filter[territory]=ISR&include=inAppPurchasePricePoint&limit=10', ok404=True)
        if mp:
            for inc in mp.get('included', []):
                if inc['type'] == 'inAppPurchasePricePoints':
                    now = inc['attributes'].get('customerPrice')
    except ApiError:
        now = None
    if now is not None and abs(float(now) - float(best['attributes']['customerPrice'])) < 0.001:
        out.append('price ₪' + now)
    else:
        call('POST', '/inAppPurchasePriceSchedules', {
            'data': {'type': 'inAppPurchasePriceSchedules', 'relationships': {
                'inAppPurchase': {'data': {'type': 'inAppPurchases', 'id': iid}},
                'baseTerritory': {'data': {'type': 'territories', 'id': 'ISR'}},
                'manualPrices': {'data': [{'type': 'inAppPurchasePrices', 'id': '${p0}'}]}}},
            'included': [{'type': 'inAppPurchasePrices', 'id': '${p0}', 'attributes': {'startDate': None},
                          'relationships': {'inAppPurchasePricePoint': {'data': {'type': 'inAppPurchasePricePoints', 'id': best['id']}}}}]})
        out.append('price set ₪' + best['attributes']['customerPrice'] + (f' (was ₪{now})' if now else ''))
    # availability
    av = call('GET', f'/v2/inAppPurchases/{iid}/inAppPurchaseAvailability', ok404=True)
    if av and av.get('data'):
        out.append('available')
    else:
        call('POST', '/inAppPurchaseAvailabilities', {'data': {'type': 'inAppPurchaseAvailabilities',
             'attributes': {'availableInNewTerritories': True}, 'relationships': {
                 'inAppPurchase': {'data': {'type': 'inAppPurchases', 'id': iid}},
                 'availableTerritories': {'data': [{'type': 'territories', 'id': t} for t in territories()]}}}})
        out.append(f'availability set ({len(territories())} territories)')
    # review screenshot
    sh = call('GET', f'/v2/inAppPurchases/{iid}/appStoreReviewScreenshot', ok404=True)
    sd = sh and sh.get('data')
    state = sd and ((sd['attributes'].get('assetDeliveryState') or {}).get('state'))
    if sd and state not in ('FAILED',):
        out.append('screenshot ok')
    else:
        if sd:
            call('DELETE', f"/inAppPurchaseAppStoreReviewScreenshots/{sd['id']}")
        f = screenshot_for(p)
        upload('/inAppPurchaseAppStoreReviewScreenshots', 'inAppPurchaseV2', 'inAppPurchases', iid, f)
        out.append('screenshot uploaded (' + os.path.relpath(f, ROOT) + ')')
    return '; '.join(out)


for p in catalog():
    if ONLY and p['id'] not in ONLY:
        continue
    step(f"{p['id']} ({p['appleType']}, ₪{p['ils']:.2f})", lambda p=p: ensure(p))


def age_rating():
    infos = call('GET', f'/apps/{APP}/appInfos')['data']
    ed = [i for i in infos if (i['attributes'].get('appStoreState') or i['attributes'].get('state')) not in
          ('READY_FOR_SALE', 'READY_FOR_DISTRIBUTION', 'REPLACED_WITH_NEW_INFO', 'WAITING_FOR_REVIEW', 'IN_REVIEW')]
    if not ed:
        return 'SKIPPED: no editable app info yet (it opens when the 2.0 version is created). Run this workflow again after that.'
    ar = call('GET', f"/appInfos/{ed[0]['id']}/ageRatingDeclaration")['data']
    # 2.0: random reward chests bought with in-game currency that can be bought with money = loot boxes (declared).
    # No gambling, no messaging (emotes only), ads as before.
    fields = {'lootBox': True, 'gambling': False, 'gamblingSimulated': 'NONE', 'messagingAndChat': False, 'advertising': True}
    dropped = []
    import re
    for _ in range(6):
        try:
            call('PATCH', f"/ageRatingDeclarations/{ar['id']}", {'data': {'type': 'ageRatingDeclarations', 'id': ar['id'], 'attributes': fields}})
            return 'saved ' + ', '.join(f'{k}={v}' for k, v in fields.items()) + (' (API has no: ' + ', '.join(dropped) + ')' if dropped else '')
        except ApiError as e:
            ptrs = [x for x in re.findall(r'/data/attributes/(\w+)', str(e)) if x in fields]
            if not ptrs:
                raise
            for x in ptrs:
                fields.pop(x); dropped.append(x)
    raise ApiError('age rating: too many retries')


def retire_premium():
    """premium_all: remove from sale in every territory (owner decision for 2.0). Buyers keep it: StoreKit keeps the
    transaction in Transaction.currentEntitlements / Transaction.all, which the plugin's getPurchases reads, and
    restorePurchases (AppStore.sync) still returns it. Run ONLY after 2.0 is live: 1.0.13 still sells it."""
    i = HAVE.get('premium_all')
    if not i:
        return 'premium_all not found'
    call('POST', '/inAppPurchaseAvailabilities', {'data': {'type': 'inAppPurchaseAvailabilities',
         'attributes': {'availableInNewTerritories': False}, 'relationships': {
             'inAppPurchase': {'data': {'type': 'inAppPurchases', 'id': i['id']}},
             'availableTerritories': {'data': []}}}})
    return 'premium_all removed from sale in all territories (not deleted; restore keeps working)'


if os.environ.get('IAP_RETIRE_PREMIUM', 'false').lower() == 'true':
    step('retire premium_all (remove from sale)', retire_premium)

if DO_AGE and not ONLY:
    step('age rating 2.0 (loot boxes yes, gambling no, chat no)', age_rating)

print('\n===== SUMMARY =====')
for s, n, r in REPORT:
    print(f'[{s}] {n}: {r}')
fails = [r for r in REPORT if r[0] == 'FAIL']
print(f'{len(REPORT) - len(fails)} ok, {len(fails)} failed')
sys.exit(1 if fails else 0)
