# Mini Fighter: Android app (cloud build)

Every push to `main` (or **Actions > Build Android app > Run workflow**) builds a signed AAB in GitHub Actions.
Download it from the finished run, under **Artifacts**, and upload it to Google Play Console.

- The game itself is `game/index.html` (built from the source repo `minifighter-source`).
- `build/make_web.py` prepares the app version (offline fonts, back button, AdMob ads).
- Signing uses the upload key stored as encrypted repository secrets (KEYSTORE_BASE64, KEYSTORE_PASSWORD, KEY_ALIAS, KEY_PASSWORD).
- Version code = the workflow run number, so every build is higher than the previous one.
