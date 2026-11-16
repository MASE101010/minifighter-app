#!/usr/bin/env bash
# Boot the real app on an Android emulator or an iPhone simulator and read the MFSMOKE status lines the
# --smoke web build logs every 5 s (Capacitor prints console.log to logcat / the system log in debug builds).
# usage: build/smoke_device.sh android <apk> | ios <App.app>
# PASS = the v2 UI reached the lobby (or the first-run naming screen), no failed asset loads, purchases client native.
set -u
PLAT=$1; PKG=$2; OUT=${SMOKE_OUT:-smoke}; mkdir -p "$OUT"; ID=com.sapirproductions.minifighter
if [ "$PLAT" = android ]; then
  adb wait-for-device; adb install -r "$PKG" || exit 1
  adb logcat -c
  adb shell am start -n $ID/.MainActivity
  for i in $(seq 1 24); do sleep 5; adb logcat -d > "$OUT/log.txt"; grep -q 'MFSMOKE {"screen":"\(lobby\|onboard\)"' "$OUT/log.txt" && break; done
  sleep 8; adb logcat -d > "$OUT/log.txt"; adb exec-out screencap -p > "$OUT/android_lobby.png"
  # the real AdMob test banner in the lobby: wait for its view, then compare its place with the slot the page reports
  BRES=2
  for i in $(seq 1 18); do adb shell dumpsys activity top > "$OUT/views.txt"; adb logcat -d > "$OUT/log.txt"
    python3 "$(dirname "$0")/android_banner.py" "$OUT/views.txt" "$OUT/log.txt" > "$OUT/banner.txt"; BRES=$?; [ $BRES -ne 2 ] && break; sleep 5; done
  cat "$OUT/banner.txt"; adb exec-out screencap -p > "$OUT/android_banner.png"
  [ $BRES -eq 1 ] && echo "SMOKE FAIL: banner outside the lobby slot" && exit 1
else
  UDID=$(xcrun simctl list devices available -j | python3 -c "import json,sys;d=json.load(sys.stdin)['devices'];print(next(x['udid'] for k,v in d.items() if 'iOS' in k for x in v if 'iPhone' in x['name']))")
  xcrun simctl boot "$UDID"; xcrun simctl bootstatus "$UDID" -b
  xcrun simctl install "$UDID" "$PKG" || exit 1
  # skip the tracking prompt so it does not cover the screenshot (the real prompt is tested on TestFlight)
  xcrun simctl privacy "$UDID" grant all $ID 2>/dev/null || true
  # Capacitor prints console.log to the app's stdout (Swift.print): attach it with --console-pty
  (xcrun simctl launch --console-pty "$UDID" $ID > "$OUT/log.txt" 2>&1 &)
  for i in $(seq 1 30); do sleep 5; grep -q 'MFSMOKE {"screen":"\(lobby\|onboard\)"' "$OUT/log.txt" && break; done
  sleep 8; xcrun simctl io "$UDID" screenshot "$OUT/ios_lobby.png"
fi
grep -o 'MFSMOKE .*' "$OUT/log.txt" | tail -3
LAST=$(grep -o 'MFSMOKE {.*' "$OUT/log.txt" | tail -1)
python3 - "$LAST" <<'PY'
import json, sys
raw = sys.argv[1][len('MFSMOKE '):] if sys.argv[1] else ''
try:
    d = json.loads(raw)
except Exception:
    print('SMOKE FAIL: no status line from the app'); sys.exit(1)
ok = d.get('screen') in ('lobby', 'onboard') and d.get('native') and not any(e.startswith('load ') for e in d.get('errors', []))
print('platform', d.get('platform'), '| screen', d.get('screen'), '| purchases native', d.get('native'), '| billing ready', d.get('iapReady'),
      '| products listed by the store', d.get('listed'), 'of', d.get('products'), '| web-mode items', d.get('web'), '| errors', d.get('errors'))
print('SMOKE', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
PY
