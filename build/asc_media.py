"""Replace the App Store screenshots and app previews of one version with the 2.0 store media (safe to run again).
Source: store/media_v2/manifest.json (made by store/media_v2/tools/manifest.py; lists every file with size, md5,
pixel size and, for the videos, duration). The same Hebrew media goes to every localization in TARGETS (default: all
localizations of the version, today he and en-US).

For each localization and each display type (APP_IPHONE_67 = 6.9", APP_IPHONE_65 = 6.5"):
  screenshots: delete the existing ones, reserve, upload the parts, commit with the md5 checksum, set the order,
               wait until Apple finished processing (assetDeliveryState COMPLETE; FAILED stops the run);
  previews:    the same for the preview set (IPHONE_67 / IPHONE_65), then the poster frame (previewFrameTimeCode)
               is set once the video is processed, and read back.
Stops with a clear message, before changing anything, when the version does not exist or is not editable.

Environment: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8 (as the other asc_* scripts), VERSION (default 2.0.0),
LOCALE (media language folder key in the manifest, default he), TARGETS (all | comma separated locales),
WHAT (all | screenshots | previews), DRY_RUN (default true: only reads from Apple and prints the plan)."""
import hashlib, json, os, sys, time
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asc_api import call, all_pages, app_id, ApiError, ROOT

MEDIA = os.path.join(ROOT, 'store', 'media_v2')
VERSION = os.environ.get('VERSION', '').strip() or '2.0.0'
LOCALE = os.environ.get('LOCALE', '').strip() or 'he'
TARGETS = os.environ.get('TARGETS', '').strip() or 'all'
WHAT = os.environ.get('WHAT', '').strip() or 'all'
DRY = os.environ.get('DRY_RUN', 'true').strip().lower() not in ('false', '0', 'no')
EDITABLE = {'PREPARE_FOR_SUBMISSION', 'DEVELOPER_REJECTED', 'REJECTED', 'METADATA_REJECTED', 'INVALID_BINARY'}
# manifest set -> App Store Connect display type
SHOT_SETS = {'appstore_iphone69': 'APP_IPHONE_67', 'appstore_iphone65': 'APP_IPHONE_65'}
PREVIEW_SETS = {'appstore_iphone69': 'IPHONE_67', 'appstore_iphone65': 'IPHONE_65'}
SHOT_SIZES = {'APP_IPHONE_67': {(2868, 1320), (2796, 1290), (2736, 1260)}, 'APP_IPHONE_65': {(2778, 1284), (2688, 1242)}}
POLL_S, WAIT_SHOT_S, WAIT_VIDEO_S = 10, 600, 1800


def log(*a): print(*a, flush=True)


def fail(msg):
    log('\nERROR: ' + msg); sys.exit(1)


def load_manifest():
    p = os.path.join(MEDIA, 'manifest.json')
    if not os.path.exists(p): fail('store/media_v2/manifest.json is missing (run store/media_v2/tools/manifest.py)')
    m = json.load(open(p, encoding='utf8'))
    if LOCALE not in m.get('locales', {}): fail(f'no media for locale {LOCALE} in the manifest (has: {", ".join(m.get("locales", {}))})')
    return m['locales'][LOCALE]


def check_files(man):
    """Every file exists and is byte for byte what the manifest describes; sizes fit the display type."""
    n = 0
    for kind, table, sizes in (('screenshots', SHOT_SETS, SHOT_SIZES), ('previews', PREVIEW_SETS, None)):
        for key, dtype in table.items():
            for f in man.get(kind, {}).get(key, []):
                path = os.path.join(MEDIA, f['path'])
                if not os.path.exists(path): fail('missing file ' + f['path'])
                data = open(path, 'rb').read()
                if len(data) != f['bytes'] or hashlib.md5(data).hexdigest() != f['md5']:
                    fail(f['path'] + ' differs from the manifest (run tools/manifest.py again and commit)')
                if sizes and (f['width'], f['height']) not in sizes[dtype]: fail(f"{f['path']} is {f['width']}x{f['height']}, not a {dtype} size")
                if kind == 'previews':
                    if (f['width'], f['height']) != (1920, 886): fail(f"{f['path']} is {f['width']}x{f['height']}, an iPhone preview must be 1920x886")
                    if not 15 <= f['duration'] <= 30: fail(f"{f['path']} lasts {f['duration']} s, a preview must be 15 to 30 s")
                    if len(data) > 500 * 1024 * 1024: fail(f['path'] + ' is over 500 MB')
                n += 1
    return n


