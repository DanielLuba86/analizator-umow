import pytest

from app.domain.fragments import split_into_fragments
from app.domain.quotes import QuoteMatch, QuoteNotFound, verify_quote

TEXT = "§ 9. Kara\n\n1. Najemca zapłaci karę umowną w wysokości 500 zł.\n"
FRS = split_into_fragments(TEXT)

TEXT2 = (
    "§ 1. Zakres\n\n"
    "1. Pierwszy ustęp zawiera tekst alfa.\n\n"
    "2. Drugi ustęp zawiera tekst beta,\n   który ma wcięcie i ciąg dalszy.\n"
)
FRS2 = split_into_fragments(TEXT2)


def test_fixture_fragments() -> None:
    assert [f.id for f in FRS] == ["f001"]
    assert [f.id for f in FRS2] == ["f001", "f002"]


def test_exact_quote_accepted_with_original_offsets() -> None:
    q = "zapłaci karę umowną w wysokości 500 zł"
    m = verify_quote(TEXT, FRS, "f001", q)
    assert isinstance(m, QuoteMatch)
    assert TEXT[m.start : m.end] == q


def test_whitespace_differences_are_tolerated() -> None:
    m = verify_quote(TEXT, FRS, "f001", "zapłaci   karę\numowną w wysokości")
    assert m.start == TEXT.index("zapłaci")
    assert TEXT[m.start : m.end] == "zapłaci karę umowną w wysokości"


def test_text_whitespace_runs_map_to_original_span() -> None:
    text = "§ 1. X\n\n1. Najemca   zapłaci\n\n  karę umowną   w terminie.\n"
    m = verify_quote(text, split_into_fragments(text), "f001", "zapłaci karę umowną w terminie.")
    assert text[m.start : m.end] == "zapłaci\n\n  karę umowną   w terminie."


def test_quote_ends_are_stripped_and_span_has_no_trailing_whitespace() -> None:
    q = "  \n zapłaci karę umowną w wysokości \t\n"
    m = verify_quote(TEXT, FRS, "f001", q)
    assert TEXT[m.start : m.end] == "zapłaci karę umowną w wysokości"


def test_changed_word_rejected() -> None:
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(TEXT, FRS, "f001", "zapłaci karę umowną w wysokości 600 zł")
    assert e.value.reason == "brak_dosłownego_cytatu"


def test_case_and_typography_must_match() -> None:
    for q in ["ZAPŁACI karę umowną", "zaplaci kare umowna w wysokosci"]:
        with pytest.raises(QuoteNotFound) as e:
            verify_quote(TEXT, FRS, "f001", q)
        assert e.value.reason == "brak_dosłownego_cytatu"


def test_markdown_markers_must_match_and_hint_says_copy_verbatim() -> None:
    text = "§ 4. Wynagrodzenie\n\n1. Stawka **45,00 zł brutto** za godzinę.\n"
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(text, split_into_fragments(text), "f001", "Stawka 45,00 zł brutto za godzinę")
    assert "dosłownie" in e.value.hint and "read_fragment" in e.value.hint


def test_short_quote_rejected() -> None:
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(TEXT, FRS, "f001", "500 zł")
    assert e.value.reason == "za_krótki_cytat"
    assert "12" in e.value.hint


def test_min_len_boundary_11_vs_12() -> None:
    text = "§ 1. X\n\n1. Strony ustalają termin płatności.\n"
    frs = split_into_fragments(text)
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(text, frs, "f001", "Strony usta")  # 11 znaków
    assert e.value.reason == "za_krótki_cytat"
    m = verify_quote(text, frs, "f001", "Strony ustal")  # 12 znaków
    assert text[m.start : m.end] == "Strony ustal"


def test_min_len_measured_after_normalization() -> None:
    # 11 znaków po normalizacji, mimo dłuższego surowego cytatu
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(TEXT, FRS, "f001", "  Najemca  \n zap  ")
    assert e.value.reason == "za_krótki_cytat"
    # "Najemca zapł" = 12 znaków po normalizacji
    m = verify_quote(TEXT, FRS, "f001", "  Najemca  \n zapł  ")
    assert TEXT[m.start : m.end] == "Najemca zapł"


def test_custom_min_len() -> None:
    m = verify_quote(TEXT, FRS, "f001", "500 zł", min_len=6)
    assert TEXT[m.start : m.end] == "500 zł"


@pytest.mark.parametrize("q", ["", "   ", "\n\t  "])
def test_empty_or_whitespace_quote_is_too_short(q: str) -> None:
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(TEXT, FRS, "f001", q)
    assert e.value.reason == "za_krótki_cytat"


def test_unknown_fragment_rejected() -> None:
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(TEXT, FRS, "f999", "zapłaci karę umowną")
    assert e.value.reason == "zły_fragment"
    assert "list_fragments" in e.value.hint


