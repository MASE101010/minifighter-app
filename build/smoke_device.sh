#!/usr/bin/env bash
# Boot the real app on an Android emulator or an iPhone simulator and read the MFSMOKE status lines the
# --smoke web build logs every 5 s (Capacitor prints console.log to logcat / the system log in debug builds).
# usage: build/smoke_device.sh android <apk> | ios <App.app>
# PASS = the v2 UI reached the lobby (or the first-run naming screen), no failed asset loads, purchases client native.
set -u
PLAT=$1; PKG=$2; OUT=${SMOKE_OUT:-smoke}; mkdir -p "$OUT"; ID=com.sapirproductions.minifighter
if [ "$PLAT" = android ]; then
  adb wait-for-device; adb install -r "$PKG" || exit 1
  adb shell pm grant $ID android.permission.POST_NOTIFICATIONS 2>/dev/null || true
  adb logcat -c
  adb shell am start -n $ID/.MainActivity
  for i in $(seq 1 24); do sleep 5; adb logcat -d > "$OUT/log.txt"; grep -q 'MFSMOKE {.*"screen":"\(lobby\|onboard\)"' "$OUT/log.txt" && break; done
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
  for i in $(seq 1 30); do sleep 5; grep -q 'MFSMOKE {.*"screen":"\(lobby\|onboard\)"' "$OUT/log.txt" && break; done
  sleep 8; xcrun simctl io "$UDID" screenshot "$OUT/ios_lobby.png"
fi
# the limited-time event on the device (builds made with --smoke-event): wait for the app's own event pass
if [ "${SMOKE_EVENT:-}" = 1 ]; then
  rd() { if [ "$PLAT" = android ]; then adb logcat -d > "$OUT/log.txt"; fi; }
  shot() { if [ "$PLAT" = android ]; then adb exec-out screencap -p > "$OUT/${PLAT}_$1.png"; else xcrun simctl io "$UDID" screenshot "$OUT/${PLAT}_$1.png"; fi; }
  for i in $(seq 1 50); do sleep 5; rd; grep -q 'MFSMOKE {.*"ev":{"step":[129]' "$OUT/log.txt" && break; done
  sleep 3; shot event_sheet
  if [ "$PLAT" = android ]; then sleep 14; adb shell dumpsys notification --noredact > "$OUT/notifications.txt" 2>/dev/null
    grep -c "smoke test notification" "$OUT/notifications.txt" | sed 's/^/EVENT test notification posted by Android (lines): /'
    adb shell cmd statusbar expand-notifications; sleep 2; shot notification; adb shell cmd statusbar collapse; fi
  for i in $(seq 1 40); do sleep 5; rd; grep -q 'MFSMOKE {.*"ev":{"step":[29]' "$OUT/log.txt" && break; done
  sleep 2; shot event_arena; rd
  python3 - "$(grep -o 'MFSMOKE {.*' "$OUT/log.txt" | tail -1)" <<'PY' || EVFAIL=1
import json, sys
try: e = json.loads(sys.argv[1][len('MFSMOKE '):]).get('ev') or {}
except Exception: e = {}
print('EVENT', json.dumps(e, ensure_ascii=False))
need = dict(day=3, chests=3, button=True, news=True, claim=True, claimedNow=True, plugin=True, sheet=True, match=True)
bad = {k: e.get(k) for k, v in need.items() if e.get(k) != v}
if e.get('step') != 2 or bad or not (e.get('deco') or e.get('lite')): print('EVENT FAIL', bad, e.get('error')); sys.exit(1)
print('EVENT PASS')
PY
fi
grep -o 'MFSMOKE .*' "$OUT/log.txt" | tail -3
LAST=$(grep -o 'MFSMOKE {.*' "$OUT/log.txt" | tail -1)
if [ -z "$LAST" ]; then echo "--- no status line; diagnostics ---"
  if [ "$PLAT" = android ]; then echo "app pid: $(adb shell pidof $ID)"; adb shell dumpsys activity activities | grep -m3 -E "topResumedActivity|mResumedActivity"
    grep -E "Capacitor|AndroidRuntime|chromium|FATAL|MFSMOKE|AdMob|Ads" "$OUT/log.txt" | tail -40 | cut -c1-300
  else tail -40 "$OUT/log.txt" | cut -c1-300; fi; fi
python3 - "$LAST" <<'PY'
import json, sys
raw = sys.argv[1][len('MFSMOKE '):] if sys.argv[1] else ''
try:
    d = json.loads(raw)
except Exception:
    print('SMOKE FAIL: no status line from the app'); sys.exit(1)
ok = d.get('screen') in ('lobby', 'onboard') and d.get('native') and not any(e.startswith('load ') for e in d.get('errors', []))
print('audio:', d.get('audio'), '(context state after the game\'s own unlock, no real tap; native = MFAudio.setPlayback answer)')
print('platform', d.get('platform'), '| screen', d.get('screen'), '| purchases native', d.get('native'), '| billing ready', d.get('iapReady'),
      '| products listed by the store', d.get('listed'), 'of', d.get('products'), '| web-mode items', d.get('web'), '| errors', d.get('errors'))
print('SMOKE', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
PY
RC=$?; [ "${EVFAIL:-0}" = 1 ] && exit 1; exit $RC
