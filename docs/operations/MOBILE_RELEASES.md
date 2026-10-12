# Mobile release and acceptance

DeviceMesh treats build validation, signed artifact production and store publication as separate
release gates. Pull requests never require production signing material.

## Android

Pull-request CI runs:

- core network unit tests;
- Android lint;
- debug APK build;
- release AAB build;
- Compose UI instrumentation tests on an API 35 emulator.

The signed release workflow requires these repository secrets:

- `ANDROID_KEYSTORE_BASE64`;
- `ANDROID_KEYSTORE_PASSWORD`;
- `ANDROID_KEY_ALIAS`;
- `ANDROID_KEY_PASSWORD`.

The workflow writes the keystore only to the runner temporary directory, verifies the signed APK
with `apksigner`, emits APK/AAB SHA-256 checksums and uploads the signed artifacts.

For Google Play internal testing, configure `ANDROID_PUBLISHER_CREDENTIALS` with a service
account authorized for the DeviceMesh Play Console application. A manual release can opt in with
`upload_play=true`; an `android-v*` tag publishes automatically. Version code uses the GitHub
run number and version name is derived from the tag.

## iOS

Simulator CI generates the project with XcodeGen and executes both XCTest and XCUITest. Signing is
disabled in that gate.

The signed release workflow requires:

- `IOS_CERTIFICATE_P12_BASE64`;
- `IOS_CERTIFICATE_PASSWORD`;
- `IOS_PROVISIONING_PROFILE_BASE64`;
- `IOS_TEAM_ID`.

The certificate is imported into an ephemeral runner keychain. The provisioning profile is
decoded only for the job. DeviceMesh is archived in Release configuration, exported to an IPA,
checksummed and uploaded as an artifact. The cleanup step deletes the temporary keychain and
signing files even when the job fails.

For TestFlight/App Store Connect upload configure:

- `APP_STORE_CONNECT_API_KEY_ID`;
- `APP_STORE_CONNECT_API_ISSUER_ID`;
- `APP_STORE_CONNECT_API_PRIVATE_KEY_BASE64`.

A manual run opts in with `upload_testflight=true`; an `ios-v*` tag validates and uploads
automatically.

## Acceptance boundary

Emulator/simulator CI proves application navigation and release-build integrity, not physical
device behaviour. Before a mobile release is considered fully accepted retain evidence from at
least one supported physical Android device and one supported physical iPhone for:

- login, refresh and logout;
- background/foreground push notification delivery;
- BLE provisioning of a reference ESP32;
- network loss and session-recovery behaviour;
- device detail and safe-operation workflow;
- installation of the signed release artifact.

Store-account publication receipts and physical-device evidence are release-environment artifacts;
they are not fabricated in pull-request CI.
