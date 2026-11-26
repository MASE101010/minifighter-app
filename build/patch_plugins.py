"""Small fixes to native plugin code, applied after every npm install (package.json postinstall).
1. AdMob banner (Android): hideBanner read the shared mAdView inside a task posted to the UI thread; a remove or a failed
   load can null it first -> NullPointerException that closes the app (Play vitals, 2.0.0:
   BannerExecutor.lambda$hideBanner$1). The task now works on the view it was given and always answers the call.
The script stops the build if the code it expects is not there (a plugin update: look again)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, 'node_modules', '@capacitor-community', 'admob', 'android', 'src', 'main', 'java', 'com', 'getcapacitor',
                 'community', 'admob', 'banner', 'BannerExecutor.java')
if not os.path.exists(p):
    print('patch_plugins: AdMob plugin not installed, nothing to do'); sys.exit(0)
s = open(p, encoding='utf8').read()
MARK = '/* mf-patch hideBanner */'
if MARK not in s:
    old = '''                .runOnUiThread(() -> {
                    if (mAdViewLayout != null) {
                        mAdViewLayout.setVisibility(View.GONE);
                        mAdView.pause();
'''
    new = '''                .runOnUiThread(() -> { ''' + MARK + '''
                    final AdView hideView = mAdView;
                    if (mAdViewLayout == null || hideView == null) {
                        call.resolve();
                        return;
                    }
                    if (mAdViewLayout != null) {
                        mAdViewLayout.setVisibility(View.GONE);
                        hideView.pause();
'''
    if s.count(old) != 1:
        sys.exit('patch_plugins: BannerExecutor.hideBanner does not look as expected, the AdMob plugin changed')
    open(p, 'w', encoding='utf8').write(s.replace(old, new))
    print('patch_plugins: AdMob hideBanner patched')
else:
    print('patch_plugins: AdMob hideBanner already patched')
