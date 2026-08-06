# Konzept: check-host-api (Python SDK)

**Status:** Historischer Entwurf v2 (nach Self-Review)
**Datum:** 2026-05-12
**Swagger-Referenz:** Check-Host.cc API v1.2.0

> **Hinweis:** Dieses Dokument haelt den urspruenglichen Entwurf fest und wird
> nicht mehr gepflegt. Es beschreibt Stand v1.2.0 der API — inzwischen
> ueberholt durch Swagger 2.1.0. Insbesondere wandert der API-Token seit
> Version 1.1.0 in den `Authorization: Bearer`-Header statt in den POST-Body.
> Massgeblich sind `README.md` und `CHANGELOG.md`.

---

## 1. Zielsetzung

Eine Python-SDK für check-host.cc, die:

- **Volle API-Parität** zu den existierenden Libs (`nodejs-lib`, `php-lib`, `go-lib`, `CheckHost4J`) bietet
- Sich strikt an **Swagger 1.2.0** orientiert — alle Endpoints, alle Schemas, alle Statuscodes
- **Zero runtime dependencies** hat (nur Python-Stdlib) — gleicher "lightweight, zero-dependency"-Anspruch wie nodejs/php/go
- **Pythonic** ist: Type Hints, dataclasses, snake_case, Context Manager, Exception-Hierarchie, PEP 561
- **Mehr leistet** als die anderen Libs: Built-in Polling-Helper, og-image Support, ENV-Var-Fallback, clientseitige Validation, Region-/DNS-Konstanten

## 2. Projekt-Metadaten

| Item | Wert | Begruendung |
|---|---|---|
| PyPI-Name | `check-host-api` | Aligned mit `@check-hostcc/check-host-api` (nodejs) und `check-hostcc/check-host-api-php` |
| Import | `from checkhost import CheckHost` | Kurz, kollidiert mit nichts |
| License | **Apache-2.0** | Aligned mit `go-lib` + `CheckHost4J` (Mehrheit), Industriestandard fuer Libraries |
| Python-Version | **3.10+** | Erlaubt `slots=True`, `\|`-Union-Syntax, `kw_only`. Andere Libs zielen auf moderne Stacks (Java 17+, Node 18+, PHP 8.1+) |
| Build-Backend | `hatchling` | Modern, simpel, kein Setuptools-Cruft |
| Repository | `git.check-host.eu/Check-Host/python-lib` -> Mirror `github.com/Check-Host/python-lib` | Wie alle anderen Libs |

## 3. Modulstruktur

```
python-lib/
|-- checkhost/
|   |-- __init__.py        # Public API: CheckHost, Exceptions, Models, Regions, __version__
|   |-- _client.py         # Internal HTTP-Layer (urllib.request)
|   |-- _models.py         # Dataclasses: MinResponseINFO, CheckCreated, Location, Report
|   |-- _exceptions.py     # Exception-Hierarchie
|   |-- _validation.py     # Port/Region/DNS-Type Validation
|   |-- regions.py         # Continent / DNSType / MTRProtocol Konstanten
|   |-- api.py             # CheckHost-Klasse (Main Entry)
|   |-- _version.py        # __version__
|   |-- py.typed           # PEP 561 Marker (leer)
|   `-- swagger.yaml       # Eingefrorene API-Spec zur Referenz
|-- tests/
|   |-- conftest.py
|   |-- test_client.py
|   |-- test_models.py
|   |-- test_exceptions.py
|   |-- test_validation.py
|   |-- test_api.py
|   `-- test_integration.py    # @pytest.mark.live, skipped by default
|-- examples/
|   |-- 01_basic.py
|   |-- 02_polling.py
|   |-- 03_multi_check.py
|   `-- 04_og_image.py
|-- .github/workflows/
|   |-- ci.yml
|   `-- publish.yml
|-- .gitlab-ci.yml
|-- pyproject.toml
|-- README.md
|-- LICENSE
|-- CHANGELOG.md
|-- KONZEPT.md
`-- .gitignore
```

## 4. Public API (vollstaendig)

### 4.1 Konstruktor

```python
class CheckHost:
    def __init__(
        self,
        apikey: str | None = None,
        *,
        base_url: str = "https://api.check-host.cc",
        timeout: float = 30.0,
        user_agent: str | None = None,
    ) -> None:
        """
        Initialize the Check-Host API client.

        Args:
            apikey: Optional API key. Falls auf ENV CHECK_HOST_API_KEY zurueck.
            base_url: Endpoint-Override (z.B. fuer Tests / Dev).
            timeout: Pro-Request HTTP-Timeout in Sekunden.
            user_agent: Custom User-Agent (Default: check-host-python/<ver>).
        """
