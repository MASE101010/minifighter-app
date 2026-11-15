# Mini Fighter 2.0: store release (in-app purchases, legal, ratings)

Status 2026-11-15. Source of the catalog: minifighter-source v2 `docs/STORE_PRODUCTS.md` at commit b0e6f23
(checked against `game/src/v2/meta.js` by `build/iap_catalog.py --check-meta`: same 30 ids, types and prices).

## 1. What exists now

### App Store Connect: all 30 products created, state READY_TO_SUBMIT
Each one has: type, reference name `<English name> (<id>)`, Hebrew + English (en-US) display name and description,
price from the Israeli price point (base territory Israel, Apple equalizes the other territories), available in all
175 territories and new ones, a review screenshot of the real v2 shop (`store/iap_review/<section>.png`, 2868x1320),
and a review note (where to find it, the parent gate, restore, odds link). Family sharing is off for the consumables.
Nothing was submitted for review.

| product id | Apple type | ILS | state |
|---|---|---|---|
| mf_gems_1 | CONSUMABLE | 4.90 | READY_TO_SUBMIT |
| mf_gems_2 | CONSUMABLE | 9.90 | READY_TO_SUBMIT |
| mf_gems_3 | CONSUMABLE | 19.90 | READY_TO_SUBMIT |
| mf_gems_4 | CONSUMABLE | 49.90 | READY_TO_SUBMIT |
| mf_gems_5 | CONSUMABLE | 99.90 | READY_TO_SUBMIT |
| mf_offer_starter | NON_CONSUMABLE | 4.90 | READY_TO_SUBMIT |
| mf_bundle_hero | NON_CONSUMABLE | 19.90 | READY_TO_SUBMIT |
| mf_bundle_legend | NON_CONSUMABLE | 59.90 | READY_TO_SUBMIT |
| mf_fighter_elroei, _alin, _elaor, _hop, _fox, _tiger, _hatul | NON_CONSUMABLE | 4.90 | READY_TO_SUBMIT |
| mf_fighter_lito, _raz, _noa, _sheleg, _lehava | NON_CONSUMABLE | 9.90 | READY_TO_SUBMIT |
| mf_fighter_barak, _sela, _maya | NON_CONSUMABLE | 19.90 | READY_TO_SUBMIT |
| mf_fighter_tal, _virus | NON_CONSUMABLE | 34.90 | READY_TO_SUBMIT |
| mf_fighter_boss | NON_CONSUMABLE | 59.90 | READY_TO_SUBMIT |
| mf_skin_michael_h | NON_CONSUMABLE | 14.90 | READY_TO_SUBMIT |
| mf_skin_tuli_h | NON_CONSUMABLE | 12.90 | READY_TO_SUBMIT |
| mf_skin_hop_h | NON_CONSUMABLE | 9.90 | READY_TO_SUBMIT |
| mf_pass_premium | NON_RENEWING_SUBSCRIPTION | 19.90 | READY_TO_SUBMIT |
| premium_all (unchanged) | NON_CONSUMABLE | 9.90 | APPROVED, still on sale |

### Google Play: NOT created yet
The repository has no `PLAY_SERVICE_ACCOUNT_JSON` secret, so `play_iap.yml` stopped before calling Google
(run 43687926785: "PLAY_SERVICE_ACCOUNT_JSON secret is missing"). The script is ready; see 2.1.

### Tools (all in this repo, safe to run again)
- `build/iap_catalog.py <STORE_PRODUCTS.md> --check-meta` makes `store/iap_products.json` (the only input of the store
  scripts). Run it after every change to STORE_PRODUCTS.md, commit, then run the workflows.
- Actions > **App Store in-app purchases (2.0 catalog)** (`asc_iap.yml`): create/update all, or `only` some ids;
  `age_rating` (default on) sets the 2.0 age rating once the 2.0 version exists; `retire_premium` removes premium_all
  from sale; `status_only` prints the table.
- Actions > **Google Play in-app products (2.0 catalog)** (`play_iap.yml`): create/update and activate all (one-time
  products API, falls back to the legacy in-app products API), ILS price for Israel, other regions from Google's own
  conversion, Hebrew + English listings. `status_only` prints the table. premium_all is never touched.
