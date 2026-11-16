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
        "if(d.pluginId==='AdMob'){(window.__ad=window.__ad||[]).push(d.methodName);if(d.methodName==='showBanner')(window.__adopts=window.__adopts||[]).push(d.options);if(d.methodName==='initialize'){setTimeout(()=>Capacitor.fromNative({callbackId:d.callbackId,pluginId:d.pluginId,methodName:d.methodName,success:true,data:{}}),6000);return;}}"
        "if(d.methodName==='addListener'){(window.__ls=window.__ls||{})[d.pluginId+'.'+d.options.eventName]=d.callbackId;return;}"
        "if(d.pluginId==='AdMob'&&d.methodName==='showBanner'){const c=(window.__ls||{})['AdMob.bannerAdSizeChanged'];if(c)setTimeout(()=>Capacitor.fromNative({callbackId:c,pluginId:'AdMob',methodName:'addListener',success:true,data:{width:320,height:56}}),300);}"
        "setTimeout(()=>Capacitor.fromNative({callbackId:d.callbackId,pluginId:d.pluginId,methodName:d.methodName,success:true,data}),20);}};"
        "window.Capacitor={DEBUG:false,isLoggingEnabled:false,Plugins:{}};\n" % json.dumps(PR)) + NB + "\nwindow.Capacitor.PluginHeaders=" + json.dumps(HEADERS) + ";"

PLACE_JS = """(sab)=>{const o=(window.__adopts||[]).slice(-1)[0];const st=MF2.adsPolicy.state();if(!st.shown||!o)return {shown:false,fit:st.fit};
 const W=innerWidth,H=innerHeight,bw=320,bh=50,left=W/2-bw/2,bottom=H-sab-o.margin,top=bottom-bh;
 const lob=document.querySelector('#v2root .m2-lobby');const f=lob.querySelector('[data-a="fight"]').getBoundingClientRect();
 const m=(lob.querySelector('.m2-bottom .modeb')||lob.querySelector('[data-a="modes"]')).getBoundingClientRect();
 const P=(lob.querySelector('.pband.placed .plate')||{getBoundingClientRect:()=>null}).getBoundingClientRect();
 const L=f.left<m.left?f:m,R=f.left<m.left?m:f;
 const pg=P?Math.max(Math.max(left,P.left)-Math.min(left+bw,P.right),Math.max(top,P.top)-Math.min(bottom,P.bottom)):null;
 return {shown:true,W,H,margin:o.margin,position:o.position,banner:[Math.round(left),Math.round(top),Math.round(left+bw),Math.round(bottom)],
  gapLeft:Math.round(left-L.right),gapRight:Math.round(R.left-(left+bw)),bottomVsSlot:Math.round(bottom-Math.min(f.bottom,m.bottom)),plateGap:pg==null?null:Math.round(pg),fit:st.fit};}"""


def placement(pg):
    """Where AdMob would draw the banner from the margin ads.js sent (BOTTOM_CENTER): Android counts the margin from
    the window bottom (the app is immersive), iPhone from the bottom of the safe area. It must sit in the lobby slot:
    at least 12 px from the fight and mode buttons and from the nameplate card, its bottom on the row's bottom line."""
    good = True
    for plat, sab in (('android', 0), ('ios', 21)):
        for w, h in ((844, 390), (932, 430), (740, 360), (915, 412)):
            pg.set_viewport_size({'width': w, 'height': h})
            pg.evaluate(f"window.MF_IOS={'true' if plat == 'ios' else 'false'};window.__mfSabTest={sab}")
            pg.evaluate("title()"); pg.wait_for_timeout(1500); pg.evaluate("MF2.adsPolicy.apply()"); pg.wait_for_timeout(900)
            r = pg.evaluate(PLACE_JS, sab)
            if not r['shown']:
                print(f'placement {plat} {w}x{h}: no banner (the slot does not fit at this size: fit={r["fit"]})'); continue
            # iPhone: AdMob anchors to the safe area, so a slot whose bottom line is inside the home-indicator band gets
            # the banner's bottom on the safe-area line instead (never in the band); everything else is the same
            want_shift = 0 if plat == 'android' else -max(0, sab - (h - (r['banner'][3] - r['bottomVsSlot'])))
            fine = r['gapLeft'] >= 12 and r['gapRight'] >= 12 and abs(r['bottomVsSlot'] - want_shift) <= 1 and (r['plateGap'] is None or r['plateGap'] >= 12) and r['banner'][1] >= 0 and r['banner'][3] <= h - sab + 1
            good = good and fine
            print(f"placement {plat} {w}x{h}: {'OK ' if fine else 'BAD'} margin {r['margin']} banner {r['banner']} gaps L{r['gapLeft']} R{r['gapRight']} plate {r['plateGap']} bottom vs slot {r['bottomVsSlot']}")
    pg.evaluate("window.MF_IOS=false;window.__mfSabTest=null")
    return good


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
        # AdMob initializes slowly on a phone (consent, tracking prompt): the lobby banner must still come once it is ready
        pg.wait_for_timeout(9000)
        ad = pg.evaluate('window.__ad||[]')
        pol = pg.evaluate('MF2.adsPolicy?MF2.adsPolicy.state():null')
        print('AdMob calls:', ad, '| policy:', pol and {k: pol[k] for k in ('want', 'shown', 'payer')}, '| body.ad-banner:', pg.evaluate("document.body.classList.contains('ad-banner')"))
        if pol is not None:
            ok = ok and pol['want'] and 'showBanner' in ad and 'loadAppOpen' not in ad and 'showAppOpen' not in ad
            ok = ok and ad.index('showBanner') > ad.index('prepareInterstitial')   # only after the shared init (consent first)
        pg.evaluate("MF2UI.go('shop',{tab:'shop'})"); pg.wait_for_timeout(1500)
        ad2 = pg.evaluate('window.__ad||[]')
        print('after opening the shop:', ad2[len(ad):], '| body.ad-banner:', pg.evaluate("document.body.classList.contains('ad-banner')"))
        if pol is not None:
            ok = ok and 'hideBanner' in ad2[len(ad):]
        if SHOTS:
            pg.screenshot(path=os.path.join(SHOTS, 'shop_native.png'))
        if pol is not None:
            ok = placement(pg) and ok
    b.close()
print('missing bundle files:', bad[:10])
print('page errors:', errors[:5])
print('failed requests:', fails[:5])
errors = [e for e in errors if NATIVE or 'not implemented on web' not in e]   # plain web: the App plugin has no web part
ok = ok and not bad and not errors
print('SMOKE', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
