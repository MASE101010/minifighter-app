"""iPhone project settings (run after `npx cap sync ios`, safe to run again).
AdMob app ID + SKAdNetwork list, tracking prompt text, landscape only, iPhone only,
no encryption export questions, app icon without transparency."""
import json, os, plistlib, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IOS = os.path.join(ROOT, 'ios', 'App')
PL = os.path.join(IOS, 'App', 'Info.plist')
PBX = os.path.join(IOS, 'App.xcodeproj', 'project.pbxproj')
cfg = json.load(open(os.path.join(ROOT, 'build', 'ios_ads.json')))
TEST_APP = 'ca-app-pub-3940256099942544~1458002511'
app_id = cfg.get('app') or TEST_APP

p = plistlib.load(open(PL, 'rb'))
p['CFBundleDisplayName'] = 'מיני פייטר'
p['CFBundleDevelopmentRegion'] = 'he'
p['GADApplicationIdentifier'] = app_id
ids = open(os.path.join(ROOT, 'build', 'skadnetwork_ids.txt')).read().split()
p['SKAdNetworkItems'] = [{'SKAdNetworkIdentifier': i + '.skadnetwork'} for i in ids]
p['NSUserTrackingUsageDescription'] = ('המידע משמש להצגת פרסומות שמתאימות לך יותר. '
                                       'המשחק ממומן מפרסומות ונשאר חינמי בזכותן.')
p['ITSAppUsesNonExemptEncryption'] = False
land = ['UIInterfaceOrientationLandscapeRight', 'UIInterfaceOrientationLandscapeLeft']
p['UISupportedInterfaceOrientations'] = land
p['UISupportedInterfaceOrientations~ipad'] = land
p['UIRequiresFullScreen'] = True
p['UIStatusBarHidden'] = True
p['UIViewControllerBasedStatusBarAppearance'] = False
p['UIRequiredDeviceCapabilities'] = ['arm64']
p['GADDelayAppMeasurementInit'] = True
plistlib.dump(p, open(PL, 'wb'))

s = open(PBX, encoding='utf8').read()
s = s.replace('TARGETED_DEVICE_FAMILY = "1,2";', 'TARGETED_DEVICE_FAMILY = 1;')
s = re.sub(r'IPHONEOS_DEPLOYMENT_TARGET = [\d.]+;', 'IPHONEOS_DEPLOYMENT_TARGET = 15.0;', s)
open(PBX, 'w', encoding='utf8').write(s)

# App icon: 1024x1024, no alpha (App Store rejects transparent icons)
from PIL import Image
src = os.path.join(ROOT, 'build', 'icon_1024.png')
if os.path.exists(src):
    im = Image.open(src).convert('RGBA').resize((1024, 1024), Image.LANCZOS)
    bg = Image.new('RGB', im.size, (11, 22, 80)); bg.paste(im, mask=im.split()[3])
    bg.save(os.path.join(IOS, 'App', 'Assets.xcassets', 'AppIcon.appiconset', 'AppIcon-512@2x.png'))
# Launch screen: game background colour
for f in os.listdir(os.path.join(IOS, 'App', 'Assets.xcassets', 'Splash.imageset')):
    if f.endswith('.png'):
        Image.new('RGB', (2732, 2732), (11, 22, 80)).save(
            os.path.join(IOS, 'App', 'Assets.xcassets', 'Splash.imageset', f))
print('iOS ready | AdMob:', 'LIVE ' + app_id if cfg.get('app') else 'TEST (fill build/ios_ads.json)')
