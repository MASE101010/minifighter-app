"""Replace the Google Play listing graphics with the 2.0 store media (safe to run again).
Source: store/media_v2/manifest.json. Uses the Android Publisher API edits: one edit, for every listing language
(TARGETS, default all languages the listing has) delete all + upload for phoneScreenshots and featureGraphic, and for
sevenInchScreenshots / tenInchScreenshots when TABLETS is on; then validate and commit.
DRY_RUN (default true): opens an edit, prints what the listing has and what would be uploaded, deletes the edit.
The promo video is not uploaded here: Google Play takes a YouTube URL (Play Console > Main store listing > Video).

Environment: PLAY_SA (the PLAY_SERVICE_ACCOUNT_JSON secret; the account needs "Manage store presence"),
LOCALE (media language in the manifest, default he), TARGETS (all | comma separated Play language codes, Hebrew is
iw-IL), TABLETS (default false), DRY_RUN (default true)."""
import hashlib, json, os, sys, time

PKG = 'com.sapirproductions.minifighter'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA = os.path.join(ROOT, 'store', 'media_v2')
API = 'https://androidpublisher.googleapis.com/androidpublisher/v3/applications/' + PKG
UP = 'https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/' + PKG
LOCALE = os.environ.get('LOCALE', '').strip() or 'he'
TARGETS = os.environ.get('TARGETS', '').strip() or 'all'
TABLETS = os.environ.get('TABLETS', 'false').strip().lower() in ('true', '1', 'yes')
DRY = os.environ.get('DRY_RUN', 'true').strip().lower() not in ('false', '0', 'no')
# manifest set -> (Play image type, allowed pixel sizes or None, max count)
TYPES = [('play_phone', 'phoneScreenshots', 8), ('play_feature', 'featureGraphic', 1)]
if TABLETS: TYPES += [('play_tablet7', 'sevenInchScreenshots', 8), ('play_tablet10', 'tenInchScreenshots', 8)]


def log(*a): print(*a, flush=True)


def fail(msg):
    log('\nERROR: ' + msg); sys.exit(1)


def load():
    p = os.path.join(MEDIA, 'manifest.json')
    if not os.path.exists(p): fail('store/media_v2/manifest.json is missing (run store/media_v2/tools/manifest.py)')
    m = json.load(open(p, encoding='utf8')).get('locales', {})
    if LOCALE not in m: fail(f'no media for locale {LOCALE} in the manifest')
    out = []
    for key, itype, mx in TYPES:
        files = m[LOCALE].get('screenshots', {}).get(key, [])
        if not files: fail(f'the manifest has no {key} files')
        if len(files) > mx: fail(f'{key}: {len(files)} files, Google Play takes at most {mx}')
        for f in files:
            path = os.path.join(MEDIA, f['path'])
            if not os.path.exists(path): fail('missing file ' + f['path'])
            data = open(path, 'rb').read()
            if len(data) != f['bytes'] or hashlib.md5(data).hexdigest() != f['md5']: fail(f['path'] + ' differs from the manifest (run tools/manifest.py again and commit)')
            if len(data) > 8 * 1024 * 1024: fail(f['path'] + ' is over 8 MB')
            w, h = f['width'], f['height']
            if itype == 'featureGraphic' and (w, h) != (1024, 500): fail(f"{f['path']} must be 1024x500")
            if itype != 'featureGraphic' and not (320 <= min(w, h) and max(w, h) <= 3840 and max(w, h) <= 2 * min(w, h)):
                fail(f"{f['path']}: {w}x{h} is outside Google Play's screenshot limits (320 to 3840 px, at most 2:1)")
        out.append((itype, files))
    return out


def main():
    plan = load()
    log(f'Media: locale {LOCALE}; ' + ', '.join(f'{t} x{len(f)}' for t, f in plan) + f'. Targets {TARGETS}, dry run {DRY}.')
    raw = os.environ.get('PLAY_SA', '')
    if not raw.strip(): fail('PLAY_SERVICE_ACCOUNT_JSON secret is missing (docs/STORE_RELEASE_2.0.md section 2.1). The local files are valid.')
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    S = AuthorizedSession(service_account.Credentials.from_service_account_info(json.loads(raw), scopes=['https://www.googleapis.com/auth/androidpublisher']))

    def call(method, url, ok404=False, **kw):
        for attempt in range(4):
            r = S.request(method, url, timeout=300, **kw)
            if r.status_code in (429, 500, 502, 503) and attempt < 3: time.sleep(4 * (attempt + 1)); continue
            break
        if ok404 and r.status_code == 404: return None
        if r.status_code >= 300: fail(f'{method} {url.split("/applications/")[-1]} -> {r.status_code}: {r.text[:2000]}')
        return r.json() if r.text else {}

    edit = call('POST', API + '/edits', json={})['id']
    try:
        langs = [l['language'] for l in call('GET', f'{API}/edits/{edit}/listings').get('listings', [])]
        if not langs: fail('the app has no store listing yet')
        want = langs if TARGETS == 'all' else [x.strip() for x in TARGETS.split(',') if x.strip()]
        miss = [x for x in want if x not in langs]
        if miss: fail(f'the listing has no language {", ".join(miss)} (it has: {", ".join(langs)})')
        log(f'Listing languages: {", ".join(langs)}; replacing media in: {", ".join(want)}')
        for lang in want:
            for itype, files in plan:
                old = call('GET', f'{API}/edits/{edit}/listings/{lang}/{itype}').get('images', [])
                log(f'  [{lang}] {itype}: {len(old)} existing -> {len(files)} new' + (' (dry run)' if DRY else ''))
                if DRY:
                    for f in files: log(f"      would upload {f['path']} ({f['width']}x{f['height']}, {f['bytes'] // 1024} KB)")
                    continue
                call('DELETE', f'{API}/edits/{edit}/listings/{lang}/{itype}')
                for f in files:
                    data = open(os.path.join(MEDIA, f['path']), 'rb').read()
                    r = call('POST', f'{UP}/edits/{edit}/listings/{lang}/{itype}?uploadType=media', data=data,
                             headers={'Content-Type': 'image/png' if f['path'].endswith('.png') else 'image/jpeg'})
                    got = (r.get('image') or {}).get('sha256', '')
                    if got and got != hashlib.sha256(data).hexdigest(): fail(f"{f['path']}: Google stored different bytes (sha256 mismatch)")
                    log(f"      uploaded {os.path.basename(f['path'])}")
                now = call('GET', f'{API}/edits/{edit}/listings/{lang}/{itype}').get('images', [])
                if len(now) != len(files): fail(f'[{lang}] {itype}: the edit holds {len(now)} images, expected {len(files)}')
        if DRY:
            log('\nDry run: nothing was changed. Run again with dry_run off to replace the graphics.'); return
        call('POST', f'{API}/edits/{edit}:validate')
        call('POST', f'{API}/edits/{edit}:commit'); edit = None
        log('\nDone: the edit is committed. Listing changes can take a few hours (or a review) to show on Google Play.')
    finally:
        if edit:
            try: S.request('DELETE', f'{API}/edits/{edit}', timeout=60)
            except Exception: pass


if __name__ == '__main__':
    main()
