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
- **Full Swagger 2.0.0 parity** — every endpoint covered, including the
  new `/myinfo`, `/infoforce/{target}`, `/report/{uuid}/og-image` and
  `/report/{uuid}/country-map`.
- **Type hints throughout** with a [PEP 561](https://peps.python.org/pep-0561/)
  `py.typed` marker.
- **POST-based requests** — no URL-encoding pitfalls.
- **Built-in polling helper** `wait_for_report()` so you don't have to
  babysit the `report` endpoint by hand.
- **Automatic API-key injection** from the constructor or the
  `CHECK_HOST_API_KEY` environment variable.
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

The API works without a key (subject to public rate limits). For higher
limits, provide an API key (UUID) via constructor or environment variable:

```python
ch = CheckHost("YOUR_API_KEY_UUID")
# or
import os
os.environ["CHECK_HOST_API_KEY"] = "YOUR_API_KEY_UUID"
ch = CheckHost()
```

When both are present, the constructor argument wins.

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
# Cached lookup (90 day TTL)
info = ch.info("check-host.cc")

# Force a fresh, uncached lookup (IPs only)
fresh = ch.info_force("1.1.1.1")
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

## API surface (reference table)

| Method | Endpoint | Returns |
|---|---|---|
| `ch.myip()` | `GET /myip` | `str` |
| `ch.myinfo()` | `GET /myinfo` | `MinResponseINFO` |
| `ch.locations()` | `GET /locations` | `dict[str, Any]` |
| `ch.info(target)` | `POST /info` | `MinResponseINFO` |
| `ch.info_force(target)` | `GET /infoforce/{target}` | `MinResponseINFO` |
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

### Client-side validation

The SDK rejects obviously bad input before issuing an HTTP call:

- `port`: 1-65535
- `repeat_checks` (non-MTR): 0-120
- `repeat_checks` (MTR): 3-30
- `query_method`: one of `A`, `AAAA`, `MX`, `TXT`, `CAA`, `A/AAAA`, …
  (full list in `checkhost.regions.DNSType.ALL`)
- `force_ip_version`: 4 or 6
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
        # 429: provide an API key or back off.
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
rate-limit budget — set `CHECK_HOST_API_KEY` for higher quotas):

```bash
pytest -m live              # 8 live tests, ~6s with an API key
```

## License

[Apache-2.0](LICENSE)

## Related libraries

- [`@check-hostcc/check-host-api`](https://github.com/Check-Host/nodejs-lib) (Node.js — npm)
- [`check-hostcc/check-host-api-php`](https://github.com/Check-Host/php-lib) (PHP — Composer)
- [`github.com/Check-Host/go-lib`](https://github.com/Check-Host/go-lib) (Go)
- [`cc.checkhost:checkhost4j`](https://github.com/Check-Host/CheckHost4J) (Java)

Full API reference: <https://check-host.cc/docs>.
