# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-05-12

### Removed
- `CheckHost.info_force()` and the matching tests. The endpoint
  `/infoforce/{target}` was an artefact of a pre-2.0 Swagger draft and
  does **not** exist on the production Check-Host API; calls would
  have returned 404. Use `CheckHost.info()` (`POST /info`) instead.

### Changed
- Bundled `swagger.yaml` re-synced with the latest 2.0.0 spec the API
  team is publishing.
- README points to <https://check-host.cc/docs> as the primary API
  reference; the bundled Swagger spec is the secondary fallback.

## [1.0.0] - 2026-05-12

Stable release. Aligned with **Check-Host.cc API Swagger 2.0.0** (richer
`/info` shape, new endpoints, new fields on `CheckCreated`). All
existing call sites from `0.9.0` keep working - backward-compatible
properties cover the renamed fields.

### Added
- `CheckHost.myinfo()` - geolocation + ASN for the caller's own IP
  (`GET /myinfo`).
- `CheckHost.info_force(target)` - cache-bypass geolocation lookup
  (`GET /infoforce/{target}`; accepts IPs only, not hostnames).
- `CheckHost.country_map(uuid)` / `save_country_map(uuid, path)` -
  per-country world map (SVG default, PNG optional with low/med/high
  resolution; `GET /report/{uuid}/country-map`).
- `MinResponseINFO` now exposes the rich Swagger 2.0.0 fields:
  `country_code`, `is_eu`, `continent`, `latitude`, `longitude`,
  `time_zone`, `postal_code`, `subdivision`, `currency_code`,
  `calling_code`, `privacy`, `asn`, `company`, `abuse`, `success`.
  Old `zipcode` and `iprange` survive as backward-compatible properties.
- `CheckCreated` now exposes `region`, `og_image_url`, `port`,
  `query`, `payload` - all echoed back by the production API since 2.0.0.
- `DNSType.A_AAAA = "A/AAAA"` constant; validation accepts the
  compound query method without uppercase-folding it.
- Swagger 2.0.0 file shipped inside the wheel at `checkhost/swagger.yaml`.

### Changed
- Project description sharpened to mention all check types and 60+ global
  locations.
- `publish_pypi` CI job now passes `--skip-existing` to `twine upload`
  so an idempotent re-tag (force-move) does not break the pipeline if
  the file already exists on PyPI.

### Test
- Unit-test suite grew from 143 to 155 tests (12 new for the new
  endpoints, model fields, and DNS-type compound).
- Live integration tests grew from 5 to 8 (covering `myinfo`,
  `info_force`, `country_map`); all 8 pass against the production API.

## [0.9.0] - 2026-05-12

First publishable release. Identical surface to the planned `1.0.0`;
shipped at `0.9.0` first so the GitLab CI publish pipeline and PyPI
artefact could be smoke-tested without burning the immutable `1.0.0`
version on PyPI.

### Added
- Initial release.
- Full Check-Host.cc API 1.2.0 coverage:
  - Utilities: `myip()`, `locations()`, `info()`, `whois()`.
  - Monitoring: `ping()`, `dns()`, `tcp()`, `udp()`, `http()`, `mtr()`.
  - Results: `report()`, `wait_for_report()`, `og_image()`, `save_og_image()`.
- Granular exception hierarchy (`CheckHostError`, `CheckHostNetworkError`,
  `CheckHostTimeoutError`, `CheckHostAPIError`, `CheckHostBadRequestError`,
  `CheckHostNotFoundError`, `CheckHostRateLimitError`, `CheckHostServerError`,
  `CheckHostValidationError`).
- Client-side validation (port range, DNS type, MTR repeats, force-protocol).
- Region/DNS-Type/MTR-protocol constants.
- Automatic API-key injection (constructor or `CHECK_HOST_API_KEY` env).
- Context manager support.
- Built-in polling helper `wait_for_report()` with configurable interval and
  timeout.
- OG-image fetch and save helper.
- PEP 561 typing marker (`py.typed`).
- Zero runtime dependencies (stdlib only).

### Notes on API drift
The production `check-host.cc` API deviates from Swagger 1.2.0 in two places.
This release transparently handles both shapes:

1. `CheckCreated.success` — Swagger says `string` ("success" / "failure"); the
   live API returns a boolean. `is_success` accepts `true`, `"success"`,
   `"true"` and `"ok"` interchangeably.
2. `GET /report/{uuid}` — Swagger describes no schema. The live API nests node
   results under `data` with each node carrying metadata plus a `checks` list.
   Some peer libraries assume a flat `{node: [results]}` shape; the SDK
   supports both.

[Unreleased]: https://github.com/Check-Host/python-lib/compare/v1.0.1...HEAD
[1.0.1]: https://github.com/Check-Host/python-lib/releases/tag/v1.0.1
[1.0.0]: https://github.com/Check-Host/python-lib/releases/tag/v1.0.0
[0.9.0]: https://github.com/Check-Host/python-lib/releases/tag/v0.9.0
