# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0] - 2026-05-12

First publishable release. Identical surface to the planned `1.0.0`;
shipped at `0.9.0` first so the GitLab CI publish pipeline and PyPI
artefact can be smoke-tested without burning the immutable `1.0.0`
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

[Unreleased]: https://github.com/Check-Host/python-lib/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/Check-Host/python-lib/releases/tag/v0.9.0
