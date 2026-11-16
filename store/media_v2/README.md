# Mini Fighter 2.0: store media (App Store + Google Play)

Everything the two store pages show for version 2.0: screenshots, the App Store app preview, the Google Play promo
video master and the feature graphic, plus the tools that make them and the tools that upload them.
All picture material is the real v2 game (the build in `game/v2web`), driven in headless Chromium through the game's
own interface: real matches against the game's bots, real special moves, the real chest opening and menus. The save
is a seeded long-time player called מיכאל. Nothing is drawn by hand except the Hebrew headline, the frame and the
captions (brand font SAPIR POP, `tools/SapirPop-Hebrew3.ttf`). No ads, no tester or debug UI, no prices.
Language: Hebrew, used for every localization of the listing (he and en-US on the App Store).

## Files

### Screenshots (`screenshots/`, JPEG quality 92, RGB, no alpha, 8 per set, strongest first)
| folder | size | store slot |
|---|---|---|
| `appstore_iphone69/` | 2868x1320 | App Store iPhone 6.9" (`APP_IPHONE_67`) |
| `appstore_iphone65/` | 2778x1284 | App Store iPhone 6.5" (`APP_IPHONE_65`) |
| `play_phone/` | 1920x1080 | Google Play phone screenshots |
| `play_tablet7/` | 1920x1200 | Google Play 7 inch tablet (optional, see below) |
| `play_tablet10/` | 2560x1600 | Google Play 10 inch tablet (optional, see below) |
| `play_feature/play_feature_1024x500.jpg` | 1024x500 | Google Play feature graphic (the game's key art + title) |

Order and headline of the 8 screenshots (file names carry the number and the scene):
1. `fight` קרבות אונליין מטורפים (2 on 2 on the volcano arena, the royal beam mid-hit)
2. `crown` שלושה על שלושה: קרב על הכתר (3 on 3 crown mode, sky arena)
3. `chest` פתחו תיבות וגלו לוחמים אגדיים (a legendary fighter revealed from a chest)
4. `lobby` שחקו ביחד עם חברים (the lobby with a party of three)
5. `fighters` אספו ושדרגו 27 לוחמים (the roster)
6. `modes` 4 מצבי קרב לבחירה
7. `pass` כרטיס עונה מלא פרסים (the season pass; the current season is Hanukkah)
8. `road` טפסו בליגות ואספו גביעים (the trophy road)

iPad: the app is iPhone only (`TARGETED_DEVICE_FAMILY = 1`, set in `build/ios_setup.py`), so there are no iPad
screenshots or previews. Google Play tablets: whether the current listing has tablet screenshots could not be read
without the Play service account, so both tablet sets are provided and `play_media.yml` uploads them only when asked.

### Videos (`video/`)
| file | spec |
|---|---|
| `appstore_preview_1920x886.mp4` | App Store app preview for iPhone 6.9" and 6.5": 1920x886, H.264 High, 30 fps, stereo AAC 48 kHz, under 30 s |
| `appstore_preview_1920x886.json` | its length and the poster frame (`hh:mm:ss:ff`) the upload sets |
| `play_promo_1920x1080.mp4` | Google Play promo video master: 1920x1080, H.264 High, 30 fps, stereo AAC 48 kHz, 30 to 60 s |

The exact sizes, durations and checksums are in `manifest.json` (written by `tools/manifest.py`, read by the upload
scripts). Google Play takes the promo video as a YouTube URL: upload `play_promo_1920x1080.mp4` to the channel
(public or unlisted, no ads on it, not age restricted), then paste the URL in Play Console > Main store listing > Video.

Sound: the game's own fight music file (`music_fight`) and the game's own sound effects. The effects are not
recorded from the speakers: each take logs which effect the game played on which frame, and the game's sound engine
(`MF2SFX.render`) renders exactly those offline, in the cut's order.

### Contact sheets (`contact_sheets/`)
`screenshots_<set>.jpg` (all 8 of a set) and `video_<name>.jpg` (30 evenly spaced frames of each video), for a quick review.

## Regenerate (one command)

    store/media_v2/tools/make_all.sh

It uses the game build of this repository (`game/v2web`, updated by `build/update_game.py`). To use another build,
for example a newer one from minifighter-source (`MF_V2=1 python3 game/tools/build.py && python3 game/tools/split_web.py`):

    MF_WEB=/path/to/minifighter-source/game/dist/v2web store/media_v2/tools/make_all.sh

Needs: Python 3 with Playwright (Chromium) and Pillow, ffmpeg. About 25 minutes on a small machine. Parts:
`make_all.sh shots` (screenshots only), `make_all.sh video` (videos only), `make_all.sh check` (spec check only).
Raw captures go to `store/media_v2/.work/` (not committed; `MF_WORK` moves it). Then commit the changed files and
`manifest.json`.

| tool | what it does |
|---|---|
| `tools/lib.py` | opens the game offline with the seeded save; the fight director (keeps real matches lively: the engine's AI plays every fighter, mana stays up, nobody falls before the planned moment) |
| `tools/vclock.js` | virtual clock: every clock the page reads moves only when the capture steps it, one step per video frame, so the footage is exact 30 fps however slow the machine is; also seeds `Math.random` so a scene replays the same way |
| `tools/shots_raw.py` | raw 2868x1320 captures: UI screens, the chest reveal, and for the two fights the frame with the most action (scored from the game state) |
| `tools/compose.py` | headline + frame for every store size, and the feature graphic. Headlines are in `ITEMS` |
| `tools/video_capture.py` | the takes (lobby, VS, duel with KO, 3 on 3, 2 on 2, results, chest, menus) with marks and the effect log. `appstore` = 1920x886, `play` = 1920x1080 |
| `tools/video_edit.py` | the cuts (`PREVIEW`, `PROMO`: take, mark, offset, length, caption), captions, sound mix, encode |
| `tools/manifest.py` | checks every file against the store specs, writes `manifest.json` and the contact sheets |

To change a headline or caption: edit `ITEMS` in `compose.py` or `PREVIEW` / `PROMO` in `video_edit.py` and run the
matching part again (the raw captures are reused if `.work` is still there).

## Upload

### App Store (Actions > "App Store media (screenshots + app previews, 2.0)", `asc_media.yml`)
Inputs: `version` (2.0.0), `locale` (he, the media language), `dry_run` (on by default), `targets` (all = every
localization of the version, today he and en-US), `what` (all / screenshots / previews).
1. Run with `dry_run` on: it checks the local files against `manifest.json`, finds the version, and prints what is
   there now and what would be uploaded. Nothing changes.
2. Run with `dry_run` off: for each localization and each display type it deletes the existing screenshots, reserves
   and uploads the new ones (parts, then commit with the md5 checksum), sets the order, waits until Apple has
   processed them; the same for the app preview, then sets the poster frame and reads it back.
It stops with a clear message, before changing anything, if version 2.0.0 does not exist or is not editable
(editable: PREPARE_FOR_SUBMISSION, DEVELOPER_REJECTED, REJECTED, METADATA_REJECTED, INVALID_BINARY). Secrets: the
same `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_KEY_P8` as the other App Store workflows. Script: `build/asc_media.py`.
Note: `build/asc_setup.py` (workflow "App Store page setup") still uploads the old 1.0 screenshots from
`store/screens` to the 6.9" set when that set does not already hold 8; run `asc_media.yml` after it, not before.

### Google Play (Actions > "Google Play media (screenshots + feature graphic, 2.0)", `play_media.yml`)
Needs the `PLAY_SERVICE_ACCOUNT_JSON` secret, which does not exist yet (docs/STORE_RELEASE_2.0.md section 2.1; the
account needs "Manage store presence"). Until then the workflow validates the files and stops with that message.
Inputs: `dry_run` (on by default), `locale` (he), `targets` (all listing languages), `tablets` (off).
With `dry_run` off it opens one edit, and for every listing language deletes and uploads the phone screenshots and
the feature graphic (and the tablet sets when `tablets` is on), validates and commits the edit. Script:
`build/play_media.py`. The promo video is set by hand (YouTube URL, see above).
