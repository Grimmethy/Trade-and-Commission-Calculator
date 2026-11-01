"""Optional pinned links on the home page, managed by a small JSON file (no code change to add or remove one).

data/pinned-links.json (path overridable with PINNED_LINKS_PATH) is a list of {"label": "...", "href": "/commissions/<code>"}.
Only same-site paths are accepted (href must start with a single "/"), at most MAX_LINKS are shown, and a missing or
broken file means no links. Remove an entry from the file and it disappears at once: that is the 'temporary' part."""
import json
import os
from pathlib import Path

MAX_LINKS = 10
MAX_LABEL = 80


def pinned_path() -> Path:
    return Path(os.environ.get("PINNED_LINKS_PATH", "data/pinned-links.json"))


def load_pinned_links() -> list[dict]:
    try:
        raw = json.loads(pinned_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(raw, list):
        return []
    links = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        label, href = entry.get("label"), entry.get("href")
        if not isinstance(label, str) or not isinstance(href, str):
            continue
        label = label.strip()[:MAX_LABEL]
        if not label or not href.startswith("/") or href.startswith("//") or "\\" in href or any(c.isspace() for c in href):
            continue
        links.append({"label": label, "href": href})
        if len(links) >= MAX_LINKS:
            break
    return links
