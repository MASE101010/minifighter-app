"""Smoke test of www/ in headless Chromium, served the way the Android app serves it (https://localhost/, every file
from www/, nothing else reachable except the game's own servers), optionally with a simulated native store.
    python3 build/smoke_www.py [--native] [--shots DIR]
Checks: no request for a missing bundle file, no page errors, the v2 UI boots to the lobby (or the first-run naming
screen), and with --native the purchases client lists every catalog product with its store price (mocked
NativePurchases plugin answering like the real one)."""
import json, mimetypes, os, sys
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(ROOT, 'www')
NATIVE = '--native' in sys.argv
SHOTS = sys.argv[sys.argv.index('--shots') + 1] if '--shots' in sys.argv else None
CAT = json.load(open(os.path.join(ROOT, 'store', 'iap_products.json'), encoding='utf8'))['products']
PR = {p['id']: '₪' + f"{p['ils']:.2f}" for p in CAT}
NB = open(os.path.join(ROOT, 'node_modules', '@capacitor', 'android', 'capacitor', 'src', 'main', 'assets', 'native-bridge.js'), encoding='utf8').read()
METHODS = {
    'NativePurchases': ['isBillingSupported', 'getProducts', 'getPurchases', 'restorePurchases', 'purchaseProduct', 'acknowledgePurchase', 'consumePurchase'],
    'AdMob': ['initialize', 'requestConsentInfo', 'showConsentForm', 'requestTrackingAuthorization', 'trackingAuthorizationStatus', 'showBanner',
              'hideBanner', 'resumeBanner', 'removeBanner', 'prepareInterstitial', 'showInterstitial', 'prepareRewardVideoAd', 'showRewardVideoAd',
              'prepareRewardInterstitialAd', 'showRewardInterstitialAd', 'loadAppOpen', 'showAppOpen', 'setApplicationMuted', 'setApplicationVolume'],
    'App': ['exitApp', 'getInfo', 'getState', 'minimizeApp'],
    'Share': ['share', 'canShare']}
HEADERS = [{'name': n, 'methods': [{'name': m, 'rtype': 'promise'} for m in ms] + [{'name': 'addListener', 'rtype': 'callback'},
           {'name': 'removeListener'}, {'name': 'removeAllListeners', 'rtype': 'promise'}]} for n, ms in METHODS.items()]
# The page is given what Capacitor's Android WebView injects before any page script: the global, native-bridge.js and
# the plugin headers. Calls go to androidBridge.postMessage and are answered through Capacitor.fromNative, exactly as
# the native side does; the store answers like Google Play would for products that exist.
MOCK = ("window.__np=[];window.androidBridge={postMessage(m){const d=JSON.parse(m);const PR=%s;let data={};"
        "if(d.pluginId==='NativePurchases'){window.__np.push(d.methodName);"
        " if(d.methodName==='isBillingSupported')data={isBillingSupported:true};"
        " if(d.methodName==='getProducts')data={products:(d.options.productIdentifiers||[]).filter(i=>PR[i]).map(i=>({identifier:i,priceString:PR[i],title:i}))};"
        " if(d.methodName==='getPurchases')data={purchases:[]};"
        " if(d.methodName==='purchaseProduct'){setTimeout(()=>Capacitor.fromNative({callbackId:d.callbackId,pluginId:d.pluginId,methodName:d.methodName,success:false,error:{message:'User cancelled'}}),50);return;}}"
        "if(d.methodName==='addListener')return;"
        "setTimeout(()=>Capacitor.fromNative({callbackId:d.callbackId,pluginId:d.pluginId,methodName:d.methodName,success:true,data}),20);}};"
        "window.Capacitor={DEBUG:false,isLoggingEnabled:false,Plugins:{}};\n" % json.dumps(PR)) + NB + "\nwindow.Capacitor.PluginHeaders=" + json.dumps(HEADERS) + ";"

bad, errors, fails = [], [], []
with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2, locale='he-IL')

    def route(r):
        u = r.request.url
        if u.startswith('https://localhost/'):
            path = u[len('https://localhost/'):].split('?')[0].split('#')[0] or 'index.html'
            f = os.path.join(W, path)
            if os.path.isfile(f):
                return r.fulfill(path=f, content_type=mimetypes.guess_type(f)[0] or 'application/octet-stream')
            bad.append(path); return r.fulfill(status=404, body='')
        return r.continue_()
    ctx.route('**/*', route)
    if NATIVE:
        ctx.add_init_script(MOCK)
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errors.append(str(e)[:300]))
    pg.on('requestfailed', lambda r: fails.append(r.url[:120]) if r.url.startswith('https://localhost/') else None)
    pg.goto('https://localhost/', wait_until='load', timeout=120000)
    pg.wait_for_function('window.MF2&&window.MF2UI&&MF2UI.state&&MF2UI.state()', timeout=90000)
    pg.wait_for_timeout(6000)
    st = pg.evaluate('MF2UI.state().name')
    print('v2 screen:', st)
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True); pg.screenshot(path=os.path.join(SHOTS, 'boot.png'))
    ok = st in ('lobby', 'onboard')
    if NATIVE:
        pg.wait_for_function('MF2.iap&&MF2.iap.ready', timeout=30000)
        prods = pg.evaluate('MF2.iap.products()')
        listed = [p for p in prods if p['listed']]
        print('plugin calls:', pg.evaluate('window.__np'))
        print('native:', pg.evaluate('MF2.iap.native'), '| listed', len(listed), 'of', len(prods))
        webish = pg.evaluate("MF2.shop().filter(i=>i.kind==='real'&&(i.reason==='web'||i.reason==='test')).map(i=>i.id)")
        print('items still in web mode:', webish)
        price_ok = all(p['price'] == PR[p['id']] for p in listed if p['id'] in PR)
        ok = ok and len([p for p in listed if p['id'] in PR]) == len(PR) and not webish and price_ok
        pg.evaluate("MF2UI.go('shop',{tab:'shop'})"); pg.wait_for_timeout(1500)
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, 'shop_native.png'))
    b.close()
print('missing bundle files:', bad[:10])
print('page errors:', errors[:5])
print('failed requests:', fails[:5])
errors = [e for e in errors if NATIVE or 'not implemented on web' not in e]   # plain web: the App plugin has no web part
ok = ok and not bad and not errors
print('SMOKE', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
