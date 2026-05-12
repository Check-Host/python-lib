# check-host-api

A lightweight, zero-dependency Python 3.10+ SDK for the [Check-Host.cc](https://check-host.cc) API.

Distributed network diagnostics from 60+ global locations: ICMP ping, MTR, DNS,
HTTP, TCP, UDP, WHOIS and geolocation, with the same fluent surface as the
official [`nodejs-lib`](https://github.com/Check-Host/nodejs-lib),
[`php-lib`](https://github.com/Check-Host/php-lib),
[`go-lib`](https://github.com/Check-Host/go-lib) and
[`CheckHost4J`](https://github.com/Check-Host/CheckHost4J) — and a few extras
specific to Python.

## Highlights

- **Zero runtime dependencies** — built on top of `urllib.request`.
- **Full Swagger 1.2.0 parity** — every endpoint covered.
- **Type hints throughout** with a [PEP 561](https://peps.python.org/pep-0561/)
  `py.typed` marker.
- **POST-based requests** — no URL-encoding pitfalls.
- **Built-in polling helper** `wait_for_report()` so you don't have to babysit
  the `report` endpoint by hand.
- **Automatic API-key injection** from the constructor or the
  `CHECK_HOST_API_KEY` environment variable.
- **Granular exception hierarchy** — separate classes for 400, 404, 429 and 5xx.
- **Client-side validation** for ports, DNS record types, MTR repeats etc.
- **OG-Image** fetch and save helper for status maps.
- **Region / DNS / MTR-protocol constants** for IDE autocompletion.
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
    print(f"{info.ip} -> {info.city}, {info.country}")

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

    # Save the dynamic status map (PNG, 1200x630)
    ch.save_og_image(task.uuid, "./status.png")
```

## Authentication

The API works without a key (subject to public rate limits). For higher limits,
provide an API key via constructor or environment variable:

```python
ch = CheckHost("YOUR_API_KEY")
# or
import os
os.environ["CHECK_HOST_API_KEY"] = "YOUR_API_KEY"
ch = CheckHost()
```

When both are present, the constructor argument wins.

## API reference

### Utilities

| Method | Endpoint | Returns |
|---|---|---|
| `ch.myip()` | `GET /myip` | `str` — public IP of the caller |
| `ch.locations()` | `GET /locations` | `dict[str, Any]` — raw node catalogue |
| `ch.info(target)` | `POST /info` | `MinResponseINFO` — geolocation/ISP |
| `ch.whois(target)` | `POST /whois` | `dict[str, Any]` — registry data |

### Monitoring

All monitoring methods return a `CheckCreated` whose `uuid` is the handle for
`report()` / `og_image()`.

| Method | Endpoint |
|---|---|
| `ch.ping(target, *, region=None, repeat_checks=0, timeout=None)` | `POST /ping` |
| `ch.dns(target, *, query_method="A", region=None)` | `POST /dns` |
| `ch.tcp(target, port, *, region=None, repeat_checks=0, timeout=None)` | `POST /tcp` |
| `ch.udp(target, port, *, payload=None, region=None, repeat_checks=0, timeout=None)` | `POST /udp` |
| `ch.http(target, *, region=None, repeat_checks=0, timeout=None)` | `POST /http` |
| `ch.mtr(target, *, region=None, repeat_checks=10, force_ip_version=None, force_protocol=None)` | `POST /mtr` |

Validation enforced client-side:

- `port`: 1-65535
- `repeat_checks` (non-MTR): 0-120
- `repeat_checks` (MTR): 3-30
- `query_method`: one of `A`, `AAAA`, `MX`, `TXT`, `CAA`, … (full list in
  `checkhost.regions.DNSType.ALL`)
- `force_ip_version`: 4 or 6
- `force_protocol`: `"icmp" | "udp" | "tcp"`

### Reports

| Method | Endpoint | Returns |
|---|---|---|
| `ch.report(uuid)` | `GET /report/{uuid}` | `Report` (may be incomplete) |
| `ch.wait_for_report(uuid, *, interval=1.5, max_wait=30.0, require_complete=True)` | polls `GET /report/{uuid}` | `Report` |
| `ch.og_image(uuid)` | `GET /report/{uuid}/og-image` | `bytes` (PNG) |
| `ch.save_og_image(uuid, path)` | same | `Path` written |

Use `report.completed_nodes`, `report.pending_nodes` and `report.is_complete`
to inspect progress; `report.raw` always preserves the raw API payload.

### Constants

```python
from checkhost.regions import Continent, DNSType, IPVersion, MTRProtocol

Continent.EUROPE        # "EU"
Continent.ALL           # ("EU", "NA", "SA", "AS", "AF", "OC")

DNSType.MX              # "MX"
DNSType.ALL             # ("A", "AAAA", "NS", ..., "DNSKEY")

IPVersion.V4            # 4
MTRProtocol.TCP         # "tcp"
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
        # Invalid input — fix the call.
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

The SDK uses the standard `logging` module under the logger name `"checkhost"`.
Enable debug logs to inspect every outgoing HTTP request:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("checkhost").setLevel(logging.DEBUG)
```

## Proxies and TLS

`urllib.request` from the standard library is used, which means
`HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` environment variables are honoured
automatically and TLS verification follows the system trust store.

## Development

```bash
git clone https://git.check-host.eu/Check-Host/python-lib
cd python-lib
pip install -e ".[dev]"
pytest
```

To run the integration tests against the live API (these consume real rate
limit budget):

```bash
pytest -m live
```

## License

[Apache-2.0](LICENSE)

## Related libraries

- [`@check-hostcc/check-host-api`](https://github.com/Check-Host/nodejs-lib) (Node.js)
- [`check-hostcc/check-host-api-php`](https://github.com/Check-Host/php-lib) (PHP)
- [`github.com/Check-Host/go-lib`](https://github.com/Check-Host/go-lib) (Go)
- [`cc.checkhost:checkhost4j`](https://github.com/Check-Host/CheckHost4J) (Java)
