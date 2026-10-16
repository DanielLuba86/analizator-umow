"""Test E2E na stosie docker compose: to, czego nie widzą testy jednostkowe.

Sprawdza start całego stosu, logowanie za nginx (Origin, limit prób), analizę bez klucza API
(fail closed → kwarantanna) oraz odporność nginx na zmianę adresu i brak backendu.

Uruchomienie z katalogu repozytorium: `python3 scripts/e2e_compose.py`.
Stos działa jako osobny projekt compose (`E2E_PROJECT`, domyślnie `analizator-e2e`) na porcie
`APP_PORT` (domyślnie 18080), z plikiem env zbudowanym z `.env.example` — bez klucza API, więc
test nic nie kosztuje i nie dotyka lokalnego `.env` ani działającej aplikacji.
`E2E_KEEP=1` zostawia stos po teście.
"""

import http.cookiejar
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PROJECT = os.environ.get("E2E_PROJECT", "analizator-e2e")
PORT = int(os.environ.get("APP_PORT", "18080"))
BASE = f"http://localhost:{PORT}"
PASSWORD = "e2e-haslo-asystenta"  # noqa: S105 - konto demo w jednorazowym stosie testowym
CONTRACT = """# UMOWA NAJMU (test E2E, dane fikcyjne)

## § 1. Czynsz

Najemca płaci czynsz 2 000 zł miesięcznie do 10. dnia miesiąca.

## § 2. Kary

Za każdy dzień opóźnienia Najemca zapłaci karę umowną 50 zł.
"""


class E2EFailure(Exception):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise E2EFailure(message)


def write_env_file(path: Path) -> None:
    """`.env.example` z hasłem konta demo i portem; klucze API zostają puste."""
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    overrides = {"SEED_ASSISTANT_PASSWORD": PASSWORD, "APP_PORT": str(PORT)}
    out = []
    for line in lines:
        key = line.split("=", 1)[0]
        check(
            not (key.endswith("API_KEY") and line.strip() != f"{key}="),
            f".env.example ma ustawiony {key} — test E2E nie może używać klucza API",
        )
        out.append(f"{key}={overrides.pop(key)}" if key in overrides else line)
    out += [f"{k}={v}" for k, v in overrides.items()]
    out.append(f"ENV_FILE={path}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


class Stack:
    def __init__(self, env_file: Path) -> None:
        self.env_file = env_file

    def compose(self, *args: str, check_rc: bool = True) -> str:
        cmd = ["docker", "compose", "-p", PROJECT, "--env-file", str(self.env_file), *args]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)  # noqa: S603
        if check_rc and r.returncode != 0:
            raise E2EFailure(f"{' '.join(args)}: kod {r.returncode}\n{r.stdout}{r.stderr}")
        return r.stdout

    def container(self, service: str) -> str:
        cid = self.compose("ps", "-q", service).strip()
        check(bool(cid), f"brak kontenera usługi {service}")
        return cid

    def running(self, service: str) -> bool:
        return bool(self.compose("ps", "-q", "--status", "running", service).strip())

    def ip(self, service: str) -> str:
        return docker(
            "inspect",
            "-f",
            "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
            self.container(service),
        ).strip()


def docker(*args: str) -> str:
    r = subprocess.run(["docker", *args], capture_output=True, text=True)  # noqa: S603, S607
    if r.returncode != 0:
        raise E2EFailure(f"docker {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


class Http:
    """Klient z ciasteczkami; zwraca (status, nagłówki, ciało) także dla 4xx/5xx."""

    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def request(
        self, method: str, path: str, body: Any = None, origin: str | None = None
    ) -> tuple[int, dict[str, str], str]:
        headers = {"Content-Type": "application/json"} if body is not None else {}
        if origin is not None:
            headers["Origin"] = origin
        data = json.dumps(body).encode() if body is not None else None
        # BASE to stały http://localhost — schemat nie pochodzi z danych wejściowych
        req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)  # noqa: S310
        try:
            with self.opener.open(req, timeout=10) as r:
                return r.status, dict(r.headers), r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, dict(e.headers), e.read().decode()
        except OSError as e:  # połączenie zerwane: nginx jeszcze nie słucha
            return 0, {}, str(e)

    def login(self, password: str, origin: str = BASE) -> int:
        body = {"login": "asystent", "password": password}
        return self.request("POST", "/api/auth/login", body, origin=origin)[0]


