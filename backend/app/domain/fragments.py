"""Podział tekstu umowy na fragmenty o stabilnych etykietach i identyfikatorach."""

import re
from dataclasses import dataclass

MAX_FRAGMENT_ID_LEN = 20  # długość kolumn fragment_id / frag_id w bazie

_PARAGRAPH_HEADING = re.compile(r"^(?:#{1,3}\s*§\s*(\d+)|§\s*(\d+)\.)")
_OTHER_HEADING = re.compile(r"^#{1,3}\s+(.+)")
_LIST_ITEM = re.compile(r"^\d+\.\s")


@dataclass(frozen=True)
class Fragment:
    id: str
    label: str
    start: int
    end: int


def fragment_text(text: str, f: Fragment) -> str:
    return text[f.start : f.end]


def _paragraph_number(line: str) -> str | None:
    m = _PARAGRAPH_HEADING.match(line)
    if m is None:
        return None
    return m.group(1) or m.group(2)


def _build(text: str, boundaries: list[tuple[int, str]]) -> list[Fragment]:
    if not boundaries:
        return []
    starts = [0] + [start for start, _ in boundaries[1:]]
    ends = [*starts[1:], len(text)]
    seen: dict[str, int] = {}
    fragments: list[Fragment] = []
    for i, (_, label) in enumerate(boundaries):
        seen[label] = seen.get(label, 0) + 1
        unique = label if seen[label] == 1 else f"{label} ({seen[label]})"
        fragments.append(Fragment(id=f"f{i + 1:03d}", label=unique, start=starts[i], end=ends[i]))
    return fragments


def _split_akapity(text: str) -> list[tuple[int, str]]:
    boundaries: list[tuple[int, str]] = []
    offset = 0
    prev_blank = True
    for line in text.splitlines(keepends=True):
        blank = not line.strip()
        if not blank and prev_blank:
            boundaries.append((offset, f"Akapit {len(boundaries) + 1}"))
        prev_blank = blank
        offset += len(line)
    return boundaries


def _split_paragraphs(text: str, lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    boundaries: list[tuple[int, str]] = []
    first = next(i for i, (_, line) in enumerate(lines) if _paragraph_number(line))
    if text[: lines[first][0]].strip():
        boundaries.append((0, "Komparycja"))

    section: str | None = None  # numer bieżącego §, None poza sekcją §
    ust = 0
    for offset, line in lines[first:]:
        number = _paragraph_number(line)
        other = _OTHER_HEADING.match(line)
        item = _LIST_ITEM.match(line)  # tylko od kolumny 0; wcięte linie to część punktu
        if number is not None:
            section, ust = number, 0
            boundaries.append((offset, f"§ {number}"))
        elif other is not None:
            section = None
            boundaries.append((offset, other.group(1).strip()))
        elif item is not None and section is not None:
            ust += 1
            label = f"§ {section} ust. {ust}"
            if ust > 1:
                boundaries.append((offset, label))
            else:
                # nagłówek i tekst przed punktem 1 należą do pierwszego ustępu
                boundaries[-1] = (boundaries[-1][0], label)
    return boundaries


def split_into_fragments(text: str) -> list[Fragment]:
    """Dzieli tekst na ciągłe fragmenty pokrywające dokładnie [0, len(text))."""
    lines: list[tuple[int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        lines.append((offset, line))
        offset += len(line)

    if any(_paragraph_number(line) for _, line in lines):
        boundaries = _split_paragraphs(text, lines)
    else:
        boundaries = _split_akapity(text)
    return _build(text, boundaries)
