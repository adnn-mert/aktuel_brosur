# Çarşı Pazar (Flutter app)

The Android app of the Aktüel Broşür project: weekly brochures of Turkish supermarket chains,
designed for elderly users (large touch targets, large text, high contrast, screen-reader labels,
offline reading). It has no server; it only reads the JSON and images that the scraper in
`../scraper/` publishes to GitHub Pages. The project overview is in the [root README](../README.md).

State management is Riverpod, UI text is Turkish and lives in `lib/l10n/`. Code layout:
`lib/data/` (data layer, the only place that talks to HTTP, files and JSON), `lib/design/`
(theme and shared widgets), `lib/features/` (one folder per screen).

## Run

Flutter 3.47, from this folder:

```bash
flutter pub get
flutter run --dart-define=CATALOG_BASE_URL=https://adnn-mert.github.io/aktuel_brosur/
```

Without `CATALOG_BASE_URL` the app shows bundled sample data.

Notification support needs the Firebase values as `--dart-define`s. No Firebase configuration is
committed. Put your `google-services.json` into the git-ignored `../secrets/` folder, generate the
define file once from the repository root, then pass it to Flutter:

```bash
python app/tool/firebase_defines.py          # writes secrets/firebase_defines.json
cd app
flutter run --dart-define-from-file=../secrets/firebase_defines.json --dart-define=CATALOG_BASE_URL=https://adnn-mert.github.io/aktuel_brosur/
```

Without the Firebase values the app simply has no notification controls.

## Analyze and test

```bash
flutter analyze
flutter test
```

Both must finish without warnings or failures.

## Release signing

Release APKs are signed with one permanent project key, because Android installs an update only
over an app signed with the same key. `android/app/build.gradle.kts` looks for it in this order:

1. the environment variables `ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`,
   `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD` (what the release workflow sets);
2. `android/key.properties`;
3. `../secrets/android/keystore.properties` (repository root).

The two properties files use the keys `storeFile`, `storePassword`, `keyAlias` and `keyPassword`;
a relative `storeFile` is resolved against the folder of the properties file. All of these, the
keystore and the whole `secrets/` folder are git-ignored; never commit them.

If no key is found, a local `flutter run --release` or `flutter build apk --release` still works
but is signed with the debug key and prints a warning (that APK cannot update an installed release
build). On CI (`CI` environment variable set) the build fails instead.

A local build of the three per-architecture APKs, as the release workflow does it:

```bash
flutter build apk --release --split-per-abi --dart-define-from-file=../secrets/firebase_defines.json --dart-define=CATALOG_BASE_URL=https://adnn-mert.github.io/aktuel_brosur/
```

## More

- [`DESIGN.md`](DESIGN.md): the design system (touch targets, type sizes, colours, interaction
  rules). Anyone touching the UI follows it.
- [`lib/data/README.md`](lib/data/README.md): the data layer for UI code (providers, models,
  error and offline behaviour).
