import re
from pathlib import Path

from app.domain.fragments import Fragment, fragment_text, split_into_fragments


def by_label(text: str, label: str) -> Fragment:
    return next(f for f in split_into_fragments(text) if f.label == label)


def assert_covers(text: str) -> None:
    frs = split_into_fragments(text)
    assert frs[0].start == 0 and frs[-1].end == len(text)
    assert all(a.end == b.start for a, b in zip(frs, frs[1:], strict=False))
    assert all(f.start < f.end for f in frs)
    assert all(text[f.start : f.end].strip() for f in frs)


def test_fragments_cover_whole_text_contiguously(umowy_dir: Path) -> None:
    paths = sorted(umowy_dir.glob("*.md"))
    assert len(paths) == 5
    for path in paths:
        assert_covers(path.read_text(encoding="utf-8"))


def test_zlecenie_labels(zlecenie_text: str) -> None:
    labels = [f.label for f in split_into_fragments(zlecenie_text)]
    assert labels[0] == "Komparycja"
    assert "§ 4 ust. 1" in labels and "§ 8" in labels and "Podpisy" in labels


def test_numbered_point_text_lands_in_its_fragment(zlecenie_text: str) -> None:
    f = by_label(zlecenie_text, "§ 4 ust. 1")
    assert "45,00 zł brutto" in fragment_text(zlecenie_text, f)


def test_text_without_paragraph_headers_splits_into_akapity() -> None:
    text = "Pierwszy akapit umowy.\n\nDrugi akapit umowy.\n"
    assert [f.label for f in split_into_fragments(text)] == ["Akapit 1", "Akapit 2"]


def test_ids_are_sequential(zlecenie_text: str) -> None:
    frs = split_into_fragments(zlecenie_text)
    assert [f.id for f in frs[:3]] == ["f001", "f002", "f003"]


def test_title_and_komparycja_form_one_fragment(zlecenie_text: str) -> None:
    first = split_into_fragments(zlecenie_text)[0]
    body = fragment_text(zlecenie_text, first)
    assert first.label == "Komparycja"
    assert body.startswith("# UMOWA ZLECENIA")
    assert "## §" not in body


def test_attachment_heading_gets_own_fragment(zlecenie_text: str) -> None:
    labels = [f.label for f in split_into_fragments(zlecenie_text)]
    assert any(label.startswith("Załącznik nr 1") for label in labels)


def test_text_starting_with_paragraph_has_no_komparycja() -> None:
    text = "§ 1. Przedmiot\n1. Pierwszy punkt.\n2. Drugi punkt.\n"
    frs = split_into_fragments(text)
    assert [f.label for f in frs] == ["§ 1 ust. 1", "§ 1 ust. 2"]
    assert frs[0].start == 0
    assert_covers(text)


def test_leading_whitespace_belongs_to_first_fragment() -> None:
    text = "\n\n## § 1. Tytuł\nTreść paragrafu.\n"
    frs = split_into_fragments(text)
    assert [f.label for f in frs] == ["§ 1"]
    assert frs[0].start == 0 and frs[0].end == len(text)


def test_indented_subitems_are_not_new_ustepy() -> None:
    text = "## § 2. Tytuł\n\n1. Punkt.\n   1. podpunkt trzy\n    2. podpunkt cztery\n2. Drugi.\n"
    frs = split_into_fragments(text)
    assert [f.label for f in frs] == ["§ 2 ust. 1", "§ 2 ust. 2"]
    body = fragment_text(text, frs[0])
    assert "podpunkt trzy" in body and "podpunkt cztery" in body


def test_labels_unique_per_file(umowy_dir: Path) -> None:
    for path in sorted(umowy_dir.glob("*.md")):
        labels = [f.label for f in split_into_fragments(path.read_text(encoding="utf-8"))]
        assert len(labels) == len(set(labels)), path.name


def test_ust_numbers_sequential_per_paragraph(umowy_dir: Path) -> None:
    for path in sorted(umowy_dir.glob("*.md")):
        per_par: dict[str, list[str]] = {}
        for f in split_into_fragments(path.read_text(encoding="utf-8")):
            m = re.fullmatch(r"(§ \d+) ust\. (\d+)", f.label)
            if m:
                per_par.setdefault(m.group(1), []).append(m.group(2))
        for par, nums in per_par.items():
            assert nums == [str(k) for k in range(1, len(nums) + 1)], (path.name, par)


def test_restarted_list_continues_numbering() -> None:
    text = "## § 1. A\n1. a\n2. b\n\nTekst.\n\n1. c\n"
    labels = [f.label for f in split_into_fragments(text)]
    assert labels == ["§ 1 ust. 1", "§ 1 ust. 2", "§ 1 ust. 3"]


def test_label_collisions_get_suffix() -> None:
    text = "## § 1. A\nTreść.\n\n## Uwagi\nx\n\n## Uwagi\ny\n"
    labels = [f.label for f in split_into_fragments(text)]
    assert labels == ["§ 1", "Uwagi", "Uwagi (2)"]


def test_section_without_list_is_single_fragment_and_rule_is_text() -> None:
    text = "Wstęp.\n\n## § 1. A\nTreść.\n\n---\n\n## § 2. B\nInna.\n"
    frs = split_into_fragments(text)
    assert [f.label for f in frs] == ["Komparycja", "§ 1", "§ 2"]
    assert "---" in fragment_text(text, frs[1])
    assert_covers(text)


def test_empty_text_has_no_fragments() -> None:
    assert split_into_fragments("") == []
    assert split_into_fragments("  \n\n") == []