- `build/asc_submit.py` (the iOS workflow's submit job) now also sends every catalog product that is READY_TO_SUBMIT
  with the version (`SUBMIT_IAPS`, default true; a no-op once they are approved).
- `build/odds_page.py <source> <site>` rebuilds the public odds page from meta.js (run it if drop odds change).

## 2. Owner only (cannot be done through the API or by an agent)

1. **Google Play service account** (needed for `play_iap.yml` and for the automatic Play upload in `build.yml`):
   Google Cloud console > IAM > Service accounts > create one > Keys > add JSON key. Play Console > Users and
   permissions > Invite new users > the service account e-mail > App permissions for Mini Fighter: "Manage store
   presence" (in-app products) and "Release to production" if the build upload should work too. Then GitHub >
   minifighter-app > Settings > Secrets > Actions > `PLAY_SERVICE_ACCOUNT_JSON` = the whole JSON file. Tell the
   coordinator; the agent then runs `play_iap.yml`. (Alternative: create the 30 products by hand in Play Console >
   Monetize > Products > One-time products, with the ids, prices and texts of `store/iap_products.json`.)
2. **Apple Agreements, Tax and Banking**: premium_all was approved, so the Paid Apps agreement was active. Open App
   Store Connect > Business and check that the Paid Apps agreement is "Active" (not "Pending" after a new terms
   version) and that bank and tax forms show no warning. Same in Play Console > Setup > Payments profile.
3. **App Privacy questionnaire** in App Store Connect (not in the public API): answers in section 4.2.
4. **Decision: nicknames.** Nicknames are free text (16 characters, control characters removed, no word filter) and
   other players see them. Apple asks about user-generated content (guideline 1.2 then expects a way to report and
   block). The age rating step declares `userGeneratedContent` as false (nicknames only, no chat, no uploads). If the
   owner prefers to declare it, change it in App Store Connect; either way a simple bad-word filter on nicknames
   (server `cleanName`) and a "report player" button are recommended before review.
5. **Optional: a lawyer's review** of the terms section 5 (cancellation of digital content under the Consumer
   Protection Law) and the privacy policy. The texts follow the existing style and the law as generally applied,
   but they are not legal advice.

## 3. Release steps

### App Store (2.0)
1. Done: `version.txt` is 2.0.0 and `game/v2web` holds the split v2 build pinned in `game/SOURCE.txt`. To ship a
   newer game commit: `python3 build/update_game.py /path/to/minifighter-source <commit>`, commit, push (the push
   builds the Android AAB/APK), then Run workflow on **Build iPhone app** (upload on, submit off for TestFlight).
   Optional check before release: Actions > **Smoke test 2.0** (web, Android emulator, iPhone simulator).
2. Run **App Store page setup** (`asc_setup.yml`): it needs an editable version; if none exists yet, the iOS
   workflow's submit job creates it, or create "2.0.0" in App Store Connect (+ Version). It writes the 2.0 texts,
   the new App Review notes (`store/listing_en.txt`) and the age rating with loot boxes declared.
3. Run **App Store in-app purchases** with `age_rating` on (sets loot boxes = yes on the 2.0 app info).
4. In App Store Connect check: Age Rating shows "In-App Purchases" and "Random Items / Loot Boxes", App Privacy
   (section 4.2), What's New (from `release_notes/`).
5. Run **Build iPhone app** with `upload` on and `submit` on. The submit job attaches the build, sends the 30
   in-app purchases with the version and submits. If the log shows "in-app purchase NOT sent", open the 2.0 version
   page > "In-App Purchases and Subscriptions" > Select, tick all 30, Save, then Add for Review.
6. Review: sandbox testing is described in the review notes. After approval it releases automatically.
7. **After 2.0 is live** (and most players updated): run **App Store in-app purchases** with `retire_premium` on.
   premium_all is removed from sale, not deleted. Restore keeps working: the plugin's `getPurchases` reads
   `Transaction.currentEntitlements` / `Transaction.all`, which keep a non-consumable that is no longer on sale. Do not
   do this before: 1.0.13 still sells it.

### Google Play (2.0)
1. Owner: the service account secret (2.1). Then run **Google Play in-app products**; it ends with a status table
   (all 30 ACTIVE). Products appear in the app within about an hour.
2. Apply the Play Console checklists in section 5 (Data safety, content rating, target audience stays 13+).
3. Build the AAB with the v2 game (push to main, or Run workflow); upload: Run workflow with `publish` on, or a
   commit message with `[release]`, or upload the AAB from the run's Artifacts by hand. The Hebrew "What's new" comes
   from `release_notes/he.txt` (318 bytes; the workflow cuts at 500 bytes).
4. premium_all on Play stays **active but unused** (the v2 build never offers it). Not deactivated: it was not
   verified that Google keeps returning owned purchases of a deactivated product to `queryPurchasesAsync` on every
   Billing Library version, and leaving it active costs nothing.

## 4. App Store answers

### 4.1 Age rating (2.0)
- Cartoon or fantasy violence: Frequent/Intense (as now). Realistic violence, weapons, horror, mature themes,
  sexual content, profanity, drugs, medical: None.