```

### 4.2 Utility-Methoden

```python
def myip(self) -> str
def locations(self) -> dict[str, Any]    # rohe API-Antwort (Swagger spezifiziert kein Schema)
def info(self, target: str) -> MinResponseINFO
def whois(self, target: str) -> dict[str, Any]    # rohe API-Antwort (kein Schema)
```

**Hinweis:** `locations()` und `whois()` haben in Swagger 1.2.0 kein definiertes Response-Schema. Wir geben die rohe geparste JSON-Struktur als `dict[str, Any]` zurueck und dokumentieren das Verhalten, anstatt eine Struktur zu erfinden, die wir nicht verifizieren koennen. Sobald die API ein Schema liefert, wrappen wir in einer Minor-Version (z.B. `Location`-Dataclass) — backwards-kompatibel ueber zusaetzliche Methoden.

### 4.3 Monitoring-Methoden (geben `CheckCreated` mit UUID zurueck)

```python
def ping(self, target: str, *,
         region: Sequence[str] | None = None,
         repeat_checks: int = 0,        # 0-120
         timeout: int | None = None
) -> CheckCreated

def dns(self, target: str, *,
        query_method: str = "A",
        region: Sequence[str] | None = None
) -> CheckCreated

def tcp(self, target: str, port: int, *,    # port 1-65535
        region: Sequence[str] | None = None,
        repeat_checks: int = 0,
        timeout: int | None = None
) -> CheckCreated

def udp(self, target: str, port: int, *,
        payload: str | None = None,
        region: Sequence[str] | None = None,
        repeat_checks: int = 0,
        timeout: int | None = None
) -> CheckCreated

def http(self, target: str, *,
         region: Sequence[str] | None = None,
         repeat_checks: int = 0,
         timeout: int | None = None
) -> CheckCreated

def mtr(self, target: str, *,
        region: Sequence[str] | None = None,
        repeat_checks: int = 10,        # MTR: 3-30
        force_ip_version: int | None = None,   # 4|6
        force_protocol: str | None = None      # icmp|udp|tcp
) -> CheckCreated
```

### 4.4 Result-Methoden

```python
def report(self, uuid: str) -> Report:
    """Einmalig fetchen — kann unvollstaendig sein wenn Nodes noch melden."""

def wait_for_report(
    self,
    uuid: str,
    *,
    interval: float = 1.5,
    max_wait: float = 30.0,
    require_complete: bool = True,
) -> Report:
    """Pollt mit festem Intervall (default 1.5s) bis alle Nodes gemeldet
    haben oder max_wait erreicht ist.

    - require_complete=True: Bei Timeout Raise von CheckHostTimeoutError.
    - require_complete=False: Bei Timeout Rueckgabe des aktuellen Report-Stands.
    - Mindest-Intervall 1.0s (API-Hinweis: max 1 Request/Sek je UUID).
    """

def og_image(self, uuid: str) -> bytes:
    """PNG-Bytes (1200x630) der Status-Karte."""

def save_og_image(self, uuid: str, path: str | Path) -> None:
    """Convenience: fetch + write to file."""
