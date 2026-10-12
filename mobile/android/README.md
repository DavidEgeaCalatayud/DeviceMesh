# DeviceMesh Android

Native Kotlin/Compose operator client for the DeviceMesh V1 API.

The application implements human login/refresh/logout, optional MFA possession-factor login,
Android Keystore-backed encrypted session persistence, HTTPS-only server validation, dashboard,
devices, incidents, alerts, synthetic monitors and distributed-probe status.

The app never stores passwords or MFA factors. Access/refresh tokens are encrypted with an
AES-256-GCM key generated inside AndroidKeyStore and application backup is disabled.

Pull requests run unit tests, Android lint and a debug build. The release workflow creates a
signed AAB/APK when production signing secrets are configured; signing material is never
committed to the repository.