- Gambling: No. Simulated gambling: None. Contests: None.
- **Loot boxes: Yes** (reward chests with random contents can be bought with gems, and gems can be bought with
  money; odds disclosed in the game and at https://minifighter.co.il/odds/).
- Messaging and chat: No (no free text; predefined emotes only).
- User-generated content: No (see owner decision 2.4).
- Advertising: Yes. Unrestricted web access: No. Social media: No. Parental controls: No (the parent gate is a
  purchase gate, not a parental control feature). Age assurance: No.
- Age rating override: 13+ (as now). In-app purchases are shown automatically from the products.

### 4.2 App Privacy (nutrition label), add to the existing ad answers
Data collected, all **linked to the user** (the cloud account id), **not used for tracking**, purpose
**App Functionality**:
- Identifiers > User ID (the anonymous cloud account id and the public player tag).
- Purchases > Purchase History (product id and transaction id, kept in the save so a purchase is granted once).
- User Content > Gameplay Content (nickname and game progress in the cloud save; friends list).
Unchanged from 1.0: Identifiers > Device ID, Usage Data and Diagnostics as declared for Google AdMob (third-party
advertising), and the App Tracking Transparency prompt.

### 4.3 App Review notes
In `store/listing_en.txt` section "App Review notes" (pushed by `asc_setup.py`): no login, cloud save, online modes
with bots filling seats, friends (tag, add, party), the parent gate with an example and how to answer it, sandbox
testing, the product types, chests only for in-game currency with the odds link, premium_all retired but restorable,
ads and ATT. Every product also carries its own review note.

## 5. Google Play checklists (Play Console, by hand)

### 5.1 Data safety (App content > Data safety), changes from 1.0
- Data collected: **Personal info > Name** (the in-game nickname; Google counts nicknames as name), **Personal
  info > User IDs** (cloud account id, player tag), **App activity > In-app purchase history** (transaction ids),
  **App activity > Other actions** (game progress in the cloud save). For each: collected, not shared, not processed
  ephemerally, required for cloud save / optional for offline play, purposes **App functionality** and
  **Account management**.
- Keep the AdMob answers as today (Device or other IDs, App interactions, Diagnostics; shared with Google for
  advertising).
- Data is encrypted in transit: Yes.
- Users can request deletion: Yes. Deletion URL: https://minifighter.co.il/privacy/ (section 11 explains how, with
  the restore code or player tag, by e-mail).
- Account creation: "My app does not allow users to create an account" is no longer exact; choose that the app
  creates an account automatically (no username/password), and give the same deletion URL.

### 5.2 Content rating (App content > Content rating > start a new questionnaire)
- Category: Game. Violence: cartoon/fantasy as before.
- **Users interact / online interaction: Yes** (online matches, friends list, parties; no free text chat, only
  predefined emotes; nicknames visible).
- **Shares user's location: No.** Shares personal info with other users: No (only nickname and player tag).
- **Digital purchases: Yes.**
- **Random items (loot boxes) purchasable: Yes**: chests with random contents are bought with in-game currency
  (gems) that can be bought with real money. Expect "In-game purchases (includes random items)" on the rating.
- Gambling or simulated gambling: No. Unrestricted internet: No.

### 5.3 Other Play Console pages
- Target audience and content: stays **13 and over** (no change). Not in the Families program.
- Ads: Yes, contains ads (no change).
- Privacy policy URL: https://minifighter.co.il/privacy/ (updated).
- Store listing: the description sentences about the Full Version were replaced in `store/listing_he.txt` and
  `store/listing_en.txt` (paste them into the Play listing too).

## 6. Legal pages (minifighter-site, deployed by Cloudflare on push)
- https://minifighter.co.il/privacy/ : cloud save and restore code, player tag, friends, parties, nicknames,
  emotes only, purchases (store confirmation only), parent gate, retention per data type, deletion, Amendment 13.
- https://minifighter.co.il/terms/ : virtual items (licence, no cash value, not transferable), purchases (never
  chests), parent gate, cancellation and refunds (Consumer Protection Law, digital content exception, statutory
  rights kept, contact social@sapirfamily.co.il and the Google/Apple refund paths), chest odds, cloud account and
  nicknames, online conduct.
- https://minifighter.co.il/odds/ : chest odds from the game's tables (start rarity, upgrade chances, pity, contents
  by rarity, fighter chances per chest type), linked in every footer and the sitemap.

## 7. Submission 2026-11-15 (build 28, game cb608142)
- 2.0.0 (28) submitted with release MANUAL: version and review submission WAITING_FOR_REVIEW.
- 24 in-app purchases went with it (WAITING_FOR_REVIEW): the starter offer, both bundles, all 18 fighters, the 3 skins.
- Apple refused the 5 gem packs and the season pass through the API: STATE_ERROR.FIRST_CONSUMABLE_MUST_BE_SUBMITTED_ON_VERSION
  and STATE_ERROR.FIRST_NON_RENEWING_SUBSCRIPTION_MUST_BE_SUBMITTED_ON_VERSION. The app never had a consumable or a
  non-renewing product, and the first of each type can only be attached on the version page in App Store Connect
  (the API has no call for it). They stay READY_TO_SUBMIT; in 2.0 the game shows them as "בקרוב" until approved.
- To include them in 2.0: App Store Connect > the app > 2.0.0 > "Cancel submission" (or remove from review), then on
  the version page, "In-App Purchases and Subscriptions" > Select > tick mf_gems_1..5 and mf_pass_premium > Done >
  Add for Review > Submit. Otherwise attach them the same way to the next version (2.0.1). After the first of each
  type is approved, later ones can be sent alone (Actions > App Store in-app purchases > submit_ready).