```

### 4.5 Context Manager

```python
with CheckHost() as ch:
    task = ch.ping("1.1.1.1")
    result = ch.wait_for_report(task.uuid)
```

## 5. Datenmodelle (Dataclasses)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class MinResponseINFO:
    ip: str
    reverse: str
    iprange: str
    country: str
    city: str
    zipcode: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "MinResponseINFO": ...


@dataclass(frozen=True, slots=True, kw_only=True)
class CheckCreated:
    status: int
    target: str
    method: str
    repeat_checks: int      # JSON: "repeatchecks"
    uuid: str
    report_url: str         # JSON: "reportURL"
    api_url: str            # JSON: "apiURL"
    autodelete: str
    message: str
    success: str

    @property
    def is_success(self) -> bool:
        return self.success.lower() == "success"

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "CheckCreated": ...


@dataclass(frozen=True, slots=True, kw_only=True)
class Report:
    """Wrapper um die rohe /report/{uuid}-Antwort.

    Die API liefert ein Dict, in dem die Schluessel Node-IDs sind und die
    Werte entweder eine Result-Liste oder `null` (wenn der Node noch nicht
    geantwortet hat). Eventuelle zusaetzliche Top-Level-Felder bleiben in
    `raw` erhalten.
    """
    uuid: str
    raw: dict[str, Any]

    @property
    def nodes(self) -> dict[str, list[Any] | None]:
        """Nur die Node-Ergebnisse (filtert nicht-Node-Felder heraus)."""
        return {k: v for k, v in self.raw.items() if isinstance(v, (list, type(None)))}

    @property
    def is_complete(self) -> bool:
        n = self.nodes
        return bool(n) and all(v is not None for v in n.values())

    @property
    def completed_nodes(self) -> dict[str, list[Any]]:
        return {k: v for k, v in self.nodes.items() if v is not None}

    @property
    def pending_nodes(self) -> list[str]:
        return [k for k, v in self.nodes.items() if v is None]
```

## 6. Exception-Hierarchie

```python
class CheckHostError(Exception):
    """Basis fuer alle Lib-Fehler."""

class CheckHostNetworkError(CheckHostError):
    """Netzwerk-/Verbindungsfehler."""

class CheckHostTimeoutError(CheckHostError):
    """wait_for_report ueberschritt max_wait."""

class CheckHostAPIError(CheckHostError):
    """API hat non-2xx zurueckgegeben."""
    status: int
    response: dict[str, Any] | None

class CheckHostBadRequestError(CheckHostAPIError):   # 400
class CheckHostNotFoundError(CheckHostAPIError):     # 404
class CheckHostRateLimitError(CheckHostAPIError):    # 429
class CheckHostServerError(CheckHostAPIError):       # 500

class CheckHostValidationError(CheckHostError, ValueError):
    """Clientseitige Validation (Port-Range, DNS-Type, etc.)."""
```

## 7. Clientseitige Validation

Vor jedem HTTP-Request:

- `target`: nichtleerer String
- `port`: 1-65535 (Swagger spricht von 0-65535 fuer GET, aber 1-65535 fuer POST; konservative Wahl)
- `repeat_checks`:
  - ping/tcp/udp/http: 0-120
  - mtr: 3-30
- `query_method` (DNS): aus Enum-Liste laut Swagger
- `force_ip_version` (MTR): 4 oder 6
- `force_protocol` (MTR): icmp|udp|tcp

Verletzung -> `CheckHostValidationError` (ist auch `ValueError`).

## 8. Konstanten-Modul (`checkhost/regions.py`)

