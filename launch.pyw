"""Start the desktop app without a console and report startup failures."""

import ctypes
import traceback


def main() -> None:
    try:
        from app import main as run_app

        run_app()
    except Exception:
        message = traceback.format_exc()
        try:
            from i18n import translate
            from preferences import load_language

            title = translate(load_language(), "startup_title")
            body = translate(load_language(), "startup_error", error=message)
        except Exception:
            title = "Startup error"
            body = f"Could not start Batch Markdown Converter.\n\n{message}"
        ctypes.windll.user32.MessageBoxW(
            None,
            body,
            title,
            0x10,
        )


if __name__ == "__main__":
    main()
