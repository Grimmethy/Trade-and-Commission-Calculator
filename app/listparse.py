"""Pure list-parsing helpers for pasted trade lists.

Stdlib only, no I/O, no network, no model calls.

Deliberate deviation from the two-value spec: ``kits_for`` returns the
specified ``(kits, partial)`` pair. Because that pair has no slot for an
"unknown kit size" flag, callers that need it must call
``kit_size_known(models_per_kit)`` separately. When the kit size is unknown
(``None``, ``0``, or any non-positive value), ``kits_for`` returns
``kits == models`` and ``partial == False``.

Catalog rows are dicts shaped like ``CatalogItem.to_dict()``; ``match_line``
reads the real keys ``item_name`` and ``models_per_box``.
"""

import difflib
import math
import re

# Thresholds are assumptions; they are to be tuned by the parser unit tests.
HIGH_CUTOFF = 0.85
LOW_CUTOFF = 0.6
AMBIGUITY_GAP = 0.05

_SEPARATORS_RE = re.compile(r"\n| / |;|,")
_BULLET_RE = re.compile(r"^\s*(?:[-*\u2022]+\s*)+")
_LEADING_COUNT_RE = re.compile(r"^(\d+)\s*[xX]?\s+(.+)$")
_TRAILING_COUNT_RE = re.compile(r"^(.+?)\s+[xX](\d+)$")


def split_list(text):
    """Split pasted text into trimmed, non-empty entries."""
    if not text:
        return []
    out = []
    for piece in _SEPARATORS_RE.split(text):
        cleaned = _BULLET_RE.sub("", piece).strip()
        if cleaned:
            out.append(cleaned)
    return out


def parse_line(line):
    """Return ``(models, name)`` for ``N name``, ``Nx name``, ``name xN``, or bare ``name``."""
    text = line.strip()
    m = _LEADING_COUNT_RE.match(text)
    if m:
        name = m.group(2).strip()
        if name:
            return int(m.group(1)), name
    m = _TRAILING_COUNT_RE.match(text)
    if m:
        name = m.group(1).strip()
        if name:
            return int(m.group(2)), name
    return 1, text


def normalize(name):
    """Lowercase, strip punctuation, collapse whitespace, naively singularize words.

    Assumption: a word longer than three characters that ends in a single ``s``
    loses that ``s``. Verify against real catalog names such as "Flamers".
    """
    s = name.lower()
    s = re.sub(r"['\u2019]", "", s)
    s = re.sub(r"[^\w\s]|_", " ", s)
    out = []
    for word in s.split():
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]
        out.append(word)
    return " ".join(out)


def kit_size_known(models_per_kit):
    """True only for a positive int kit size (bools are rejected)."""
    return (
        isinstance(models_per_kit, int)
        and not isinstance(models_per_kit, bool)
        and models_per_kit > 0
    )


def kits_for(models, models_per_kit):
    """Return ``(kits, partial)``.

    With an unknown kit size, treat each model as one kit and report
    ``partial == False``; use ``kit_size_known`` to detect that case.
    Assumption: ``partial`` means the last kit is incomplete.
    """
    if not kit_size_known(models_per_kit):
        return models, False
    kits = math.ceil(models / models_per_kit)
    partial = models % models_per_kit != 0
    return kits, partial


def match_line(name, catalog):
    """Fuzzy-match ``name`` against catalog dicts.

    Returns ``(status, candidates)`` where status is ``matched``, ``ambiguous``
    or ``not_found``, and candidates are catalog dicts (with a ``score`` key)
    sorted best first, limited to those at or above ``LOW_CUTOFF``.
    """
    target = normalize(name)
    scored = []
    for item in catalog:
        cand = normalize(item.get("item_name") or "")
        if not cand:
            continue
        score = difflib.SequenceMatcher(None, target, cand).ratio()
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)

    candidates = [
        dict(item, score=round(score, 4))
        for score, item in scored
        if score >= LOW_CUTOFF
    ]
    if not candidates:
        return "not_found", []

    best = candidates[0]["score"]
    clear_winner = best >= HIGH_CUTOFF and (
        len(candidates) == 1 or best - candidates[1]["score"] >= AMBIGUITY_GAP
    )
    status = "matched" if clear_winner else "ambiguous"
    return status, candidates