```python
class Continent:
    EUROPE = "EU"
    NORTH_AMERICA = "NA"
    SOUTH_AMERICA = "SA"
    ASIA = "AS"
    AFRICA = "AF"
    OCEANIA = "OC"
    ALL: tuple[str, ...] = (EUROPE, NORTH_AMERICA, SOUTH_AMERICA, ASIA, AFRICA, OCEANIA)

class DNSType:
    A = "A"; AAAA = "AAAA"; MX = "MX"; TXT = "TXT"
    NS = "NS"; CNAME = "CNAME"; SOA = "SOA"
    PTR = "PTR"; SRV = "SRV"; CAA = "CAA"
    DNSKEY = "DNSKEY"; ANY = "ANY"
    # ... vollstaendige Liste aus Swagger

class MTRProtocol:
    ICMP = "icmp"
    UDP = "udp"
    TCP = "tcp"
```

## 9. Field-Naming Strategy

**Python-Signaturen** verwenden snake_case (`repeat_checks`, `force_ip_version`, `query_method`) — PEP 8.
**JSON-Wire-Format** behaelt Swagger-Keys (`repeatchecks`, `forceIPversion`, `querymethod`) durch manuelles Mapping in `from_json`/`to_json` der Modelle und in den API-Methoden.

So bleibt die public API ergonomisch fuer Python-Entwickler und API-treu auf der Leitung.

## 10. HTTP-Layer (`_client.py`)

- Pure Stdlib: `urllib.request`, `urllib.error`, `json`
- `from __future__ import annotations` in allen Modulen (PEP 563 fuer cheaper type hints, einfachere Forward References)
- Auto-Injection: `apikey` wird in POST-Body geschrieben falls nicht explizit gesetzt
- ENV-Fallback: `os.environ.get("CHECK_HOST_API_KEY")` falls Konstruktor-Argument None
- Statuscode-Mapping zu spezifischen Exceptions
- Konfigurierbarer Timeout pro Request
- Helpers: `_post(path, body) -> dict`, `_get(path) -> dict`, `_get_bytes(path) -> bytes`
- Module-level `logger = logging.getLogger("checkhost")` mit DEBUG-Logs fuer Request/Response — Anwender kann subscriben
- Custom User-Agent (`check-host-python/<version>`) immer gesetzt
- HTTPS-Verifikation via `ssl.create_default_context()` (Standard Stdlib-Verhalten)
- `HTTP_PROXY`/`HTTPS_PROXY` Env-Vars werden automatisch respektiert (Stdlib urllib)

## 11. Tests

```python
# Unit-Tests (mocken urlopen ueber unittest.mock)
test_client_post_injects_apikey
test_client_envvar_fallback
test_client_handles_400_404_429_500
test_client_handles_network_error
test_models_roundtrip_json
test_models_completed_pending_split
test_validation_rejects_invalid_port
test_validation_rejects_invalid_dns_type
test_validation_rejects_invalid_mtr_repeats
test_wait_for_report_polls_until_complete
test_wait_for_report_raises_on_timeout
test_og_image_returns_bytes
test_save_og_image_writes_file
test_context_manager_closes_cleanly

# Integration-Tests (markiert @pytest.mark.live, default skipped)
test_live_myip
test_live_locations
test_live_info
test_live_ping_and_poll
test_live_og_image
```

**CI-Matrix:** Python 3.10, 3.11, 3.12, 3.13 auf Linux/macOS/Windows.

## 12. CI/CD

### GitLab (`.gitlab-ci.yml`)

```yaml
stages: [lint, test, build, mirror, publish]

lint:
  image: python:3.12
  script:
    - pip install ruff mypy
    - ruff check .
    - ruff format --check .
    - mypy checkhost/

test:
  parallel:
    matrix:
      - PYTHON_VERSION: ["3.10", "3.11", "3.12", "3.13"]
  image: python:$PYTHON_VERSION
  script:
    - pip install -e .[dev]
    - pytest --cov=checkhost --cov-report=xml

build:
  image: python:3.12
  script:
    - pip install build
    - python -m build
  artifacts:
    paths: [dist/]

mirror_to_github:
  stage: mirror
  rules:
    - if: $CI_COMMIT_TAG
  script:
    - git push --mirror https://$GH_USER:$GH_TOKEN@github.com/Check-Host/python-lib.git
```

