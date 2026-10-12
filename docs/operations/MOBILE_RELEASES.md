# Mobile testing and releases

DeviceMesh treats mobile validation and distribution as release gates, not as a successful
compiler invocation.

## Android

Pull requests that touch `mobile/android` run:

1. core network unit tests;
2. Android lint;
3. debug APK build;
4. unsigned release AAB build validation;
5. an API 35 emulator boot;
6. `connectedDebugAndroidTest`, including the Compose fresh-install login smoke.

The release workflow remains separate from PR CI. It imports the Android keystore only from
GitHub Actions secrets and emits a signed APK/AAB plus SHA-256 checksums.

Required Android release secrets:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

## iOS

The generated DeviceMesh Xcode scheme includes both `DeviceMeshTests` and
`DeviceMeshUITests`. Pull requests build without code signing and execute both XCTest and
XCUITest on an iPhone simulator.

`iOS Release` performs the stronger release gate:

1. imports an Apple Distribution certificate into an ephemeral runner keychain;
2. installs the supplied provisioning profile;
3. regenerates the Xcode project;
4. runs unit/UI tests;
5. archives a manually signed Release build;
6. exports and verifies the IPA;
7. publishes the IPA/checksum as a workflow artifact;
8. on an `ios-v*` tag (or an explicit manual choice), uploads the IPA to App Store Connect.

Required signing secrets:

- `APPLE_TEAM_ID`
- `IOS_CERTIFICATE_P12_BASE64`
- `IOS_CERTIFICATE_PASSWORD`
- `IOS_PROVISIONING_PROFILE_BASE64`
- `IOS_KEYCHAIN_PASSWORD`

App Store Connect upload additionally requires:

- `APPSTORE_API_KEY_ID`
- `APPSTORE_ISSUER_ID`
- `APPSTORE_API_PRIVATE_KEY_BASE64`

No certificate, provisioning profile, keystore, API key or password is stored in the repository.

## Physical-device boundary

Simulator/emulator gates verify UI startup, navigation surface and build/runtime integration.
Bluetooth provisioning, push delivery and device-specific lifecycle behaviour still require
named physical-device acceptance before a release is promoted as hardware-validated. Those
checks are tracked separately so simulator success is never presented as physical validation.