def test_unknown_fragment_checked_before_length() -> None:
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(TEXT, FRS, "f999", "x")
    assert e.value.reason == "zły_fragment"


def test_quote_from_other_fragment_rejected() -> None:
    q = "Drugi ustęp zawiera tekst beta"
    assert q in TEXT2
    assert TEXT2[verify_quote(TEXT2, FRS2, "f002", q).start :].startswith(q)
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(TEXT2, FRS2, "f001", q)
    assert e.value.reason == "brak_dosłownego_cytatu"


def test_quote_across_fragment_boundary_rejected() -> None:
    q = "tekst alfa.\n\n2. Drugi ustęp"
    assert q in TEXT2
    for fid in ("f001", "f002"):
        with pytest.raises(QuoteNotFound) as e:
            verify_quote(TEXT2, FRS2, fid, q)
        assert e.value.reason == "brak_dosłownego_cytatu"


def test_quote_spanning_newline_and_indent_inside_fragment() -> None:
    m = verify_quote(TEXT2, FRS2, "f002", "tekst beta, który ma wcięcie")
    assert TEXT2[m.start : m.end] == "tekst beta,\n   który ma wcięcie"
    assert m.start >= FRS2[1].start and m.end <= FRS2[1].end


def test_first_occurrence_is_returned() -> None:
    text = "§ 1. X\n\n1. Kara umowna wynosi 100 zł. Kara umowna wynosi 100 zł.\n"
    m = verify_quote(text, split_into_fragments(text), "f001", "Kara umowna wynosi 100 zł")
    assert m.start == text.index("Kara umowna")
    assert m.end == m.start + len("Kara umowna wynosi 100 zł")


def test_offsets_are_absolute_in_later_fragment() -> None:
    m = verify_quote(TEXT2, FRS2, "f002", "zawiera tekst beta")
    assert m.start == TEXT2.index("zawiera tekst beta")


def test_zero_width_inside_text_must_be_quoted() -> None:
    text = "§ 1. X\n\n1. Kara wyno​si 100 zł dziennie.\n"
    with pytest.raises(QuoteNotFound):
        verify_quote(text, split_into_fragments(text), "f001", "Kara wynosi 100 zł dziennie")
    m = verify_quote(text, split_into_fragments(text), "f001", "Kara wyno​si 100 zł dziennie")
    assert text[m.start : m.end] == "Kara wyno​si 100 zł dziennie"


@pytest.mark.parametrize("ws", [" ", " ", " ", "\t", "\r\n", " "])
def test_each_whitespace_char_equals_space(ws: str) -> None:
    text = f"§ 1. X\n\n1. Najemca{ws}zapłaci{ws}karę umowną.\n"
    m = verify_quote(text, split_into_fragments(text), "f001", "Najemca zapłaci karę umowną.")
    assert text[m.start : m.end] == f"Najemca{ws}zapłaci{ws}karę umowną."
    m2 = verify_quote(
        text, split_into_fragments(text), "f001", f"Najemca{ws}{ws}zapłaci karę umowną."
    )
    assert m2.start == m.start


def test_nfc_text_nfd_quote_not_matched() -> None:
    import unicodedata

    composed = "Zażółć gęślą jaźń tutaj."
    text = f"§ 1. X\n\n1. {composed}\n"
    nfd_quote = unicodedata.normalize("NFD", composed)
    assert nfd_quote != composed
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(text, split_into_fragments(text), "f001", nfd_quote)
    assert e.value.reason == "brak_dosłownego_cytatu"


def test_nfd_text_nfc_quote_not_matched() -> None:
    import unicodedata

    composed = "Zażółć gęślą jaźń tutaj."
    text = unicodedata.normalize("NFD", f"§ 1. X\n\n1. {composed}\n")
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(text, split_into_fragments(text), "f001", composed)
    assert e.value.reason == "brak_dosłownego_cytatu"


def test_negative_min_len_rejected() -> None:
    with pytest.raises(ValueError, match="min_len"):
        verify_quote(TEXT, FRS, "f001", "zapłaci", min_len=-1)


def test_exception_message_never_contains_quote_or_text() -> None:
    q = "zapłaci karę umowną w wysokości 600 zł"
    with pytest.raises(QuoteNotFound) as e:
        verify_quote(TEXT, FRS, "f001", q)
    s = str(e.value)
    assert s.startswith("brak_dosłownego_cytatu: ")
    assert q not in s and "zapłaci" not in s and "Najemca" not in s
    for fid, quote in (("f999", "tajny cytat o długości"), ("f001", "tajny")):
        with pytest.raises(QuoteNotFound) as e2:
            verify_quote(TEXT, FRS, fid, quote)
        assert quote not in str(e2.value)
