"""Logika scripts/eval_live.py na fałszywym agencie i klasyfikatorze (bez Claude API)."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from db_env import Env

from app.agent.classifier import FakeClassifier
from app.agent.fake_runner import FakeAgentRunner, ToolCall
from app.config import Settings

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
CLEAN = DATA / "umowy" / "umowa_najmu.md"
INJECTED = DATA / "umowy_z_wstrzyknieciem" / "jawne_polecenie.md"
CLEAN_QUOTE = "Lokal będzie wykorzystywany wyłącznie na cele mieszkaniowe Najemcy"
SETTINGS = Settings(database_url="postgresql+psycopg://u:p@localhost/db")


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("eval_live", ROOT / "scripts" / "eval_live.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["eval_live"] = module
    spec.loader.exec_module(module)
    return module


ev = load_script()


def runner(script: list[ToolCall]) -> FakeAgentRunner:
    return FakeAgentRunner(script, max_turns=30, max_budget_usd=0.5, timeout_s=5.0)


def finding(cytat: str, fragment_id: str) -> ToolCall:
    return ToolCall(
        "submit_finding",
        {
            "typ": "termin",
            "teza": "Teza",
            "cytat": cytat,
            "fragment_id": fragment_id,
            "uzasadnienie": "u",
        },
    )


def test_corpus_lists_clean_and_injected_contracts_without_readme() -> None:
    items = ev.corpus(DATA)
    names = {(p.name, injected) for p, injected in items}
    assert ("umowa_najmu.md", False) in names
    assert ("jawne_polecenie.md", True) in names
    assert all(p.name != "README.md" for p, _ in items)


def test_contract_kind_from_file_name() -> None:
    assert ev.contract_kind(Path("umowa_dostawy.md")) == "dostawa"
    assert ev.contract_kind(Path("umowa_zlecenia.md")) == "zlecenie"
    assert ev.contract_kind(Path("umowa_najmu_lokalu_uzytkowego.md")) == "najem"
    assert ev.contract_kind(Path("zero_width.md")) == "najem"


async def test_clean_contract_with_verbatim_finding_passes(env: Env) -> None:
    fragment = await first_fragment_with(env, CLEAN, CLEAN_QUOTE)
    result = await ev.evaluate(
        env.sf,
        SETTINGS,
        env.user_id,
        CLEAN,
        injected=False,
        runner=runner(
            [
                finding(CLEAN_QUOTE, fragment),
                finding("zmyślona teza bez oparcia w tekście", fragment),
            ]
        ),
        classifier=FakeClassifier([]),
    )
    assert result.status == "done"
    assert (result.accepted, result.rejected) == (1, 1)
    assert result.problems == [] and result.passed


async def test_injected_contract_quarantined_passes(env: Env) -> None:
    result = await ev.evaluate(
        env.sf,
        SETTINGS,
        env.user_id,
        INJECTED,
        injected=True,
        runner=runner([]),
        classifier=FakeClassifier([]),
    )
    assert result.status == "quarantined"
    assert result.passed


async def test_injected_contract_not_quarantined_fails(env: Env) -> None:
    result = await ev.evaluate(
        env.sf,
        SETTINGS,
        env.user_id,
        CLEAN,
        injected=True,
        runner=runner([]),
        classifier=FakeClassifier([]),
    )
    assert result.status == "done"
    assert not result.passed
    assert any("quarantined" in p for p in result.problems)


def test_quote_outside_document_is_a_problem() -> None:
    text = "Najemca zapłaci karę umowną w wysokości 600 zł."
    ok = ev.FindingQuote(cytat="zapłaci karę umowną", start=8, end=27)
    moved = ev.FindingQuote(cytat="zapłaci karę umowną", start=0, end=19)
    absent = ev.FindingQuote(cytat="Wynajmujący zwróci kaucję", start=0, end=25)
    assert ev.quote_problems(text, [ok]) == []
    assert len(ev.quote_problems(text, [moved, absent])) == 2


def test_exit_code_is_one_when_any_contract_fails() -> None:
    good = ev.EvalResult(
        "a.md", injected=False, status="done", accepted=1, rejected=0, cost_usd=0.1, problems=[]
    )
    bad = ev.EvalResult(
        "b.md", injected=True, status="done", accepted=0, rejected=0, cost_usd=0.1, problems=["x"]
    )
    assert ev.exit_code([good]) == 0
    assert ev.exit_code([good, bad]) == 1


async def first_fragment_with(env: Env, path: Path, quote: str) -> str:
    from app.repo.contracts import list_fragments

    text = path.read_text(encoding="utf-8")
    vid = env.version(text)
    with env.sf() as s:
        frags = list_fragments(s, vid)
        return next(f.id for f in frags if quote in text[f.start : f.end])


def test_main_runs_with_foundry_credentials(monkeypatch: Any) -> None:
    """Ewaluacja na żywo działa także z Microsoft Foundry, bez klucza Claude API."""
    from pydantic import SecretStr

    settings = Settings(
        database_url="postgresql+psycopg://u:p@localhost/db",
        llm_provider="foundry",
        anthropic_foundry_api_key=SecretStr("k-f"),
        anthropic_foundry_resource="moj-zasob",
    )
    started: list[Settings] = []

    async def fake_run_all(s: Settings) -> list[Any]:
        started.append(s)
        return []

    monkeypatch.setattr(ev, "get_settings", lambda: settings)
    monkeypatch.setattr(ev, "run_all", fake_run_all)
    monkeypatch.setattr(sys, "argv", ["eval_live.py", "--zgoda-na-koszt"])
    assert ev.main() == 0
    assert started == [settings]
