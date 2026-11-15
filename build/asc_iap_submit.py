"""Send every catalog in-app purchase that is READY_TO_SUBMIT to App Review on its own (inAppPurchaseSubmissions) and
print Apple's full answer. Used when some could not go with the version submission."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asc_api import ApiError, all_pages, app_id, call, catalog
APP = app_id(); want = {p['id'] for p in catalog()}
for i in all_pages(f'/v1/apps/{APP}/inAppPurchasesV2?limit=200'):
    a = i['attributes']
    if a['productId'] not in want or a.get('state') != 'READY_TO_SUBMIT':
        continue
    try:
        call('POST', '/inAppPurchaseSubmissions', {'data': {'type': 'inAppPurchaseSubmissions', 'relationships': {
            'inAppPurchaseV2': {'data': {'type': 'inAppPurchases', 'id': i['id']}}}}})
        print('SENT', a['productId'])
    except ApiError as e:
        txt = str(e); j = txt[txt.find('{'):]
        try:
            for er in json.loads(j)['errors']:
                print('REJECTED', a['productId'], er.get('code'), '|', er.get('detail'))
        except Exception:
            print('REJECTED', a['productId'], txt[:1500])
