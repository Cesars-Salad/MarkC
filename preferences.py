"""Persist small, non-secret application preferences."""

import json
import locale
import os
from pathlib import Path


def _settings_path() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home()))
        return root / "BatchMarkdownConverter" / "settings.json"
    if os.name == "posix" and os.environ.get("XDG_CONFIG_HOME"):
        return Path(os.environ["XDG_CONFIG_HOME"]) / "batch-markdown-converter" / "settings.json"
    return Path.home() / ".config" / "batch-markdown-converter" / "settings.json"


def load_language() -> str:
    try:
        settings = json.loads(_settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        system_locale = os.environ.get("LANG", "") or (locale.getlocale()[0] or "")
        normalized = system_locale.casefold().replace("_", "-")
        return "pt" if normalized.startswith(("pt", "portuguese", "português")) else "en"
    language = settings.get("language") if isinstance(settings, dict) else None
    return language if language in {"pt", "en"} else "en"


def save_language(language: str) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"language": language}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
