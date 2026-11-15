"""Print every in-app purchase of Mini Fighter in App Store Connect: product id, type, Israeli price, state,
localizations, screenshot. Read only."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asc_api import all_pages, app_id, call, catalog

APP = app_id()
want = {p['id']: p for p in catalog()}
have = {i['attributes']['productId']: i for i in all_pages(f'/v1/apps/{APP}/inAppPurchasesV2?limit=200')}
print(f"{'product id':22} {'type':26} {'ILS':>7} {'state':22} locales  shot")
for pid in list(want) + [x for x in have if x not in want]:
    i = have.get(pid)
    if not i:
        print(f'{pid:22} MISSING'); continue
    a, iid = i['attributes'], i['id']
    price = '-'
    try:
        mp = call('GET', f'/v1/inAppPurchasePriceSchedules/{iid}/manualPrices?filter[territory]=ISR&include=inAppPurchasePricePoint&limit=10', ok404=True)
        for inc in (mp or {}).get('included', []):
            if inc['type'] == 'inAppPurchasePricePoints':
                price = inc['attributes']['customerPrice']
    except Exception:
        price = '?'
    locs = ','.join(sorted(l['attributes']['locale'] for l in call('GET', f'/v2/inAppPurchases/{iid}/inAppPurchaseLocalizations')['data']))
    sh = call('GET', f'/v2/inAppPurchases/{iid}/appStoreReviewScreenshot', ok404=True)
    shot = ((sh or {}).get('data') or {}).get('attributes', {}).get('assetDeliveryState', {}) or {}
    print(f"IAP {pid:22} {a.get('inAppPurchaseType', ''):26} {price:>7} {a.get('state', ''):22} {locs:9} {shot.get('state', 'none')} {'; '.join(e.get('description', e.get('code', '')) for e in (shot.get('errors') or []))[:200]}")
