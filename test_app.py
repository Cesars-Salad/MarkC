from pathlib import Path
import queue
import unittest
from unittest.mock import patch

from app import BatchMarkdownApp
from converter import ConversionResult


class FakeVariable:
    def __init__(self, value=None) -> None:
        self.value = value
        self.history = []

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value
        self.history.append(value)


class FakeWidget:
    def __init__(self) -> None:
        self.options = {}
        self.states = []

    def configure(self, **options) -> None:
        self.options.update(options)

    def state(self, states) -> None:
        self.states.append(states)


class FakeProgress(FakeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.value = 0

    def __getitem__(self, key):
        if key == "value":
            return self.value
        raise KeyError(key)

    def __setitem__(self, key, value) -> None:
        if key == "value":
            self.value = value
        else:
            raise KeyError(key)


class FakeRoot:
    def __init__(self) -> None:
        self.scheduled = []
        self.destroyed = False

    def after(self, delay, callback) -> None:
        self.scheduled.append((delay, callback))

    def destroy(self) -> None:
        self.destroyed = True


def make_app() -> BatchMarkdownApp:
    app = BatchMarkdownApp.__new__(BatchMarkdownApp)
    app._busy = False
    app._task_total = 0
    app._close_when_done = False
    app.output_mode = FakeVariable("separate")
    app.status = FakeVariable()
    app.files = []
    app.ocr_files = set()
    app.messages = queue.Queue()
    app.failures = []
    app._successful_count = 0
    app.merged_result = None
    app.active_merge = False
    app.progress = FakeProgress()
    app.root = FakeRoot()
    app.file_list = FakeWidget()
    app.output_dir_entry = FakeWidget()
    app.merged_name_entry = FakeWidget()
    for name in (
        "add_button",
        "remove_button",
        "clear_button",
        "browse_button",
        "convert_button",
        "move_up_button",
        "move_down_button",
        "ocr_check",
        "ocr_model_entry",
        "language_picker",
    ):
        setattr(app, name, FakeWidget())
    app.mode_buttons = [FakeWidget(), FakeWidget()]
    return app


class AppTests(unittest.TestCase):
    def test_busy_state_disables_list_and_destination_and_ignores_drops(self) -> None:
        app = make_app()
        original = Path("original.txt")
        app.files = [original]

        app._set_busy(True)
        result = app._handle_drop(object())

        self.assertEqual(result, "break")
        self.assertEqual(app.files, [original])
        self.assertEqual(app.file_list.states[-1], ["disabled"])
        self.assertEqual(app.output_dir_entry.options["state"], "disabled")

    def test_progress_and_summary_keep_the_started_task_total(self) -> None:
        app = make_app()
        app.language = FakeVariable("en")
        app._task_total = 2
        app.files = [Path("one.txt"), Path("two.txt"), Path("later.txt")]
        app.messages.put(("result", ConversionResult(Path("one.txt"), Path("one.md"))))
        app.messages.put(
            ("result", ConversionResult(Path("two.txt"), None, "conversion failed"))
        )
        app.messages.put(("done", 2))

        with patch("app.messagebox.showwarning"):
            app._process_messages()

        self.assertIn("Failed 2 of 2: two.txt", app.status.history)
        self.assertEqual(app.status.get(), "Done: 1 converted, 1 failed.")
        self.assertEqual(app.progress["value"], 2)

    def test_close_during_conversion_waits_for_worker_completion(self) -> None:
        app = make_app()
        app.language = FakeVariable("en")
        app._set_busy(True)

        with patch("app.messagebox.askyesno", return_value=True) as ask:
            app._request_close()

        ask.assert_called_once()
        self.assertTrue(app._close_when_done)
        self.assertFalse(app.root.destroyed)
        self.assertIn("app will close when it finishes", app.status.get())
        app._task_total = 0
        app.messages.put(("done", 0))
        app._process_messages()
        self.assertTrue(app.root.destroyed)


if __name__ == "__main__":
    unittest.main()
