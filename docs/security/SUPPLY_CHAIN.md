# Software supply-chain security

DeviceMesh treats CI definitions and release artifacts as part of the production trust boundary.

## Immutable GitHub Actions

Every remote `uses:` reference under `.github/workflows/` is pinned to a full 40-character commit SHA. The human-readable upstream release (`v4`, `v5`, etc.) remains in a comment only.

`tools/security/check_pinned_actions.py` scans every workflow and fails Security CI if a remote action is introduced with a mutable tag or branch. Local actions (`./...`) are exempt because their code is already pinned by the repository commit being built.

Pins used in this revision were resolved directly from the corresponding GitHub tag/ref. Annotated tags were dereferenced to their final commit before pinning.

## Dependency reproducibility

- Backend production dependency installation is backed by `backend/requirements.lock` with hashes; Security CI audits the hashed lock with `pip-audit --require-hashes`.
- Web CI uses `npm ci` against the committed `package-lock.json`; Security CI rejects high/critical production advisories.
- Windows dependencies are restored from project metadata and scanned for vulnerable direct/transitive NuGet packages.
- Agent/probe build workflows execute their language-specific tests before packaging.

## SBOM

Main-branch builds generate a CycloneDX JSON software bill of materials for the repository. The SBOM is:

1. produced by the pinned Anchore SBOM action;
2. cryptographically attested by GitHub artifact attestations;
3. uploaded as the `devicemesh-sbom` workflow artifact.

Verify a downloaded SBOM with:

```bash
gh attestation verify devicemesh-sbom.cdx.json --repo DavidEgeaCalatayud/DeviceMesh
```

## Release provenance

Tagged production releases produce GitHub artifact attestations for:

- Windows MSI;
- Linux DEB and RPM packages;
- macOS agent archive;
- API OCI image by immutable digest;
- web OCI image by immutable digest;
- distributed-probe OCI image by immutable digest.

These attestations are signed provenance statements tied to the GitHub Actions identity and repository. They complement SHA-256 checksum assets: a checksum detects byte changes, while attestation verification also checks the artifact's claimed build identity/provenance.

For downloaded packages:

```bash
gh attestation verify <artifact> --repo DavidEgeaCalatayud/DeviceMesh
```

For OCI images, verify the registry digest/attestation rather than trusting a mutable local alias.

## Vulnerability gates

Security CI currently includes:

- Trivy filesystem scan for HIGH/CRITICAL findings with unfixed vulnerabilities ignored;
- `pip-audit` over the hash-locked backend dependency set;
- `npm audit --omit=dev --audit-level=high`;
- NuGet direct/transitive vulnerability inspection;
- protocol-contract tests exercising schema/mutation boundaries;
- immutable GitHub Action reference enforcement.

## Trust boundaries and limitations

Artifact attestations establish build provenance but are not a replacement for platform-specific publisher identity certificates such as Apple Developer ID or Windows Authenticode. DeviceMesh does not claim those external publisher certificates until a production distribution channel explicitly requires and configures them. The repository's release trust boundary is therefore: immutable CI definitions + checksums + GitHub signed provenance + SBOM + vulnerability gates.

Mobile and ESP32 releases remain outside the production release/supply-chain matrix until those products themselves reach their implementation/testing milestones.

## Updating an action

Do not change a SHA by guessing or by copying an unverified value. Resolve the desired upstream tag/ref through GitHub, dereference annotated tags to the final commit, review the upstream release/change, replace the SHA, and let Security CI validate that all workflow references remain immutable.