def find_version(aid):
    vs = call('GET', f'/apps/{aid}/appStoreVersions?filter[versionString]={VERSION}&filter[platform]=IOS')['data']
    if not vs:
        fail(f'version {VERSION} does not exist in App Store Connect. Create it first (asc_release.yml stage prepare, or + Version in the browser).')
    v = vs[0]; a = v['attributes']; state = a.get('appVersionState') or a.get('appStoreState')
    states = {a.get('appVersionState'), a.get('appStoreState')} - {None}
    if not states & EDITABLE:
        fail(f'version {VERSION} is in state {state}: screenshots and previews cannot be changed now. '
             f'Editable states: {", ".join(sorted(EDITABLE))}. If it is waiting for review, remove it from review first.')
    return v['id'], state


def upload_asset(typ, attrs, rel_name, rel_type, rel_id, path):
    """reserve -> PUT every part -> commit with the md5 checksum. Returns the asset id."""
    data = open(path, 'rb').read()
    a = {'fileName': os.path.basename(path), 'fileSize': len(data)}; a.update(attrs)
    res = call('POST', '/' + typ, {'data': {'type': typ, 'attributes': a, 'relationships': {rel_name: {'data': {'type': rel_type, 'id': rel_id}}}}})['data']
    ops = res['attributes'].get('uploadOperations') or []
    if not ops: raise ApiError('no upload operations returned for ' + path)
    for k, op in enumerate(ops, 1):
        chunk = data[op['offset']:op['offset'] + op['length']]
        h = {x['name']: x['value'] for x in op.get('requestHeaders', [])}
        for attempt in range(4):
            r = requests.request(op['method'], op['url'], headers=h, data=chunk, timeout=600)
            if r.status_code < 300: break
            if attempt == 3: raise ApiError(f'upload part {k}/{len(ops)} of {os.path.basename(path)} -> {r.status_code}')
            time.sleep(3 * (attempt + 1))
    call('PATCH', f'/{typ}/{res["id"]}', {'data': {'type': typ, 'id': res['id'], 'attributes': {'uploaded': True, 'sourceFileChecksum': hashlib.md5(data).hexdigest()}}})
    return res['id']


def wait_done(typ, ids, limit, video=False):
    """Poll until every asset is processed. Returns {id: attributes}. A failed asset stops the run."""
    t0, out, left = time.time(), {}, list(ids)
    while left:
        for i in list(left):
            a = call('GET', f'/{typ}/{i}')['data']['attributes']
            st = (a.get('assetDeliveryState') or {}).get('state'); vst = (a.get('videoDeliveryState') or {}).get('state') if video else None
            errs = ((a.get('assetDeliveryState') or {}).get('errors') or []) + (((a.get('videoDeliveryState') or {}).get('errors') or []) if video else [])
            if st == 'FAILED' or vst == 'FAILED' or errs:
                fail(f'{typ} {a.get("fileName")} failed processing: {json.dumps(errs, ensure_ascii=False)[:1500]}')
            if st == 'COMPLETE' or (video and vst == 'COMPLETE'):
                out[i] = a; left.remove(i)
        if left:
            if time.time() - t0 > limit: fail(f'{typ}: {len(left)} file(s) still processing after {limit} s; check App Store Connect and run again')
            time.sleep(POLL_S)
    return out


def replace_screenshots(lid, loc, dtype, files):
    sets = all_pages(f'/appStoreVersionLocalizations/{lid}/appScreenshotSets')
    s = next((x for x in sets if x['attributes']['screenshotDisplayType'] == dtype), None)
    old = all_pages(f"/appScreenshotSets/{s['id']}/appScreenshots") if s else []
    log(f'  [{loc}] screenshots {dtype}: {len(old)} existing -> {len(files)} new' + (' (dry run)' if DRY else ''))
    if DRY:
        for f in files: log(f"      would upload {f['path']} ({f['width']}x{f['height']}, {f['bytes'] // 1024} KB)")
        return
    for e in old: call('DELETE', f"/appScreenshots/{e['id']}")
    sid = s['id'] if s else call('POST', '/appScreenshotSets', {'data': {'type': 'appScreenshotSets', 'attributes': {'screenshotDisplayType': dtype},
        'relationships': {'appStoreVersionLocalization': {'data': {'type': 'appStoreVersionLocalizations', 'id': lid}}}}})['data']['id']
    ids = []
    for f in files:
        ids.append(upload_asset('appScreenshots', {}, 'appScreenshotSet', 'appScreenshotSets', sid, os.path.join(MEDIA, f['path'])))
        log(f"      uploaded {os.path.basename(f['path'])}")
    call('PATCH', f'/appScreenshotSets/{sid}/relationships/appScreenshots', {'data': [{'type': 'appScreenshots', 'id': i} for i in ids]})
    wait_done('appScreenshots', ids, WAIT_SHOT_S)
    now = [x['id'] for x in all_pages(f'/appScreenshotSets/{sid}/appScreenshots')]
    if sorted(now) != sorted(ids): fail(f'[{loc}] {dtype}: the set does not hold exactly the uploaded screenshots (has {len(now)}, expected {len(ids)})')
    log(f'      {dtype}: {len(ids)} screenshots processed' + (', order verified' if now == ids else '; WARNING: Apple lists them in another order, check the page'))


