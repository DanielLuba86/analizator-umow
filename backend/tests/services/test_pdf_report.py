"""Raport PDF dla klienta: generowany z zamrożonej treści eksportu (JSON)."""

from io import BytesIO
from typing import Any

from pypdf import PdfReader

from app.services.pdf_report import render_report

FIRM = "Kancelaria Testowa Żółw i Wspólnicy"
QUOTE = "Najemca zapłaci karę umowną w wysokości 2% czynszu za każdy dzień opóźnienia."


def finding(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "typ": "kara",
        "teza": "Kara umowna bez górnego limitu.",
        "cytat": QUOTE,
        "fragment_id": 1,
        "start": 0,
        "end": len(QUOTE),
        "poziom_ryzyka": "wysokie",
        "uzasadnienie": "Kara może przewyższyć wartość umowy.",
    }
    return base | kw


def content(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "analysis_id": 7,
        "version_id": 3,
        "version_nr": 2,
        "contract": {"id": 5, "title": "Umowa najmu – lokal w Łodzi", "kind": "najem"},
        "status": "done",
        "official": False,
        "incomplete": False,
        "approved_by": 1,
        "generated_at": "2026-10-16T12:00:00+00:00",
        "findings": [finding()],
    }
    return base | kw


def pages(pdf: bytes) -> list[str]:
    """Tekst stron z ujednoliconymi odstępami (łamanie wierszy dzieli zdania)."""
    reader = PdfReader(BytesIO(pdf))
    return [" ".join((p.extract_text() or "").split()) for p in reader.pages]


def text(pdf: bytes) -> str:
    return " ".join(pages(pdf))


def render(c: dict[str, Any], approver: str | None = "prawnik-1") -> bytes:
    return render_report(c, approver=approver, firm_name=FIRM)


def test_renders_pdf_with_polish_contract_data() -> None:
    pdf = render(content())
    assert pdf.startswith(b"%PDF")
    t = text(pdf)
    assert FIRM in t
    assert "Raport z analizy umowy" in t
    assert "Umowa najmu – lokal w Łodzi" in t
    assert "najem" in t and "wersja 2" in t
    assert QUOTE in t
    assert "Kara umowna bez górnego limitu." in t
    assert "Kara może przewyższyć wartość umowy." in t


def test_unofficial_report_has_draft_banner() -> None:
    t = text(render(content(official=False)))
    assert "WERSJA ROBOCZA" in t
    assert "nie stanowi opinii prawnej" in t
    assert "Opinia zatwierdzona" not in t


def test_official_report_names_approving_lawyer() -> None:
    t = text(render(content(official=True), approver="mec-nowak"))
    assert "Opinia zatwierdzona przez prawnika: mec-nowak" in t
    assert "WERSJA ROBOCZA" not in t


def test_incomplete_report_is_flagged() -> None:
    assert "Analiza niepełna" in text(render(content(incomplete=True)))
    assert "Analiza niepełna" not in text(render(content(incomplete=False)))


def test_findings_ordered_from_highest_risk() -> None:
    c = content(
        findings=[
            finding(teza="Teza bez oceny ryzyka.", poziom_ryzyka=None, typ="strona"),
            finding(teza="Teza o niskim ryzyku."),
            finding(teza="Teza o wysokim ryzyku.", poziom_ryzyka="wysokie"),
            finding(teza="Teza o średnim ryzyku.", poziom_ryzyka="średnie"),
        ]
    )
    c["findings"][1]["poziom_ryzyka"] = "niskie"
    t = text(render(c))
    order = [
        t.index("Teza o wysokim ryzyku."),
        t.index("Teza o średnim ryzyku."),
        t.index("Teza o niskim ryzyku."),
        t.index("Teza bez oceny ryzyka."),
    ]
    assert order == sorted(order)


def test_no_findings_is_stated() -> None:
    assert "Agent nie zgłosił żadnych tez." in text(render(content(findings=[])))


def test_disclaimer_and_page_number_on_every_page() -> None:
    many = [finding(teza=f"Teza numer {i}.") for i in range(40)]
    ps = pages(render(content(findings=many)))
    assert len(ps) > 1
    for i, p in enumerate(ps, start=1):
        assert "nie zastępuje porady prawnej" in p
        assert f"Strona {i} z {len(ps)}" in p


def test_untrusted_text_is_rendered_literally() -> None:
    """Treść od agenta i z umowy kontrahenta nie jest interpretowana jako znaczniki."""
    hostile = "**pogrubienie** <b>znacznik</b> --przekreślenie-- __podkreślenie__"
    t = text(render(content(findings=[finding(teza=hostile, cytat=hostile)])))
    assert hostile in t


def test_long_unbroken_quote_does_not_fail() -> None:
    long_word = "x" * 400
    assert render(content(findings=[finding(cytat=long_word)])).startswith(b"%PDF")
