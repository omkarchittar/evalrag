# Release verification

## Published source and CI

The source is published at [omkarchittar/evalrag](https://github.com/omkarchittar/evalrag).
The first verified commit is [`18ebfce`](https://github.com/omkarchittar/evalrag/commit/18ebfce941b96d00a878e9cf4f77b38d445c0f37).
[GitHub Actions run 36397513432](https://github.com/omkarchittar/evalrag/actions/runs/36397513432)
completed successfully on 2026-09-28 with all four jobs passing.

| Gate | Remote result |
| --- | --- |
| Backend lint, formatting and PostgreSQL tests | 185 tests passed |
| Schema drift and migration downgrade/upgrade | Passed |
| Frontend lint, types, formatting and production browser suite | 7 journeys passed |
| API image build | Passed |
| Console image build | Passed |

Browser and backend providers in CI are controlled fixtures. These results verify software
contracts, packaging and integration; they are not live-model quality measurements.
Local Linux/arm64 Compose verification also passed the same browser journeys as recorded
in the [implementation ledger](implementation-plan.md).

## Release candidate

`v0.1.0-rc.1` points to the verified commit above. Its publishing workflow repeats the complete
quality gate before building amd64/arm64 images. All six quality/publishing jobs passed in [release run 36397853294](https://github.com/omkarchittar/evalrag/actions/runs/36397853294).
Live-provider benchmark measurements and public HTTPS deployment remain open acceptance gates.
A release candidate is not a claim that those gates are complete.

## Published images

The following OCI index digests were read anonymously from GHCR and verified by SHA-256.
For each image, both Linux amd64 and arm64 platform manifests, image configurations and
SBOM/provenance statement blobs were read and their hashes checked. Source/revision labels
match the tagged commit; runtime users are nonroot (`app` / `node`). Each architecture has
an SPDX SBOM and SLSA provenance statement with the matching image subject.

| Image | Immutable OCI index digest |
| --- | --- |
| `ghcr.io/omkarchittar/evalrag-api` | `sha256:09490bcbf390fcad945418fe682628da7b25e9f97f1b338cf6199ac2861b2fba` |
| `ghcr.io/omkarchittar/evalrag-console` | `sha256:1fa63ea9df09c56698cef9dfd9b9e0e6ea8a1428eca7d8634e005745373949ee` |

[Machine-readable verification](release-images.json) records the exact platform digests,
source revision, runtime users, attestation types and check timestamp. Both images carry
`v0.1.0-rc.1` and a full commit-SHA tag; deployments should use the immutable digests above.
See [deployment instructions](deployment.md) for the API/console environment variables and
Compose image override. API, migration and worker services share the API image.

## Runtime verification of published artifacts

Pulled these exact digests anonymously and started fresh disposable stacks using
`compose.release.yaml`. API, migration and worker services used the published API image;
the console used the published frontend image. The temporary test override supplied separate
ports, fictional accounts and the existing controlled HTTP provider fixture.

Migrations completed and API health checks passed. All **7 browser journeys passed (24.2s)**
against the published images on **Linux/arm64**, including real database and worker behavior.
The temporary projects, volumes, fixture credentials and runner configuration were removed.

This verifies the release artifacts on that platform. It does not claim live-model quality,
amd64 runtime execution, production load capacity or a public HTTPS deployment. Live-provider
reports and public deployment remain open acceptance gates.
