"""A small, localized desktop interface for batch Markdown conversion."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from tkinterdnd2 import DND_FILES, TkinterDnD

from converter import (
    ConversionResult,
    MergeResult,
    create_ocr_converter,
    get_ocr_setup_issue,
    iter_convert_files,
    merge_files,
)
from i18n import translate
from preferences import load_language, save_language


OCR_FORMATS = {".pdf", ".docx", ".pptx", ".xlsx"}


class BatchMarkdownApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.files: list[Path] = []
        self.ocr_files: set[str] = set()
        self.messages: queue.Queue[tuple[str, object]] = queue.Queue()
        self.failures: list[ConversionResult] = []
        self.merged_result: MergeResult | None = None
        self.active_merge = False

        self.language = tk.StringVar(value=load_language())
        self.output_mode = tk.StringVar(value="separate")
        self.merged_name = tk.StringVar(value="convertido.md")
        self.ocr_model = tk.StringVar(value="gpt-4o")
        self.output_dir = tk.StringVar(value=str(Path.home() / "Markdown convertido"))
        self.status = tk.StringVar()
        self._build_ui()
        self._apply_language()
        self.root.after(100, self._process_messages)

    def _t(self, key: str, **values: object) -> str:
        return translate(self.language.get(), key, **values)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        self.header = ttk.Label(outer, font=("", 11, "bold"))
        self.header.pack(anchor="w", pady=(0, 8))

        language_bar = ttk.Frame(outer)
        language_bar.pack(fill="x", pady=(0, 8))
        self.language_label = ttk.Label(language_bar)
        self.language_label.pack(side="left")
        self.language_picker = ttk.Combobox(
            language_bar,
            state="readonly",
            width=14,
            values=("Português", "English"),
        )
        self.language_picker.pack(side="left", padx=(8, 0))
        self.language_picker.current(0 if self.language.get() == "pt" else 1)
        self.language_picker.bind("<<ComboboxSelected>>", self._change_language)

        self.mode_buttons = []
        modes = ttk.Frame(outer)
        modes.pack(fill="x", pady=(0, 8))
        for value in ("separate", "merged"):
            button = ttk.Radiobutton(
                modes,
                variable=self.output_mode,
                value=value,
                command=self._update_mode,
            )
            button.pack(side="left", padx=(0 if value == "separate" else 12, 0))
            self.mode_buttons.append(button)

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 8))
        self.add_button = ttk.Button(controls, command=self._add_files)
        self.add_button.pack(side="left")
        self.remove_button = ttk.Button(
            controls, command=self._remove_selected
        )
        self.remove_button.pack(side="left", padx=(8, 0))
        self.clear_button = ttk.Button(controls, command=self._clear)
        self.clear_button.pack(side="left", padx=(8, 0))
        self.move_up_button = ttk.Button(
            controls, text="↑", width=3, command=lambda: self._move_selected(-1)
        )
        self.move_up_button.pack(side="right")
        self.move_down_button = ttk.Button(
            controls, text="↓", width=3, command=lambda: self._move_selected(1)
        )
        self.move_down_button.pack(side="right", padx=(0, 4))

        listing = ttk.Frame(outer)
        listing.pack(fill="both", expand=True)
        self.file_list = ttk.Treeview(
            listing,
            columns=("name", "path", "ocr"),
            show="headings",
            selectmode="extended",
            height=8,
        )
        self.file_list.column("name", width=170, stretch=False)
        self.file_list.column("path", width=390)
        self.file_list.column("ocr", width=48, stretch=False, anchor="center")
        scrollbar = ttk.Scrollbar(
            listing, orient="vertical", command=self.file_list.yview
        )
        self.file_list.configure(yscrollcommand=scrollbar.set)
        self.file_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.file_list.drop_target_register(DND_FILES)
        self.file_list.dnd_bind("<<Drop>>", self._handle_drop)
        self.file_list.bind("<Button-1>", self._toggle_ocr_cell, add=True)
        self.file_list.bind("<Delete>", lambda _event: self._remove_selected())

        self.drop_hint = ttk.Label(outer)
        self.drop_hint.pack(anchor="w", pady=(4, 0))
        self.ocr_hint = ttk.Label(outer, wraplength=680)
        self.ocr_hint.pack(anchor="w", pady=(2, 8))

        self.ocr_options = ttk.Frame(outer)
        self.ocr_var = tk.BooleanVar(value=False)
        self.ocr_check = ttk.Checkbutton(
            self.ocr_options, variable=self.ocr_var, command=self._toggle_ocr_all
        )
        self.ocr_check.pack(side="left")
        self.ocr_model_label = ttk.Label(self.ocr_options)
        self.ocr_model_label.pack(side="left", padx=(12, 4))
        self.ocr_model_entry = ttk.Entry(
            self.ocr_options, textvariable=self.ocr_model, width=18
        )
        self.ocr_model_entry.pack(side="left")
        self.ocr_options.pack(fill="x", pady=(0, 8))

        self.destination_frame = ttk.LabelFrame(outer, padding=8)
        self.destination_frame.pack(fill="x", pady=(4, 8))
        ttk.Entry(self.destination_frame, textvariable=self.output_dir).pack(
            side="left", fill="x", expand=True
        )
        self.browse_button = ttk.Button(
            self.destination_frame, command=self._choose_output
        )
        self.browse_button.pack(side="left", padx=(8, 0))

        self.merged_name_frame = ttk.Frame(outer)
        self.merged_name_frame.pack(fill="x", pady=(0, 8))
        self.merged_name_label = ttk.Label(self.merged_name_frame)
        self.merged_name_label.pack(side="left")
        self.merged_name_entry = ttk.Entry(
            self.merged_name_frame, textvariable=self.merged_name, width=30
        )
        self.merged_name_entry.pack(side="left", padx=(8, 0))

        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(4, 0))
        self.progress = ttk.Progressbar(footer, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 8))
        self.status_label = ttk.Label(footer, textvariable=self.status)
        self.status_label.pack(side="left")
        self.convert_button = ttk.Button(
            footer, command=self._start_conversion, style="Accent.TButton"
        )
        self.convert_button.pack(side="right")
        self._update_mode()

    def _apply_language(self) -> None:
        self.root.title(self._t("window_title"))
        self.header.configure(text=self._t("header"))
        self.language_label.configure(text=self._t("language"))
        self.mode_buttons[0].configure(text=self._t("separate_mode"))
        self.mode_buttons[1].configure(text=self._t("merged_mode"))
        self.add_button.configure(text=self._t("add_files"))
        self.remove_button.configure(text=self._t("remove_files"))
        self.clear_button.configure(text=self._t("clear_list"))
        self.file_list.heading("name", text=self._t("name_column"))
        self.file_list.heading("path", text=self._t("path_column"))
        self.file_list.heading("ocr", text=self._t("ocr_column"))
        self.drop_hint.configure(text=self._t("drop_hint"))
        self.ocr_hint.configure(
            text=f"{self._t('ocr_supported')} {self._t('ocr_no_images')}"
        )
        self.ocr_check.configure(text=self._t("ocr_checkbox"))
        self.ocr_model_label.configure(text=self._t("ocr_model"))
        self.destination_frame.configure(text=self._t("output_dir"))
        self.browse_button.configure(text=self._t("browse"))
        self.merged_name_label.configure(text=self._t("merged_name"))
        self._update_mode()
        self._refresh_list()
        self._set_status()

    def _change_language(self, _event: tk.Event | None = None) -> None:
        self.language.set("pt" if self.language_picker.current() == 0 else "en")
        try:
            save_language(self.language.get())
        except OSError as exc:
            messagebox.showerror(self._t("fatal_title"), str(exc))
        self._apply_language()

    def _update_mode(self) -> None:
        merged = self.output_mode.get() == "merged"
        if hasattr(self, "merged_name_entry"):
            self.merged_name_entry.configure(state="normal" if merged else "disabled")
            self.convert_button.configure(
                text=self._t("make_merged") if merged else self._t("convert")
            )

    @staticmethod
    def _key(path: Path) -> str:
        return str(path.resolve()).casefold()

    def _refresh_list(self) -> None:
        if not hasattr(self, "file_list"):
            return
        rows = self.file_list.get_children()
        if rows:
            self.file_list.delete(*rows)
        for path in self.files:
            mark = "✓" if self._key(path) in self.ocr_files else ""
            self.file_list.insert(
                "", "end", values=(path.name, str(path), mark)
            )

    def _add_paths(self, paths: tuple[str, ...] | list[str]) -> None:
        existing = {self._key(path) for path in self.files}
        for item in paths:
            path = Path(item.strip().strip('"'))
            if path.is_file() and self._key(path) not in existing:
                self.files.append(path)
                existing.add(self._key(path))
        self._refresh_list()
        self._set_status()

    def _handle_drop(self, event: tk.Event) -> None:
        self._add_paths(self.root.tk.splitlist(event.data))
        return None

    def _add_files(self) -> None:
        chosen = filedialog.askopenfilenames(
            title=self._t("choose_files"),
            filetypes=((self._t("name_column"), "*.*"),),
        )
        self._add_paths(chosen)

    def _toggle_ocr_cell(self, event: tk.Event) -> str | None:
        if self.file_list.identify_column(event.x) != "#3":
            return None
        row = self.file_list.identify_row(event.y)
        rows = list(self.file_list.get_children())
        if row not in rows:
            return None
        path = self.files[rows.index(row)]
        if path.suffix.casefold() not in OCR_FORMATS:
            messagebox.showinfo(
                self._t("ocr_unsupported_title"),
                self._t("ocr_unsupported", name=path.name),
            )
            return "break"
        key = self._key(path)
        if key in self.ocr_files:
            self.ocr_files.remove(key)
            message = self._t("ocr_unmarked", name=path.name)
        else:
            self.ocr_files.add(key)
            message = self._t("ocr_marked", name=path.name)
        self._refresh_list()
        self.status.set(message)
        self._update_ocr_all_state()
        return "break"

    def _toggle_ocr_all(self) -> None:
        eligible = [path for path in self.files if path.suffix.casefold() in OCR_FORMATS]
        if self.ocr_var.get():
            self.ocr_files.update(self._key(path) for path in eligible)
        else:
            self.ocr_files.difference_update(self._key(path) for path in eligible)
        self._refresh_list()
        self._set_status()

    def _update_ocr_all_state(self) -> None:
        eligible = {self._key(path) for path in self.files if path.suffix.casefold() in OCR_FORMATS}
        self.ocr_var.set(bool(eligible) and eligible.issubset(self.ocr_files))

    def _move_selected(self, direction: int) -> None:
        rows = list(self.file_list.get_children())
        indices = sorted(
            (rows.index(row) for row in self.file_list.selection()),
            reverse=direction > 0,
        )
        selected_paths = {self.files[index] for index in indices}
        for index in indices:
            target = index + direction
            if 0 <= target < len(self.files):
                self.files[index], self.files[target] = self.files[target], self.files[index]
        self._refresh_list()
        selected_rows = [
            row for row, path in zip(self.file_list.get_children(), self.files)
            if path in selected_paths
        ]
        if selected_rows:
            self.file_list.selection_set(selected_rows)

    def _remove_selected(self) -> None:
        selected = set(self.file_list.selection())
        rows = list(self.file_list.get_children())
        self.files = [path for row, path in zip(rows, self.files) if row not in selected]
        active = {self._key(path) for path in self.files}
        self.ocr_files.intersection_update(active)
        self._refresh_list()
        self._update_ocr_all_state()
        self._set_status()

    def _clear(self) -> None:
        self.files.clear()
        self.ocr_files.clear()
        self.progress["value"] = 0
        self._refresh_list()
        self._update_ocr_all_state()
        self._set_status()

    def _choose_output(self) -> None:
        chosen = filedialog.askdirectory(
            title=self._t("choose_output"),
            initialdir=self.output_dir.get() or str(Path.home()),
        )
        if chosen:
            self.output_dir.set(chosen)

    def _set_status(self) -> None:
        if not self.files:
            self.status.set(self._t("empty_status"))
        else:
            self.status.set(self._t("file_count", count=len(self.files)))
        self._update_ocr_all_state()

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (
            self.add_button,
            self.remove_button,
            self.clear_button,
            self.browse_button,
            self.convert_button,
            self.move_up_button,
            self.move_down_button,
            self.merged_name_entry,
            self.ocr_check,
            self.ocr_model_entry,
            self.language_picker,
            *self.mode_buttons,
        ):
            button.configure(state=state)

    def _start_conversion(self) -> None:
        if not self.files:
            messagebox.showinfo(self._t("no_files_title"), self._t("no_files"))
            return
        destination = self.output_dir.get().strip()
        if not destination:
            messagebox.showinfo(self._t("no_output_title"), self._t("no_output"))
            return

        files = list(self.files)
        ocr_files = {
            path for path in files if self._key(path) in self.ocr_files
        }
        model = self.ocr_model.get().strip()
        if ocr_files:
            unsupported = [path for path in ocr_files if path.suffix.casefold() not in OCR_FORMATS]
            if unsupported:
                messagebox.showinfo(
                    self._t("ocr_unsupported_title"),
                    "\n".join(
                        self._t("ocr_unsupported", name=path.name) for path in unsupported
                    ),
                )
                return
            issue = get_ocr_setup_issue(model)
            if issue == "plugin":
                messagebox.showinfo(
                    self._t("ocr_missing_title"), self._t("ocr_missing_plugin")
                )
                return
            if issue == "client":
                messagebox.showinfo(
                    self._t("ocr_missing_title"), self._t("ocr_missing_client")
                )
                return
            if issue == "key":
                messagebox.showinfo(
                    self._t("ocr_missing_key_title"), self._t("ocr_missing_key")
                )
                return
            if issue == "model":
                messagebox.showinfo(
                    self._t("ocr_missing_title"), self._t("ocr_model_missing")
                )
                return
            if not messagebox.askyesno(
                self._t("ocr_checkbox"), self._t("ocr_no_images")
            ):
                return

        merged = self.output_mode.get() == "merged"
        merged_name = self.merged_name.get().strip()
        if merged and not merged_name:
            messagebox.showinfo(
                self._t("no_merged_name_title"), self._t("no_merged_name")
            )
            return
        if merged and Path(merged_name).name != merged_name:
            messagebox.showinfo(
                self._t("invalid_merged_name_title"),
                self._t("invalid_merged_name"),
            )
            return

        self.failures.clear()
        self.merged_result = None
        self.active_merge = merged
        output_dir = Path(destination).expanduser()
        self.progress.configure(maximum=len(files), value=0)
        self.status.set(
            self._t("processing" if merged else "converting", done=0, total=len(files))
        )
        self._set_busy(True)

        def worker() -> None:
            try:
                ocr_factory = lambda: create_ocr_converter(model)
                if merged:
                    result = merge_files(
                        files,
                        output_dir,
                        merged_name,
                        ocr_files=ocr_files,
                        ocr_converter_factory=ocr_factory if ocr_files else None,
                        ocr_model=model,
                    )
                    self.messages.put(("merged_result", result))
                    self.messages.put(("progress", len(files)))
                else:
                    for result in iter_convert_files(
                        files,
                        output_dir,
                        ocr_files=ocr_files,
                        ocr_converter_factory=ocr_factory if ocr_files else None,
                        ocr_model=model,
                    ):
                        self.messages.put(("result", result))
            except Exception as exc:
                self.messages.put(("fatal", exc))
            finally:
                self.messages.put(("done", len(files)))

        threading.Thread(target=worker, daemon=True).start()

    def _process_messages(self) -> None:
        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                break

            if kind == "result":
                result = payload
                assert isinstance(result, ConversionResult)
                completed = int(self.progress["value"]) + 1
                self.progress["value"] = completed
                if result.succeeded:
                    self.status.set(
                        self._t(
                            "converted",
                            done=completed,
                            total=len(self.files),
                            name=result.output.name if result.output else "",
                        )
                    )
                else:
                    self.failures.append(result)
                    self.status.set(
                        self._t(
                            "failed_progress",
                            done=completed,
                            total=len(self.files),
                            name=result.source.name,
                        )
                    )
            elif kind == "merged_result":
                self.merged_result = payload
                self.failures = list(payload.failures)
            elif kind == "progress":
                self.progress["value"] = payload
            elif kind == "fatal":
                messagebox.showerror(self._t("fatal_title"), str(payload))
            elif kind == "done":
                self._set_busy(False)
                if self.active_merge and self.merged_result is None:
                    continue
                self._show_summary()

        self.root.after(100, self._process_messages)

    def _show_summary(self) -> None:
        if self.active_merge and self.merged_result is not None:
            result = self.merged_result
            self.status.set(
                self._t("done_merged", count=result.succeeded)
            )
            if result.failures:
                details = "\n".join(
                    f"- {failure.source.name}: {failure.error}"
                    for failure in result.failures
                )
                messagebox.showwarning(
                    self._t("merge_failures_title"),
                    self._t(
                        "merge_failures",
                        ok=result.succeeded,
                        bad=len(result.failures),
                        output=result.output or "—",
                        details=details,
                    ),
                )
            elif result.output:
                messagebox.showinfo(
                    self._t("merge_done_title"),
                    self._t("output_created", output=result.output),
                )
            return

        succeeded = int(self.progress["value"])
        failed = len(self.files) - succeeded
        if failed:
            self.status.set(
                self._t("done_with_failures", ok=succeeded, bad=failed)
            )
            details = "\n".join(
                f"- {result.source.name}: {result.error}" for result in self.failures
            )
            if details:
                messagebox.showwarning(
                    self._t("conversion_failures_title"),
                    self._t(
                        "conversion_failures",
                        ok=succeeded,
                        bad=failed,
                        details=details,
                    ),
                )
        else:
            self.status.set(self._t("done_separate", count=succeeded))


def main() -> None:
    root = TkinterDnD.Tk()
    BatchMarkdownApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