def wait_for(what: str, probe: Callable[[], bool], timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if probe():
            return
        time.sleep(1)
    raise E2EFailure(f"nie doczekano się: {what} (po {timeout_s:.0f} s)")


def health_ok(web: Http) -> bool:
    status, _, body = web.request("GET", "/api/health")
    return status == 200 and json.loads(body).get("status") == "ok"


def scenario_start(stack: Stack, web: Http) -> None:
    stack.compose("up", "-d", "--build", "--wait", "--wait-timeout", "300")
    wait_for("/api/health = ok", lambda: health_ok(web), 30)
    status, headers, _ = web.request("GET", "/")
    check(status == 200, f"/ zwraca {status}")
    check("frame-ancestors 'none'" in headers.get("Content-Security-Policy", ""), "brak CSP")


def scenario_login(stack: Stack, web: Http) -> None:
    stack.compose("exec", "-T", "backend", "python", "-m", "app.repo.seed")
    status = Http().login(PASSWORD, origin="http://evil.example")
    check(status == 403, f"logowanie z obcym Origin: {status}, oczekiwano 403")
    status = web.login(PASSWORD)
    check(status == 204, f"logowanie: {status}, oczekiwano 204")


def scenario_analysis_without_api_key(web: Http) -> None:
    contract = {"title": "Najem E2E", "kind": "najem", "source": "kontrahent", "text": CONTRACT}
    status, _, body = web.request("POST", "/api/contracts", contract, origin=BASE)
    check(status == 201, f"dodanie umowy: {status} {body}")
    version_id = json.loads(body)["version_id"]
    status, _, body = web.request("POST", f"/api/versions/{version_id}/analyses", {}, origin=BASE)
    check(status == 202, f"start analizy: {status} {body}")
    analysis_id = json.loads(body)["analysis_id"]
    report: dict[str, Any] = {}

    def finished() -> bool:
        nonlocal report
        report = json.loads(web.request("GET", f"/api/analyses/{analysis_id}")[2])
        return report.get("status") not in ("queued", "running")

    wait_for("koniec analizy", finished, 120)
    check(
        (report["status"], report["reason"]) == ("quarantined", "klasyfikator_niedostępny"),
        f"bez klucza API analiza ma trafić do kwarantanny, jest: {report}",
    )
    check(report["findings"] == [], "raport w kwarantannie nie może pokazywać tez")


def scenario_backend_new_ip(stack: Stack, web: Http) -> None:
    """Nowy kontener backendu z innym IP; nginx ma go znaleźć bez restartu."""
    old_ip = stack.ip("backend")
    network = f"{PROJECT}_default"
    image = docker("inspect", "-f", "{{.Config.Image}}", stack.container("backend")).strip()
    stack.compose("rm", "-sf", "backend")
    placeholder = docker(  # zajmuje zwolniony adres, więc nowy backend dostanie inny
        "run", "-d", "--rm", "--network", network, "--entrypoint", "sleep", image, "600"
    ).strip()
    try:
        stack.compose("up", "-d", "--no-deps", "--wait", "--wait-timeout", "120", "backend")
        new_ip = stack.ip("backend")
        check(new_ip != old_ip, f"backend dostał ten sam adres {old_ip}; test niemiarodajny")
        wait_for(f"API po zmianie IP backendu {old_ip} → {new_ip}", lambda: health_ok(web), 20)
    finally:
        docker("rm", "-f", placeholder)


def scenario_nginx_without_backend(stack: Stack, web: Http) -> None:
    stack.compose("stop", "backend")
    stack.compose("restart", "frontend")
    wait_for("strona główna bez backendu", lambda: web.request("GET", "/")[0] == 200, 20)
    check(stack.running("frontend"), "nginx nie działa po starcie bez backendu")
    status = web.request("GET", "/api/health")[0]
    check(status == 502, f"API bez backendu: {status}, oczekiwano 502")
    stack.compose("up", "-d", "--no-deps", "--wait", "--wait-timeout", "120", "backend")
    wait_for("API po powrocie backendu", lambda: health_ok(web), 20)


def scenario_login_rate_limit() -> None:
    """Na końcu: limit blokuje logowanie z tego adresu przez minutę."""
    web = Http()
    statuses = [web.login("zle-haslo") for _ in range(20)]
    check(statuses[0] == 401, f"pierwsze błędne logowanie: {statuses[0]}, oczekiwano 401")
    check(429 in statuses, f"brak 429 po 20 błędnych logowaniach: {statuses}")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        env_file = Path(tmp) / "e2e.env"
        write_env_file(env_file)
        stack, web = Stack(env_file), Http()
        steps: list[tuple[str, Callable[[], None]]] = [
            ("start stosu", lambda: scenario_start(stack, web)),
            ("logowanie za nginx", lambda: scenario_login(stack, web)),
            ("analiza bez klucza API", lambda: scenario_analysis_without_api_key(web)),
            ("nowy adres IP backendu", lambda: scenario_backend_new_ip(stack, web)),
            ("nginx bez backendu", lambda: scenario_nginx_without_backend(stack, web)),
            ("limit prób logowania", scenario_login_rate_limit),
        ]
        try:
            for name, step in steps:
                started = time.monotonic()
                step()
                print(f"OK   {name} ({time.monotonic() - started:.0f} s)", flush=True)
        except E2EFailure as e:
            print(f"BŁĄD {name}: {e}", file=sys.stderr)
            print(stack.compose("logs", "--no-color", "--tail=150", check_rc=False))
            return 1
        finally:
            if os.environ.get("E2E_KEEP") != "1":
                stack.compose("down", "-v", "--remove-orphans", check_rc=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
