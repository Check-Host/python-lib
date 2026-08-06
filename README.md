# check-host-api

A lightweight, zero-dependency Python 3.10+ SDK for the [Check-Host.cc](https://check-host.cc) API.

Distributed network diagnostics from 60+ global locations: ICMP ping, MTR, DNS,
HTTP, TCP, UDP, WHOIS and geolocation, with the same fluent surface as the
official [`nodejs-lib`](https://github.com/Check-Host/nodejs-lib),
[`php-lib`](https://github.com/Check-Host/php-lib),
[`go-lib`](https://github.com/Check-Host/go-lib) and
[`CheckHost4J`](https://github.com/Check-Host/CheckHost4J) — plus a few
extras specific to Python.

Full API reference: <https://check-host.cc/docs>.

## Highlights

- **Zero runtime dependencies** — built on top of `urllib.request`.
- **Full Swagger 2.1.0 parity** — every endpoint covered, including the
  Network Intelligence and Fullscan families, `/myinfo`,
  `/report/{uuid}/og-image` and `/report/{uuid}/country-map`.
- **Type hints throughout** with a [PEP 561](https://peps.python.org/pep-0561/)
  `py.typed` marker.
- **POST-based requests** — no URL-encoding pitfalls.
- **Built-in polling helpers** `wait_for_report()` and
  `wait_for_fullscan()` so you don't have to babysit the endpoints by hand.
- **Bearer-token auth** from the constructor or the
  `CHECK_HOST_API_TOKEN` environment variable — sent as an
  `Authorization` header, never in the URL or request body.
- **Granular exception hierarchy** — separate classes for 400, 404,
  429 and 5xx.
- **Client-side validation** for ports, DNS record types, MTR repeats
  etc.
- **OG-Image and country-map fetch + save helpers** for status maps.
- **Region / DNS-type / MTR-protocol constants** for IDE autocompletion.
- **Context-manager support** (`with CheckHost() as ch: ...`).

## Installation

```bash
pip install check-host-api
```

Requires Python **3.10+**. No further dependencies.

## Quickstart

```python
from checkhost import CheckHost
from checkhost.regions import Continent, DNSType

with CheckHost() as ch:
    # Geolocation / ASN
    info = ch.info("check-host.cc")
    print(f"{info.ip} -> {info.city}, {info.country}  ({info.asn.get('name')})")

    # Ping check across Europe + North America, 3 packets per node
    task = ch.ping(
        "1.1.1.1",
        region=[Continent.EUROPE, Continent.NORTH_AMERICA],
        repeat_checks=3,
    )
    print(f"Task UUID: {task.uuid}")

    # Block until every node reports (or 20s elapses)
    report = ch.wait_for_report(task.uuid, max_wait=20.0)
    print(f"{len(report.completed_nodes)} nodes reported")

    # Save the dynamic status map (PNG, 1200x630) and country world map
    ch.save_og_image(task.uuid, "./status.png")
    ch.save_country_map(task.uuid, "./status.svg")
```

## Authentication

The API works anonymously, subject to public rate limits. For higher limits
and a per-token monthly quota, pass your API token (UUID) to the constructor
or put it in the environment:

```python
ch = CheckHost("YOUR_API_TOKEN_UUID")
# or
import os
os.environ["CHECK_HOST_API_TOKEN"] = "YOUR_API_TOKEN_UUID"
ch = CheckHost()
```

When both are present, the constructor argument wins.

The SDK sends the token as an `Authorization: Bearer <token>` header on every
request — GET, POST and binary alike. It is never placed in the query string
or the request body, so it does not leak into access logs, referrer headers
or browser history.

> **Migrating from 1.0.x:** the token used to travel in the JSON body as an
> `apikey` field. That field is deprecated server-side. The
> `CheckHost(apikey=...)` keyword still works but emits a `DeprecationWarning`
> and will be removed in 2.0 — rename it to `token`. Positional calls
> (`CheckHost("...")`) are unaffected. The old `CHECK_HOST_API_KEY`
> environment variable is still read as a fallback.

## Complete API Reference & Examples

This SDK supports both minimal invocations and detailed, options-rich
requests for every endpoint.

### Common Options

- `region`: list of node names, ISO country codes, or continent codes
  (`EU`, `NA`, `SA`, `AS`, `AF`, `OC`). Continents cannot be mixed with
  specific node names.
- `repeat_checks`: number of repeated probes per node. `0` = single
  shot; `>= 10` enables **Live Mode** (continuous probing for
  ~`repeat_checks` seconds).
- `timeout`: per-request connection timeout in seconds (currently a
  no-op on the Check-Host backend, but accepted for forward
  compatibility).

---

### Information & Utilities

#### Get my IP

Returns the requesting client's public IPv4 / IPv6 address.

```python
ip = ch.myip()
```

#### Get my info

Geolocation + ASN + privacy / abuse / company data for the caller's IP.
Subject to bot-detection — repeated calls may yield a captcha URL in a
`CheckHostRateLimitError.response`.

```python
info = ch.myinfo()
print(info.country_code, info.city, info.asn.get("name"))
```

#### List monitoring nodes

```python
locations = ch.locations()
# locations["locationlist"] is a list of nodes, each with continent,
# countryCode, isp, locationname, sponsor, etc.
```

#### Host info (geolocation / ASN)

```python
info = ch.info("check-host.cc")
```

#### WHOIS / RDAP lookup

```python
record = ch.whois("check-host.cc")
# Returns the raw RDAP record (shape varies by registry).
```

---

### Active Monitoring (POST tasks)

Each monitoring call returns a `CheckCreated` object with a `uuid`. Use
`report(uuid)` (single fetch) or `wait_for_report(uuid)` (polling
helper) to retrieve results.

#### Ping

```python
# Minimal
task = ch.ping("8.8.8.8")

# With options
task = ch.ping(
    "8.8.8.8",
    region=["DE", "NL"],
    repeat_checks=5,           # >=10 enables Live Mode
    timeout=5,
)
```

#### DNS

```python
from checkhost.regions import DNSType

# Minimal — defaults to A record
task = ch.dns("check-host.cc")

# Specific record type
task = ch.dns(
    "check-host.cc",
    query_method=DNSType.MX,    # A / AAAA / MX / TXT / NS / CAA / ...
    region=["US", "DE"],
)
```

#### TCP

```python
# Minimal — host + port
task = ch.tcp("1.1.1.1", 443)

# With options
task = ch.tcp(
    "1.1.1.1",
    80,
    region=["DE", "NL"],
    repeat_checks=3,
    timeout=10,
)
```

#### UDP

The Check-Host backend knows sensible default payloads for well-known
ports (DNS, NTP, SNMP, RIP, WireGuard, OpenVPN, Quake, Minecraft, …).
Pass a custom hex (or printable) `payload` only when probing unusual
services.

```python
# Minimal — DNS query (default payload)
task = ch.udp("1.1.1.1", 53)

# Custom NTP payload to UDP/123
task = ch.udp(
    "pool.ntp.org",
    123,
    payload="0b",
    region=["EU"],
    repeat_checks=2,
)
```

#### HTTP

```python
# Minimal — full URL
task = ch.http("https://check-host.cc")

# With options
task = ch.http(
    "https://check-host.cc/status",
    region=["EU"],
    repeat_checks=10,           # Live Mode: 11 probes over ~10s
)
```

#### MTR (My Traceroute)

```python
from checkhost.regions import MTRProtocol, IPVersion

# Minimal
task = ch.mtr("1.1.1.1")

# Force TCP for ICMP-blocked paths
task = ch.mtr(
    "1.1.1.1",
    region=["EU"],
    repeat_checks=10,
    force_ip_version=IPVersion.V4,
    force_protocol=MTRProtocol.TCP,  # "udp" or "tcp"; default is ICMP
)
```

---

### Results

#### Single fetch

```python
report = ch.report(task.uuid)
print(report.is_complete, len(report.completed_nodes), report.pending_nodes)
```

#### Poll until complete

```python
report = ch.wait_for_report(
    task.uuid,
    interval=1.5,            # clamped to >=1.0 (API limit)
    max_wait=30.0,
    require_complete=True,   # raise CheckHostTimeoutError on timeout
)
```

#### OG-Image (1200×630 PNG status map)

```python
png_bytes = ch.og_image(task.uuid)

# Or write straight to disk
ch.save_og_image(task.uuid, "./status.png")
```

#### Country world map (SVG or PNG)

```python
svg = ch.country_map(task.uuid)                                # default SVG
png_low = ch.country_map(task.uuid, format="png", resolution="low")    # 800px
png_high = ch.country_map(task.uuid, format="png", resolution="high")  # 2000px

# Convenience save
ch.save_country_map(task.uuid, "./status.svg")
```

---

### Network Intelligence

Passive lookups against the dataset behind the entity pages — no check is
dispatched, results come back immediately. Every method returns a plain
`dict` because the `data` section is open-ended: sections we hold no data for
come back as empty lists or `None`.

#### IP profile

```python
intel = ch.ip_intel("1.1.1.1")
data = intel["data"]
print(data["bgp"]["as_name"])                    # Cloudflare, Inc.
print([p["port"] for p in data["open_ports"]])   # [443, ...]
```

Sections: `ptr`, `open_ports`, `banners`, `tls_certs`, `co_hosted_domains`,
`external_refs`, `leak_candidates`, `titles`, `techs`, `bgp`, `geo`,
`probe_findings`, `threat_matches`, `threat_count`, `honeypot`,
`honeypot_recent`, `honeypot_actor`, `honeypot_ja`, `honeypot_classes`.

Honeypot passwords are never returned in cleartext — entries expose only
`password_captured` (bool) and `password_len`.

#### ASN, prefix, domain, certificate

```python
asn = ch.asn_intel("AS13335")        # or ch.asn_intel(13335)
prefix = ch.prefix_intel("1.1.1.0", 24)
domain = ch.domain_intel("check-host.cc")
cert = ch.cert_intel("3a1b8f0c…9f90")   # 64-char hex fingerprint

print(asn["data"]["prefix_count"])
print(domain["data"]["subdomains"])
print(cert["data"]["served_by"])
```

#### Port and software exposure

```python
port = ch.port_intel(443)
print(port["well_known"], port["data"]["open_ips"])

nginx = ch.software_intel("nginx")                # all versions
pinned = ch.software_intel("nginx", "1.24.0")     # one version
```

### Fullscan

A deep, on-demand multi-stage scan (ports + banners + TLS + DNS +
threat-intel). Asynchronous: submit, poll, then read the results.

```python
job = ch.fullscan("check-host.cc", scope="deep")
print(job.uuid, job.status)            # ... pending

# Block until the job reaches a terminal status (complete/partial/failed)
job = ch.wait_for_fullscan(job.uuid, max_wait=300.0)
print(job.status, job.progress)        # complete 1.0

results = ch.fullscan_results(job.uuid)
for entry in results["data"]["open_ports"]:
    print(entry["port"], entry["service"])
```

Scopes: `basic` (top-100 ports + banner), `deep` (default — full port range,
TLS, body and threat-intel), `full` (deep plus subdomain enumeration; domains
only).

Anonymous CIDR submissions are capped at `/24` (v4) and `/120` (v6); an API
token raises that to `/20` and `/112`.

Before dispatching a scan, check whether a recent one already exists:

```python
for prior in ch.fullscan_jobs("check-host.cc"):
    if prior.is_finished:
        results = ch.fullscan_results(prior.uuid)
        break
```

`fullscan()`, `fullscan_status()`, `wait_for_fullscan()` and
`fullscan_jobs()` all return `FullscanJob` objects:

| Attribute | Meaning |
|---|---|
| `uuid` | Job handle for the status / results endpoints |
| `target`, `target_type` | Submitted target and its classification (`ip`, `cidr`, `domain`, `asn`) |
| `scope` | `basic`, `deep` or `full` |
| `status` | `pending`, `running`, `complete`, `partial` or `failed` |
| `subjobs_total`, `subjobs_done`, `subjobs_failed` | Fan-out counters |
| `is_finished` | `True` once the status is terminal |
| `progress` | `subjobs_done / subjobs_total`, clamped to `[0.0, 1.0]` |
| `error` | Failure reason, or `None` |
| `report_url`, `api_url` | Human and machine report links |
| `raw` | The unmodified job dict |

---

## API surface (reference table)

| Method | Endpoint | Returns |
|---|---|---|
| `ch.myip()` | `GET /myip` | `str` |
| `ch.myinfo()` | `GET /myinfo` | `MinResponseINFO` |
| `ch.locations()` | `GET /locations` | `dict[str, Any]` |
| `ch.info(target)` | `POST /info` | `MinResponseINFO` |
| `ch.whois(target)` | `POST /whois` | `dict[str, Any]` |
| `ch.ping(target, *, region=None, repeat_checks=0, timeout=None)` | `POST /ping` | `CheckCreated` |
| `ch.dns(target, *, query_method="A", region=None)` | `POST /dns` | `CheckCreated` |
| `ch.tcp(target, port, *, region=None, repeat_checks=0, timeout=None)` | `POST /tcp` | `CheckCreated` |
| `ch.udp(target, port, *, payload=None, region=None, repeat_checks=0, timeout=None)` | `POST /udp` | `CheckCreated` |
| `ch.http(target, *, region=None, repeat_checks=0, timeout=None)` | `POST /http` | `CheckCreated` |
| `ch.mtr(target, *, region=None, repeat_checks=10, force_ip_version=None, force_protocol=None)` | `POST /mtr` | `CheckCreated` |
| `ch.report(uuid)` | `GET /report/{uuid}` | `Report` |
| `ch.wait_for_report(uuid, *, interval=1.5, max_wait=30.0, require_complete=True)` | polls `GET /report/{uuid}` | `Report` |
| `ch.og_image(uuid)` | `GET /report/{uuid}/og-image` | `bytes` (PNG) |
| `ch.save_og_image(uuid, path)` | same | `Path` |
| `ch.country_map(uuid, *, format="svg", resolution="med")` | `GET /report/{uuid}/country-map` | `bytes` |
| `ch.save_country_map(uuid, path, *, format="svg", resolution="med")` | same | `Path` |
| `ch.ip_intel(ip)` | `GET /ip/{ip}` | `dict[str, Any]` |
| `ch.asn_intel(asn)` | `GET /as/{asn}` | `dict[str, Any]` |
| `ch.prefix_intel(net, mask)` | `GET /prefix/{net}/{mask}` | `dict[str, Any]` |
| `ch.domain_intel(domain)` | `GET /domain/{domain}` | `dict[str, Any]` |
| `ch.cert_intel(sha256)` | `GET /cert/{sha256}` | `dict[str, Any]` |
| `ch.port_intel(port)` | `GET /port/{port}` | `dict[str, Any]` |
| `ch.software_intel(name, version=None)` | `GET /software/{name}[/{version}]` | `dict[str, Any]` |
| `ch.recent_scans(target)` | `GET /scan/{target}` | `dict[str, Any]` |
| `ch.fullscan_jobs(target)` | same, parsed | `list[FullscanJob]` |
| `ch.fullscan(target, *, scope="deep")` | `POST /fullscan` | `FullscanJob` |
| `ch.fullscan_status(uuid)` | `GET /fullscan/{uuid}` | `FullscanJob` |
| `ch.fullscan_results(uuid)` | `GET /fullscan/{uuid}/results` | `dict[str, Any]` |
| `ch.wait_for_fullscan(uuid, *, interval=3.0, max_wait=300.0, require_complete=True)` | polls `GET /fullscan/{uuid}` | `FullscanJob` |

### Client-side validation

The SDK rejects obviously bad input before issuing an HTTP call:

- `port`: 1-65535
- `repeat_checks` (non-MTR): 0-120
- `repeat_checks` (MTR): 3-30
- `query_method`: one of `A`, `AAAA`, `MX`, `TXT`, `CAA`, `A/AAAA`, …
  (full list in `checkhost.regions.DNSType.ALL`)
- `force_ip_version`: 4 or 6
- `asn`: `13335` or `AS13335` (normalised to the bare number)
- `sha256`: 64 hexadecimal characters
- `mask`: 0-128
- `scope`: `basic`, `deep` or `full`
- `force_protocol`: `"icmp" | "udp" | "tcp"`
- `country_map.format`: `"svg" | "png"`
- `country_map.resolution`: `"low" | "med" | "high"`

Use `report.completed_nodes`, `report.pending_nodes` and
`report.is_complete` to inspect progress; `report.raw` always preserves
the raw API payload, including any future fields the SDK doesn't yet
surface explicitly.

### Constants

```python
from checkhost.regions import Continent, DNSType, IPVersion, MTRProtocol

Continent.EUROPE         # "EU"
Continent.ALL            # ("EU", "NA", "SA", "AS", "AF", "OC")

DNSType.MX               # "MX"
DNSType.A_AAAA           # "A/AAAA" - Swagger 2.0 compound default
DNSType.ALL              # ("A/AAAA", "A", "AAAA", "NS", ..., "DNSKEY")

IPVersion.V4             # 4
MTRProtocol.TCP          # "tcp"
```

## Error handling

```python
from checkhost import (
    CheckHost,
    CheckHostBadRequestError,
    CheckHostError,
    CheckHostNetworkError,
    CheckHostRateLimitError,
    CheckHostTimeoutError,
    CheckHostValidationError,
)

with CheckHost() as ch:
    try:
        task = ch.ping("1.1.1.1")
        report = ch.wait_for_report(task.uuid, max_wait=15.0)
    except CheckHostValidationError as exc:
        # Invalid input - fix the call.
        ...
    except CheckHostRateLimitError as exc:
        # 429: send an API token or back off.
        ...
    except CheckHostBadRequestError as exc:
        # 400: bad payload.
        print(exc.status, exc.response)
    except CheckHostTimeoutError:
        # Polling deadline expired.
        ...
    except CheckHostNetworkError:
        # Connectivity / DNS / TLS issue.
        ...
    except CheckHostError:
        # Catch-all for the SDK.
        ...
```

Hierarchy at a glance:

```
CheckHostError
+-- CheckHostNetworkError
+-- CheckHostTimeoutError
+-- CheckHostValidationError       (also ValueError)
+-- CheckHostAPIError
    +-- CheckHostBadRequestError   (400)
    +-- CheckHostNotFoundError     (404)
    +-- CheckHostRateLimitError    (429)
    +-- CheckHostServerError       (5xx)
```

## Logging

The SDK uses the standard `logging` module under the logger name
`"checkhost"`. Enable debug logs to inspect every outgoing HTTP request:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("checkhost").setLevel(logging.DEBUG)
```

## Proxies and TLS

`urllib.request` from the standard library is used, which means
`HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` environment variables are
honoured automatically and TLS verification follows the system trust
store.

## Development

```bash
git clone https://git.check-host.eu/Check-Host/python-lib
cd python-lib
pip install -e ".[dev]"
pytest                      # 155 unit tests, ~0.2s
ruff check . && mypy checkhost
```

To run the integration tests against the live API (consumes real
rate-limit budget — set `CHECK_HOST_API_TOKEN` for higher quotas):

```bash
pytest -m live              # 8 live tests, ~6s with an API token
```

## License

[Apache-2.0](LICENSE)

## Related libraries

- [`@check-hostcc/check-host-api`](https://github.com/Check-Host/nodejs-lib) (Node.js — npm)
- [`check-hostcc/check-host-api-php`](https://github.com/Check-Host/php-lib) (PHP — Composer)
- [`github.com/Check-Host/go-lib`](https://github.com/Check-Host/go-lib) (Go)
- [`cc.checkhost:checkhost4j`](https://github.com/Check-Host/CheckHost4J) (Java)

Full API reference: <https://check-host.cc/docs>.
