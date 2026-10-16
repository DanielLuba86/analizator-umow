"""Raport PDF dla klienta, generowany z zamrożonej treści eksportu (`exports.content`).

Teza, cytat i uzasadnienie pochodzą od agenta i z umowy kontrahenta, więc są danymi nieufnymi:
trafiają do PDF wyłącznie jako zwykły tekst (`markdown=False`), bez linków i obrazów.
"""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos

_FONTS = Path(__file__).parent / "fonts"
_FONT = "DejaVu"
_RISK_ORDER = {"wysokie": 0, "średnie": 1, "niskie": 2}
_RISK_COLORS = {"wysokie": (176, 0, 32), "średnie": (184, 110, 0), "niskie": (40, 110, 60)}
_GREY = (90, 90, 90)
DISCLAIMER = (
    "Raport sporządzono przy wsparciu narzędzia AI. Wspiera, ale nie zastępuje porady prawnej."
)


class _Report(FPDF):
    def footer(self) -> None:
        self.set_y(-15)
        self.set_font(_FONT, "", 7)
        self.set_text_color(*_GREY)
        self.cell(0, 4, DISCLAIMER, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.cell(0, 4, f"Strona {self.page_no()} z {{nb}}", align="C")


def _date(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%d.%m.%Y")


def _paragraph(pdf: FPDF, text: str, size: float, style: str = "", h: float = 5.5) -> None:
    pdf.set_font(_FONT, style, size)
    pdf.multi_cell(0, h, text, markdown=False, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _banner(pdf: FPDF, text: str, rgb: tuple[int, int, int]) -> None:
    pdf.set_fill_color(*rgb)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(_FONT, "B", 10)
    pdf.multi_cell(
        0, 5.5, text, fill=True, align="C", padding=3, new_x=XPos.LMARGIN, new_y=YPos.NEXT
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)


def _finding(pdf: FPDF, nr: int, f: Mapping[str, Any]) -> None:
    risk = f.get("poziom_ryzyka")
    pdf.set_text_color(*_RISK_COLORS.get(risk or "", _GREY))
    pdf.set_font(_FONT, "B", 9)
    label = f"Ryzyko: {risk}" if risk else "Ryzyko: bez oceny"
    pdf.cell(0, 5, f"{nr}. {f['typ']} · {label}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)
    _paragraph(pdf, str(f["teza"]), 10.5, "B")
    pdf.set_fill_color(242, 242, 242)
    pdf.set_font(_FONT, "I", 9.5)
    pdf.multi_cell(
        0,
        5,
        f"„{f['cytat']}”",
        markdown=False,
        align="L",
        fill=True,
        padding=(2, 3),
        new_x=XPos.LMARGIN,
        new_y=YPos.NEXT,
    )
    if f.get("uzasadnienie"):
        pdf.ln(1)
        _paragraph(pdf, str(f["uzasadnienie"]), 9.5)
    pdf.ln(4)


def render_report(content: Mapping[str, Any], *, approver: str | None, firm_name: str) -> bytes:
    """`approver` — login prawnika, który zatwierdził eksport (None: konto usunięte)."""
    pdf = _Report(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.add_font(_FONT, "", str(_FONTS / "DejaVuSans.ttf"))
    pdf.add_font(_FONT, "B", str(_FONTS / "DejaVuSans-Bold.ttf"))
    pdf.add_font(_FONT, "I", str(_FONTS / "DejaVuSans-Oblique.ttf"))
    pdf.set_title("Raport z analizy umowy")
    pdf.add_page()

    pdf.set_text_color(*_GREY)
    _paragraph(pdf, firm_name, 9)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    _paragraph(pdf, "Raport z analizy umowy", 18, "B", h=9)
    contract = content["contract"]
    _paragraph(pdf, str(contract["title"]), 12, "B", h=6.5)
    pdf.set_text_color(*_GREY)
    _paragraph(
        pdf,
        f"Rodzaj: {contract['kind']} · wersja {content['version_nr']} · "
        f"data sporządzenia: {_date(content['generated_at'])} · "
        f"nr analizy: {content['analysis_id']}",
        9,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    if content["official"]:
        _banner(pdf, f"Opinia zatwierdzona przez prawnika: {approver or 'nieznany'}", (40, 90, 60))
    else:
        _banner(pdf, "WERSJA ROBOCZA – dokument nie stanowi opinii prawnej", (176, 0, 32))
    if content["incomplete"]:
        _banner(
            pdf,
            "Analiza niepełna: agent nie dokończył przeglądu umowy, lista tez może być niepełna.",
            (184, 110, 0),
        )

    findings = sorted(
        content["findings"], key=lambda f: _RISK_ORDER.get(f.get("poziom_ryzyka") or "", 3)
    )
    _paragraph(pdf, f"Ustalenia ({len(findings)})", 13, "B", h=8)
    pdf.ln(1)
    if not findings:
        _paragraph(pdf, "Agent nie zgłosił żadnych tez.", 10)
    for nr, f in enumerate(findings, start=1):
        _finding(pdf, nr, f)
    return bytes(pdf.output())
