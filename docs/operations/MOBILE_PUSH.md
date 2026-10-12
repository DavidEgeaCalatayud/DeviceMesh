# Mobile push notifications

DeviceMesh delivers alert-opened and alert-recovered notifications through the same durable
notification outbox used by webhook, Slack and email channels. Mobile push therefore inherits
route filtering, maintenance-window suppression, deduplication, leasing, exponential retry,
dead-letter state and manual retry.

## Client registration

Android uses Firebase Cloud Messaging (FCM). Production release CI materializes
`google-services.json` only from the `ANDROID_GOOGLE_SERVICES_JSON_BASE64` repository secret,
builds the signed artifact and deletes the file afterwards. The JSON file is ignored by Git.

iOS uses native APNs registration through `UIApplication.registerForRemoteNotifications()`.
The signed provisioning profile must include the Push Notifications capability. Debug builds
register against APNs sandbox; Release builds use production.

After human login, each app registers its provider token at
`POST /api/v1/mobile/push-subscriptions` together with a stable installation ID. Logout removes
the installation registration. Rotated FCM/APNs tokens replace the previous token for the same
installation.

Provider tokens are not stored in clear text in PostgreSQL. DeviceMesh stores SHA-256 for
deduplication plus AES-GCM ciphertext using `DEVICEMESH_MOBILE_PUSH_ENCRYPTION_SECRET`. The
production deployment helper creates this secret as a Docker secret. Rotating that encryption
secret requires re-registering mobile installations because existing ciphertext cannot be
decrypted with the new key.

## Notification channel

Create a normal notification channel with `kind=push` and route it like any other DeviceMesh
channel. The channel `secretRef` resolves a JSON document from the normal notification secret
directory/environment.

A combined FCM + APNs secret has this shape:

```json
{
  "fcm": {
    "projectId": "example-project",
    "clientEmail": "firebase-adminsdk@example-project.iam.gserviceaccount.com",
    "privateKey": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
  },
  "apns": {
    "teamId": "APPLE_TEAM_ID",
    "keyId": "APNS_KEY_ID",
    "bundleId": "io.github.davidegeacalatayud.devicemesh",
    "privateKey": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
  }
}
```

FCM uses the OAuth scope `https://www.googleapis.com/auth/firebase.messaging` and Google's HTTPS
OAuth endpoint. DeviceMesh signs the service-account assertion with RS256 and sends through the
FCM HTTP v1 API.

APNs uses ES256 provider tokens over HTTP/2. Sandbox registrations are sent to
`api.sandbox.push.apple.com`; production registrations go to `api.push.apple.com`.

Never commit either private key. Rotate the notification `secretRef` value/file atomically.

## Audience

Push channels accept either of these optional config fields:

- `userIds`: explicit persisted human user IDs.
- `roles`: one or more of `viewer`, `operator`, `administrator`.

If neither is present, the default audience is `operator` plus `administrator`. Disabled users
and disabled push registrations are never returned as targets.

Example channel:

```json
{
  "name": "mobile-operations",
  "kind": "push",
  "secretRef": "mobile-push-providers",
  "config": {
    "roles": ["operator", "administrator"]
  }
}
```

Route that channel through `/api/v1/operator/notification-routes` and optionally restrict it by
transition, metric or device.

## Failure handling

FCM/APNs delivery uses the existing durable notification retry policy. A provider response that
identifies a dead/unregistered device token disables that target so later alerts stop attempting
it. Transient provider/network errors keep the outbox item queued with exponential backoff.

Provider private keys, OAuth tokens and mobile device tokens must never appear in logs or API
responses. The subscription API returns only registration metadata, not the token.

## Release requirements

Android production push requires:

- signed APK/AAB credentials;
- `ANDROID_GOOGLE_SERVICES_JSON_BASE64`;
- the Firebase Android app configured for the DeviceMesh package ID.

iOS production push requires:

- Apple distribution certificate/provisioning profile;
- Push Notifications enabled for the App ID;
- the APNs provider key configured only in the backend notification secret.

Push delivery should be acceptance-tested on at least one physical Android device and one physical
iOS device before #20/#47 are considered fully validated in a release.
