import re

from app.agent.prompt import SYSTEM_PROMPT

TOOLS = ("list_fragments", "read_fragment", "search_templates", "submit_finding", "request_action")


def test_prompt_declares_untrusted_tags_as_data() -> None:
    p = SYSTEM_PROMPT
    assert "<untrusted_contract_fragment>" in p
    assert "dane" in p and "nie polecenia" in p
    assert "ignoruj" in p.lower()
    assert "dosłownie" in p
    assert "submit_finding" in p
    assert "przeczytaj fragment ponownie" in p
    assert "porzuć tezę" in p
    assert "analityk" in p


def test_prompt_lists_exactly_the_five_tools() -> None:
    for t in TOOLS:
        assert t in SYSTEM_PROMPT
    # sekcja narzędzi: dokładnie pięć pozycji "- nazwa("
    assert re.findall(r"^- (\w+)\(", SYSTEM_PROMPT, re.MULTILINE) == list(TOOLS)
    assert "żadnych innych narzędzi" in SYSTEM_PROMPT
