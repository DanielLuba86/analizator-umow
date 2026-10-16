"""Sprawdza dokumentację: 12 sekcji arc42, brak TODO/TBD, poprawne diagramy Mermaid, linki względne.

Uruchomienie z korzenia repo: `python3 scripts/check_docs.py`.
Diagramy parsuje mermaid-cli (`npx -y @mermaid-js/mermaid-cli@11`, wymaga Node).
`--skip-mermaid` pomija ten krok (szybkie sprawdzenie lokalne bez przeglądarki).
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARC42 = ROOT / "docs" / "arc42"
PUPPETEER_CONFIG = ROOT / "scripts" / "puppeteer-config.json"
MERMAID_CLI = "@mermaid-js/mermaid-cli@11"

SECTIONS = [
    "01-wprowadzenie-i-cele.md",
    "02-ograniczenia.md",
    "03-kontekst-i-zakres.md",
    "04-strategia-rozwiazania.md",
    "05-widok-blokow-budujacych.md",
    "06-widok-czasu-wykonania.md",
    "07-wdrozenie.md",
    "08-koncepcje-przekrojowe.md",
    "09-decyzje.md",
    "10-wymagania-jakosciowe.md",
    "11-ryzyka-i-dlug-techniczny.md",
    "12-slownik.md",
]

PLACEHOLDER = re.compile(r"\b(TODO|TBD)\b")
MERMAID = re.compile(r"^([ \t]*)```mermaid[ \t]*\n(.*?)^\1```[ \t]*$", re.S | re.M)
LINK = re.compile(r"\]\((<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\)")


def mermaid_blocks(text: str) -> list[str]:
    """Bloki ```mermaid, także z wcięciem (w liście) i spacjami po nazwie języka."""
    blocks = []
    for indent, body in MERMAID.findall(text):
        lines = body.splitlines()
        blocks.append("\n".join(ln[len(indent) :] if ln.startswith(indent) else ln for ln in lines))
    return blocks


def links(text: str) -> list[str]:
    """Cele linków Markdown poza diagramami; `<…>` i tytuły w cudzysłowie są obsługiwane."""
    return [t[1:-1] if t.startswith("<") else t for t in LINK.findall(MERMAID.sub("", text))]


def documents() -> list[Path]:
    return sorted((ROOT / "docs").rglob("*.md")) + [ROOT / "README.md"]


def check_sections() -> list[str]:
    errors = [f"brak sekcji arc42: {name}" for name in SECTIONS if not (ARC42 / name).exists()]
    if not (ARC42 / "README.md").exists():
        errors.append("brak spisu docs/arc42/README.md")
    for path in sorted(ARC42.glob("*.md")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if PLACEHOLDER.search(line):
                errors.append(f"{path.relative_to(ROOT)}:{n}: zawiera TODO/TBD")
    return errors


def check_links() -> list[str]:
    errors = []
    for path in documents():
        for target in links(path.read_text(encoding="utf-8")):
            if re.match(r"^[a-z]+:", target) or target.startswith("#"):
                continue
            file_part = target.split("#", 1)[0]
            if file_part and not (path.parent / file_part).resolve().exists():
                errors.append(f"{path.relative_to(ROOT)}: martwy link {target}")
    return errors


MERMAID_TIMEOUT_S = 120


def check_mermaid() -> list[str]:
    errors = []
    blocks = [
        (path, i, block)
        for path in documents()
        for i, block in enumerate(mermaid_blocks(path.read_text(encoding="utf-8")), 1)
    ]
    with tempfile.TemporaryDirectory() as tmp:
        for path, i, block in blocks:
            src = Path(tmp) / "diagram.mmd"
            src.write_text(block, encoding="utf-8")
            cmd = ["npx", "-y", MERMAID_CLI, "-q", "-i", str(src), "-o", str(Path(tmp) / "out.svg")]
            if PUPPETEER_CONFIG.exists():
                cmd += ["-p", str(PUPPETEER_CONFIG)]
            try:
                run = subprocess.run(  # noqa: S603
                    cmd, capture_output=True, text=True, check=False, timeout=MERMAID_TIMEOUT_S
                )
            except subprocess.TimeoutExpired:
                errors.append(f"{path.relative_to(ROOT)}: diagram {i}: timeout mermaid-cli")
                continue
            if run.returncode != 0:
                detail = (run.stderr or run.stdout).strip().splitlines()
                errors.append(
                    f"{path.relative_to(ROOT)}: diagram {i} nie parsuje się: {detail[:3]}"
                )
    print(f"diagramów Mermaid: {len(blocks)}")
    return errors


def main() -> int:
    errors = check_sections() + check_links()
    if "--skip-mermaid" not in sys.argv:
        errors += check_mermaid()
    for e in errors:
        print(e)
    print(f"błędów: {len(errors)}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
