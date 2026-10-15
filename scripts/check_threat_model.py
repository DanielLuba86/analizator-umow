"""Sprawdza, że każde zagrożenie w docs/threat-model.md wskazuje istniejący test lub job CI.

Odwołania w tabeli zagrożeń (w backtickach):
- `tests/<ścieżka>.py::<nazwa>` — test backendu; musi być w `pytest --collect-only -q`,
- `frontend/tests/<plik>::<nazwa testu>` — test Vitest; plik musi zawierać `test("<nazwa testu>"`,
- `ci:<job>` — job w .github/workflows/ci.yml.

Uruchamiany z katalogu backend/ (tam działa pytest):
`uv run python ../scripts/check_threat_model.py`.
Kolekcja testów nie łączy się z bazą, więc DATABASE_URL może być dowolny.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "threat-model.md"
CI = ROOT / ".github" / "workflows" / "ci.yml"

ROW = re.compile(r"^\|\s*(T\d+)\s*\|")
CODE = re.compile(r"`([^`]+)`")
BACKEND = re.compile(r"tests/[\w/]+\.py(::\w+)+")
FRONTEND = re.compile(r"frontend/tests/([\w.]+)::(.+)")
CI_JOB = re.compile(r"ci:([\w-]+)")


def collected_backend_tests() -> set[str]:
    env = {**os.environ}
    env.setdefault("DATABASE_URL", "postgresql+psycopg://u:p@localhost:1/db")
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=ROOT / "backend",
        env=env,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return {line.split("[", 1)[0] for line in out.splitlines() if "::" in line}


def ci_jobs() -> set[str]:
    jobs: set[str] = set()
    in_jobs = False
    for line in CI.read_text(encoding="utf-8").splitlines():
        if line.startswith("jobs:"):
            in_jobs = True
        elif in_jobs and re.match(r"^  [\w-]+:\s*$", line):
            jobs.add(line.strip().rstrip(":"))
    return jobs


def row_errors(line: str, backend: set[str], jobs: set[str]) -> list[str]:
    """Błędy jednego wiersza tabeli; każde odwołanie musi mieć poprawną postać i istnieć."""
    errors = []
    refs = 0
    for code in CODE.findall(line):
        if code.startswith("tests/"):
            refs += 1
            if not BACKEND.fullmatch(code):
                errors.append(f"niepoprawne odwołanie {code}")
            elif code not in backend:
                errors.append(f"brak testu {code}")
        elif code.startswith("frontend/tests/"):
            refs += 1
            m = FRONTEND.fullmatch(code)
            path = ROOT / "frontend" / "tests" / m.group(1) if m else None
            body = path.read_text(encoding="utf-8") if path and path.exists() else ""
            if not m or f'test("{m.group(2)}"' not in body:
                errors.append(f"brak testu {code}")
        elif code.startswith("ci:"):
            refs += 1
            m = CI_JOB.fullmatch(code)
            if not m or m.group(1) not in jobs:
                errors.append(f"brak joba CI {code}")
    if refs == 0:
        errors.append("zagrożenie bez testu")
    return errors


def main() -> int:
    if not DOC.exists():
        print(f"brak pliku {DOC.relative_to(ROOT)}")
        return 1
    backend = collected_backend_tests()
    if not backend:
        print("pytest --collect-only nie zwrócił żadnych testów")
        return 1
    jobs = ci_jobs()
    errors: list[str] = []
    rows = 0
    for n, line in enumerate(DOC.read_text(encoding="utf-8").splitlines(), 1):
        m = ROW.match(line)
        if not m:
            continue
        rows += 1
        errors += [f"{m.group(1)} (linia {n}): {e}" for e in row_errors(line, backend, jobs)]
    if rows == 0:
        errors.append("tabela zagrożeń jest pusta")
    for e in errors:
        print(e)
    print(f"zagrożeń: {rows}, błędów: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