def replace_previews(lid, loc, ptype, files):
    sets = all_pages(f'/appStoreVersionLocalizations/{lid}/appPreviewSets')
    s = next((x for x in sets if x['attributes']['previewType'] == ptype), None)
    old = all_pages(f"/appPreviewSets/{s['id']}/appPreviews") if s else []
    log(f'  [{loc}] previews {ptype}: {len(old)} existing -> {len(files)} new' + (' (dry run)' if DRY else ''))
    if DRY:
        for f in files: log(f"      would upload {f['path']} ({f['width']}x{f['height']}, {f['duration']} s, {f['bytes'] // 1024} KB, poster frame {f['poster']})")
        return
    for e in old: call('DELETE', f"/appPreviews/{e['id']}")
    sid = s['id'] if s else call('POST', '/appPreviewSets', {'data': {'type': 'appPreviewSets', 'attributes': {'previewType': ptype},
        'relationships': {'appStoreVersionLocalization': {'data': {'type': 'appStoreVersionLocalizations', 'id': lid}}}}})['data']['id']
    ids = []
    for f in files:
        ids.append(upload_asset('appPreviews', {'mimeType': 'video/mp4'}, 'appPreviewSet', 'appPreviewSets', sid, os.path.join(MEDIA, f['path'])))
        log(f"      uploaded {os.path.basename(f['path'])}")
    if len(ids) > 1: call('PATCH', f'/appPreviewSets/{sid}/relationships/appPreviews', {'data': [{'type': 'appPreviews', 'id': i} for i in ids]})
    wait_done('appPreviews', ids, WAIT_VIDEO_S, video=True)
    # the poster frame can only be chosen once the video is processed; Apple may need a moment more, so retry and read back
    for i, f in zip(ids, files):
        for attempt in range(6):
            try:
                call('PATCH', f'/appPreviews/{i}', {'data': {'type': 'appPreviews', 'id': i, 'attributes': {'previewFrameTimeCode': f['poster']}}}); break
            except ApiError as e:
                if attempt == 5: fail(f'poster frame of {f["path"]} could not be set: {e}')
                time.sleep(20)
        a = wait_done('appPreviews', [i], WAIT_VIDEO_S, video=True)[i]
        got = a.get('previewFrameTimeCode')
        log(f"      {os.path.basename(f['path'])}: processed, poster frame {got}" + ('' if got == f['poster'] else f" (asked for {f['poster']}; Apple rounds to a frame it has)"))


def main():
    if WHAT not in ('all', 'screenshots', 'previews'): fail('WHAT must be all, screenshots or previews')
    man = load_manifest(); n = check_files(man)
    log(f'Media: locale {LOCALE}, {n} local files match the manifest. Version {VERSION}, targets {TARGETS}, what {WHAT}, dry run {DRY}.')
    aid = app_id(); vid, state = find_version(aid)
    locs = all_pages(f'/appStoreVersions/{vid}/appStoreVersionLocalizations')
    have = [l['attributes']['locale'] for l in locs]
    want = have if TARGETS == 'all' else [x.strip() for x in TARGETS.split(',') if x.strip()]
    miss = [x for x in want if x not in have]
    if miss: fail(f'the version has no localization {", ".join(miss)} (it has: {", ".join(have)})')
    log(f'App {aid}, version {VERSION} ({state}), localizations: {", ".join(have)}; replacing media in: {", ".join(want)}')
    for l in locs:
        loc = l['attributes']['locale']
        if loc not in want: continue
        if WHAT in ('all', 'screenshots'):
            for key, dtype in SHOT_SETS.items():
                files = man.get('screenshots', {}).get(key, [])
                if files: replace_screenshots(l['id'], loc, dtype, files)
        if WHAT in ('all', 'previews'):
            for key, ptype in PREVIEW_SETS.items():
                files = man.get('previews', {}).get(key, [])
                if files: replace_previews(l['id'], loc, ptype, files)
    log('\nDry run: nothing was changed. Run again with dry_run off to replace the media.' if DRY else '\nDone: screenshots and previews replaced and processed.')


if __name__ == '__main__':
    try: main()
    except ApiError as e: fail(str(e))
