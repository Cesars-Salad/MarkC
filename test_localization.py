import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from i18n import STRINGS, translate
from preferences import load_language, save_language


class LocalizationTests(unittest.TestCase):
    def test_english_and_portuguese_translations_have_matching_keys(self) -> None:
        self.assertEqual(set(STRINGS["en"]), set(STRINGS["pt"]))
        self.assertEqual(translate("en", "convert"), "Convert files")
        self.assertEqual(translate("pt", "convert"), "Converter arquivos")
        self.assertEqual(
            translate("en", "file_count", count=3), "3 file(s) in the list."
        )

    def test_language_preference_is_persisted_without_other_settings(self) -> None:
        with TemporaryDirectory() as temporary:
            config = Path(temporary) / "settings.json"
            with patch("preferences._settings_path", return_value=config):
                save_language("pt")
                self.assertEqual(load_language(), "pt")
                save_language("en")
                self.assertEqual(load_language(), "en")

    def test_first_run_uses_the_portuguese_system_locale(self) -> None:
        with TemporaryDirectory() as temporary:
            config = Path(temporary) / "missing.json"
            with (
                patch("preferences._settings_path", return_value=config),
                patch.dict(os.environ, {"LANG": "pt_BR.UTF-8"}, clear=True),
            ):
                self.assertEqual(load_language(), "pt")

    def test_first_run_detects_windows_portuguese_locale_name(self) -> None:
        with TemporaryDirectory() as temporary:
            config = Path(temporary) / "missing.json"
            with (
                patch("preferences._settings_path", return_value=config),
                patch.dict(os.environ, {}, clear=True),
                patch("preferences.locale.getlocale", return_value=("Portuguese_Brazil.1252", "cp1252")),
            ):
                self.assertEqual(load_language(), "pt")


if __name__ == "__main__":
    unittest.main()