### GitHub Actions (`.github/workflows/publish.yml`)

- Trigger: `push` mit Tag matching `v*`
- Build wheel + sdist mit `python -m build`
- Publish zu PyPI via **Trusted Publishing** (OIDC, kein Token in Repo)

## 13. Veroeffentlichungs-Workflow

1. Entwicklung auf `git.check-host.eu/Check-Host/python-lib`
2. MRs reviewen, mergen
3. Tag `v1.0.0` auf `main` setzen
4. GitLab CI: lint -> test -> build -> mirror push -> github
5. GitHub Action triggert auf Tag: PyPI-Upload via Trusted Publishing
6. CHANGELOG aktualisieren
7. Optional: Wheel auch in GitLab Package Registry

## 14. README-Struktur (an nodejs-lib orientiert)

```
# check-host-api

A lightweight, zero-dependency Python 3.10+ SDK for the Check-Host.cc API.

## Features
- Zero runtime dependencies (stdlib only)
- Full Swagger 1.2.0 parity
- Type hints throughout (PEP 561 compatible)
- POST-based requests (no URL-encoding pitfalls)
- Built-in polling helper (wait_for_report)
- Automatic API key injection (constructor or CHECK_HOST_API_KEY env)
- OG-Image fetch & save
- Granular exception hierarchy
- Region/Continent/DNS-Type constants

## Installation
pip install check-host-api

## Quickstart
[Code example: ping + poll + og-image]

## API Reference
- Utilities: myip(), locations(), info(), whois()
- Monitoring: ping(), dns(), tcp(), udp(), http(), mtr()
- Results: report(), wait_for_report(), og_image(), save_og_image()

## Error Handling
[Exception hierarchy + Beispiele]

## Rate Limits
[Wie man einen API-Key bekommt]

## License
Apache-2.0
```

## 15. Roadmap

| Version | Inhalt |
|---|---|
| **1.0.0** | Volle Sync-API, alle Swagger-Endpoints, polling helper, og-image, exception hierarchy, tests, docs |
| 1.1.0 | `AsyncCheckHost` mit asyncio (entweder via `asyncio.to_thread` aus stdlib oder optional `httpx[async]`) |
| 1.2.0 | CLI: `python -m checkhost ping 1.1.1.1` |
| 1.3.0 | Optionale `pydantic`-Schemas via Extra `pip install check-host-api[pydantic]` |
| 2.0.0 | Falls Swagger v2 mit Breaking Changes |

## 16. Entscheidungen (vorab getroffen)

| Frage | Entscheidung | Begruendung |
|---|---|---|
| Package-Name | `check-host-api` | Aligned mit anderen Libs |
| License | Apache-2.0 | Mehrheit + Industriestandard |
| Python-Version | 3.10+ | Moderne Features, anderer Lib-Modernitaetsstandard |
| Async in v1 | Nein | Sauberes Sync zuerst, Async in v1.1.0 |
| Snake_case-Parameter | Ja, Wire-Mapping intern | Pythonic + API-treu |
| OG-Image | Ja | Im Swagger, aber in keiner anderen Lib (Unique Value) |
| Polling-Helper | Ja | Groesster Schmerzpunkt anderer Libs |
| ENV-Var-Key | Ja, `CHECK_HOST_API_KEY` | SDK-Standard |
| Region/DNS-Konstanten | Ja | DX-Aufwertung |
| Clientseitige Validation | Ja, schlank | Schneller fail, klarere Fehler |
| HTTP-Backend | stdlib urllib | Zero deps, matched theme |
| GET-Endpoints (`/ping/{target}` etc.) | NICHT exposen | Swagger empfiehlt POST, andere Libs machen es auch nicht |
| `whois` Return-Typ | `dict[str, Any]` | Swagger spezifiziert kein festes Schema |
| `locations` Return-Typ | `dict[str, Any]` (roh) | Swagger spezifiziert kein Schema — Lieber roh als falsch raten |
| `report` Return-Typ | `Report`-Dataclass (Wrapper um `raw` dict) | Bietet `.is_complete`, `.completed_nodes`, `.pending_nodes`, raw bleibt zugaenglich |
| Polling-Strategie | Festes Intervall (default 1.5s) | Vorhersagbar, respektiert API-Hinweis "1 Req/Sek" |
| Logging | `logging.getLogger("checkhost")` | Standard-Pattern, kein Auto-Setup |
| swagger.yaml im Wheel | Ja, `checkhost/swagger.yaml` | Referenz fuer Anwender / Codegen |

