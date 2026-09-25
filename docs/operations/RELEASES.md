# Releases and artifact verification

DeviceMesh publishes only components that have a production-capable implementation. Android, iOS and ESP32 remain separate roadmap products and are intentionally excluded from the production release until their implementation, testing and signing requirements are complete.

## Release trigger

A Git tag matching `v*` runs `.github/workflows/release.yml`. Pull requests that touch release inputs execute the same build/package paths without publishing anything, so packaging regressions are caught before a tag exists.

## Published artifacts

A tagged release produces:

| Component | Distribution |
|---|---|
| Backend API | `ghcr.io/<owner>/devicemesh-api:<tag>` |
| Web application | `ghcr.io/<owner>/devicemesh-web:<tag>` |
| Distributed probe | `ghcr.io/<owner>/devicemesh-probe:<tag>` |
| Windows agent | self-contained x64 MSI attached to the GitHub Release |
| Linux agent | DEB and RPM attached to the GitHub Release |
| macOS agent | release binary + launchd plist + README in a `.tar.gz` attached to the GitHub Release |

The GitHub Release is created only after all production image/package jobs succeed.

## Checksums

Each downloadable OS package has a component/version-specific `*.SHA256SUMS` asset. Verify after downloading, for example:

```bash
sha256sum -c DeviceMesh-Linux-Agent-<version>.SHA256SUMS
```

On macOS use `shasum -a 256 -c <checksum-file>`. On Windows compare `Get-FileHash -Algorithm SHA256` with the corresponding checksum asset.

## Build provenance

Tagged Windows MSI, Linux DEB/RPM and macOS archive artifacts receive GitHub artifact attestations. Published API/web/probe OCI images are also attested by immutable registry digest.

With GitHub CLI installed, a downloaded artifact can be verified against this repository:

```bash
gh attestation verify <artifact> --repo DavidEgeaCalatayud/DeviceMesh
```

For container images, use the digest emitted by GHCR/release metadata and verify its attestation rather than trusting a mutable local tag alone.

## Release invariants

- A tag must be numeric Semantic Versioning after removing the `v` prefix for OS packages.
- Windows, Linux and macOS package tests run before packaging.
- API, web and probe Dockerfiles must build successfully on release-validation pull requests.
- Tagged images are pushed only with the release tag; pull requests never publish to GHCR.
- GitHub Release creation depends on all production package/image jobs.
- Human mobile-store and hardware release channels are not represented as successful until those products themselves are production-capable.

## Rollback

Container rollback uses the previous immutable release tag/digest. Agent rollback follows the platform package mechanism and compatibility policy; do not downgrade below the server-published minimum version in `/api/v1/system/version`.
