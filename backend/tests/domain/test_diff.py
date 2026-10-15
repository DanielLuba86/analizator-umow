from app.domain.diff import FindingKey, FragmentChange, diff_findings, diff_fragments


def test_diff_detects_added_removed_changed() -> None:
    old = [("§ 1", "Stary tekst"), ("§ 2", "Bez zmian"), ("§ 3", "Usunięty")]
    new = [("§ 1", "Nowy tekst"), ("§ 2", "Bez zmian"), ("§ 4", "Dodany")]
    assert diff_fragments(old, new) == [
        FragmentChange("§ 1", "zmieniony", "Stary tekst", "Nowy tekst"),
        FragmentChange("§ 4", "dodany", None, "Dodany"),
        FragmentChange("§ 3", "usunięty", "Usunięty", None),
    ]


def test_whitespace_only_change_is_not_a_change() -> None:
    old = [("§ 1", "Ala ma  kota.\n")]
    new = [("§ 1", "Ala ma\tkota.")]
    assert diff_fragments(old, new) == []


def test_removed_labels_keep_old_order() -> None:
    old = [("c", "1"), ("a", "2"), ("b", "3")]
    new = [("b", "3")]
    assert [c.label for c in diff_fragments(old, new)] == ["c", "a"]


def test_findings_diff_new_and_resolved() -> None:
    a = FindingKey("kara", "§ 5", "kara umowna 10%")
    b = FindingKey("termin", "§ 2", "termin 14 dni")
    c = FindingKey("ryzyko", "§ 7", "odpowiedzialność bez limitu")
    d = FindingKey("kara", "§ 1", "kara 5%")
    res = diff_findings([a, b], [b, c, d])
    assert res == {"nowe": [d, c], "ustąpiło": [a]}


def test_findings_whitespace_in_cytat_is_not_a_change() -> None:
    old = [FindingKey.of("kara", "§ 5", "kara  umowna\n10%")]
    new = [FindingKey.of("kara", "§ 5", "kara umowna 10%")]
    assert diff_findings(old, new) == {"nowe": [], "ustąpiło": []}
    assert diff_findings(
        [FindingKey("kara", "§ 5", "kara  umowna 10%")],
        [FindingKey("kara", "§ 5", "kara umowna 10%")],
    ) == {"nowe": [], "ustąpiło": []}