## 17. Quickstart-Codebeispiel

```python
from checkhost import CheckHost
from checkhost.regions import Continent, DNSType

with CheckHost() as ch:
    # Geolocation
    info = ch.info("check-host.cc")
    print(f"{info.ip} -> {info.city}, {info.country}")

    # Ping ueber Europa + Nordamerika, 3 Pakete je Node
    task = ch.ping(
        "1.1.1.1",
        region=[Continent.EUROPE, Continent.NORTH_AMERICA],
        repeat_checks=3,
    )
    print(f"Task UUID: {task.uuid}")

    # Auf vollstaendige Ergebnisse warten (oder Timeout)
    report = ch.wait_for_report(task.uuid, max_wait=20.0)
    print(f"Completed nodes: {len(report.completed_nodes)}")

    # OG-Bild speichern
    ch.save_og_image(task.uuid, "./status.png")

    # DNS-MX gegen Europa
    dns_task = ch.dns(
        "check-host.cc",
        query_method=DNSType.MX,
        region=[Continent.EUROPE],
    )
    dns_report = ch.wait_for_report(dns_task.uuid)
```

## 18. Risikoanalyse / Annahmen

| Risiko | Mitigation |
|---|---|
| API liefert unerwartetes JSON-Schema (z.B. fehlendes Feld) | `from_json` mit `data.get(..., default)`, optionale Felder, raw-dict in Models |
| Rate-Limits bei CI-Integration-Tests | Tests `@pytest.mark.live` default skipped, ueber Env aktivierbar |
| GitHub-Mirror schlaegt fehl | Mirror-Step `allow_failure: false`, separate Pipeline |
| Trusted Publishing nicht konfiguriert | Fallback auf API-Token in GH-Secret bis Setup |
| swagger.yaml veraltet | CHANGELOG dokumentiert API-Stand; CI prueft `swagger.yaml`-Hash gegen letzten Stand |

## 19. Naechste Schritte (nach Konzept-Freigabe)

1. Repo `python-lib` auf `git.check-host.eu/Check-Host` anlegen
2. Skeleton: `pyproject.toml`, `LICENSE`, `.gitignore`, `README.md`
3. Implementierung in der Reihenfolge: `_exceptions` -> `_models` -> `_validation` -> `regions` -> `_client` -> `api` -> `__init__`
4. Unit-Tests parallel zur Implementierung
5. Integration-Tests gegen Live-API
6. Examples schreiben
7. CI einrichten
8. v0.1.0 alpha Release zum internen Test
9. Feedback einarbeiten
10. v1.0.0 mit Mirror+PyPI

---

## Anhang A: Endpoint-Mapping (Swagger -> Methode)

