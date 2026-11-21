"""Optional pinned links on the home page, managed by a small JSON file (no code change to add or remove one).

data/pinned-links.json (path overridable with PINNED_LINKS_PATH) is a list of {"label": "...", "href": "/commissions/<code>"}.
Only same-site paths are accepted (href must start with a single "/"), at most MAX_LINKS are shown, and a missing or
broken file means no links. Remove an entry from the file and it disappears at once: that is the 'temporary' part."""
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_LINKS = 10
MAX_LABEL = 80


def pinned_path() -> Path:
    return Path(os.environ.get("PINNED_LINKS_PATH", "data/pinned-links.json"))


def load_pinned_links() -> list[dict]:
    try:
        raw = json.loads(pinned_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except OSError as e:
        logger.warning("pinned links file %s could not be read: %s", pinned_path(), e)
        return []
    except ValueError as e:
        logger.warning("pinned links file %s is corrupt or truncated, showing no links: %s", pinned_path(), e)
        return []
    if not isinstance(raw, list):
        logger.warning("pinned links file %s must hold a list, got %s; showing no links", pinned_path(), type(raw).__name__)
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