| Swagger | Methode | HTTP |
|---|---|---|
| `POST /info` | `info(target)` | POST |
| `POST /whois` | `whois(target)` | POST |
| `GET /myip` | `myip()` | GET |
| `GET /locations` | `locations()` | GET |
| `POST /ping` | `ping(target, **opts)` | POST |
| `POST /dns` | `dns(target, **opts)` | POST |
| `POST /tcp` | `tcp(target, port, **opts)` | POST |
| `POST /udp` | `udp(target, port, **opts)` | POST |
| `POST /http` | `http(target, **opts)` | POST |
| `POST /mtr` | `mtr(target, **opts)` | POST |
| `GET /report/{uuid}` | `report(uuid)` / `wait_for_report(uuid)` | GET |
| `GET /report/{uuid}/og-image` | `og_image(uuid)` / `save_og_image(uuid, path)` | GET |
| `GET /info/{target}` | nicht exposed (POST bevorzugt) | - |
| `GET /whois/{target}` | nicht exposed | - |
| `GET /ping/{target}` | nicht exposed | - |
| `GET /dns/{target}/{methoad}` | nicht exposed | - |
| `GET /tcp/{target}/{port}` | nicht exposed | - |

## Anhang B: Vergleich zu existierenden Libs

| Feature | nodejs | php | go | java | **python (this)** |
|---|---|---|---|---|---|
| API-Parität zu Swagger | Hoch | Hoch | Hoch | Hoch | **Vollstaendig** |
| Zero deps | Ja | Ja | Ja | Nein (Jackson) | **Ja (stdlib)** |
| Typed Models | Nein | Nein | Ja | Ja | **Ja (dataclasses + Type-Hints)** |
| Custom Exceptions | Generic Error | `CheckHostException` | Sentinel errors | `CheckHostException` | **Granulare Hierarchie (5 Subklassen)** |
| Polling-Helper | Nein | Nein | Nein | Nein | **Ja (`wait_for_report`)** |
| og-image | Nein | Nein | Nein | Nein | **Ja** |
| ENV-Var Key | Nein | Nein | Nein | Nein | **Ja** |
| Region/DNS-Konstanten | Nein | Nein | Nein | Nein | **Ja** |
| Clientseitige Validation | Minimal | Minimal | Minimal | Minimal | **Ja, granular** |
| Context Manager | Nein | Nein | Nein | Nein | **Ja (`with` block)** |
| Async-Support | Nein (`Promise` only) | Nein | Nein | Nein | **Geplant v1.1.0** |
| Logging | Nein | Nein | Nein | Nein | **Ja (`logging.getLogger("checkhost")`)** |
| License | CC0-1.0 | ISC | Apache-2.0 | Apache-2.0 | **Apache-2.0** |

---

## Anhang C: Self-Review-Notizen (v1 -> v2)

Folgende Punkte wurden im Self-Review identifiziert und korrigiert:

1. **`locations()` Return-Typ:** v1 schlug `dict[str, Location]` vor — Swagger gibt aber kein Schema, das waere praeskriptiv und falsch ratsbar. v2: `dict[str, Any]` (roh).
2. **`Report`-Model:** v1 hatte feste `nodes`-Struktur. v2 wrappt um `raw` und exponiert `nodes` als gefilterte Property, damit weitere Top-Level-Felder der API nicht verloren gehen.
3. **Polling-Semantik:** v1 sagte unklar "exponential backoff". v2 macht explizit: festes Intervall (1.5s default, Mindest 1.0s) wegen API-Hinweis "1 Req/Sek je UUID".
4. **`from __future__ import annotations`:** in v1 nicht erwaehnt; v2 fordert es in allen Modulen.
5. **Logging:** in v1 vergessen; v2 fuegt `logging.getLogger("checkhost")` als Standard-Pattern hinzu.
6. **swagger.yaml-Distribution:** v1 unklar; v2 inkludiert die Spec in `checkhost/swagger.yaml` im Wheel.
7. **`Location`-Dataclass:** wurde aus v1.0 entfernt — kommt zurueck wenn API ein Schema liefert.
8. **HTTPS-Verifikation/Proxies:** in v1 nicht adressiert; v2 dokumentiert Standard-Verhalten der Stdlib.
9. **`wait_for_report` mit `require_complete=False`:** klargestellt — gibt aktuellen Stand zurueck statt Raise.

Diese Aenderungen verbessern Ehrlichkeit gegenueber unspezifizierten Schemas und Robustheit gegen API-Antwort-Aenderungen.
