"""Batch conversion helpers backed by Microsoft MarkItDown."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec
import os
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path
from typing import Callable, Iterator, Protocol


class ConvertedDocument(Protocol):
    text_content: str


class MarkItDownConverter(Protocol):
    def convert(self, source: str) -> ConvertedDocument: ...


@dataclass(frozen=True)
class ConversionResult:
    source: Path
    output: Path | None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class MergeResult:
    output: Path | None
    succeeded: int
    failures: tuple[ConversionResult, ...]


def _default_converter() -> MarkItDownConverter:
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise RuntimeError(
            "MarkItDown não está instalado. Instale as dependências com "
            "'python -m pip install -r requirements.txt'."
        ) from exc
    return MarkItDown()


def create_ocr_converter(model: str) -> MarkItDownConverter:
    try:
        distribution("markitdown-ocr")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "OCR_NOT_INSTALLED: install markitdown-ocr and openai with "
            "'python -m pip install -r requirements-ocr.txt'."
        ) from exc

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OCR_CLIENT_MISSING: install the optional OpenAI client with "
            "'python -m pip install -r requirements-ocr.txt'."
        ) from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OCR_API_KEY_MISSING: set OPENAI_API_KEY before starting the app."
        )

    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise RuntimeError(
            "MarkItDown não está instalado. Instale as dependências com "
            "'python -m pip install -r requirements.txt'."
        ) from exc

    base_url = os.environ.get("OPENAI_BASE_URL")
    client = OpenAI(api_key=api_key, base_url=base_url or None)
    return MarkItDown(
        enable_plugins=True,
        llm_client=client,
        llm_model=model,
    )


def get_ocr_setup_issue(model: str) -> str | None:
    if not model.strip():
        return "model"
    try:
        distribution("markitdown-ocr")
    except PackageNotFoundError:
        return "plugin"
    if find_spec("openai") is None:
        return "client"
    if not os.environ.get("OPENAI_API_KEY"):
        return "key"
    return None


def _path_key(path: Path) -> str:
    return str(path.resolve()).casefold()


def _available_output_path(
    source: Path, output_dir: Path, reserved: set[str]
) -> Path:
    stem = source.stem or source.name
    candidate = output_dir / f"{stem}.md"
    suffix = 2
    while candidate.exists() or _path_key(candidate) in reserved:
        candidate = output_dir / f"{stem} ({suffix}).md"
        suffix += 1
    return candidate


def iter_convert_files(
    input_files: list[Path],
    output_dir: Path,
    converter_factory: Callable[[], MarkItDownConverter] | None = None,
    ocr_files: set[Path] | None = None,
    ocr_converter_factory: Callable[[], MarkItDownConverter] | None = None,
    ocr_model: str = "gpt-4o",
) -> Iterator[ConversionResult]:
    """Convert each input independently, yielding one result per file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    reserved = {_path_key(Path(source)) for source in input_files}
    converter: MarkItDownConverter | None = None
    ocr_converter: MarkItDownConverter | None = None
    ocr_keys = {_path_key(path) for path in (ocr_files or set())}

    for source in input_files:
        source = Path(source)
        if not source.is_file():
            yield ConversionResult(source, None, "O arquivo não existe ou não é um arquivo.")
            continue

        output: Path | None = None
        output_created = False
        try:
            if _path_key(source) in ocr_keys:
                if ocr_converter is None:
                    ocr_converter = (
                        ocr_converter_factory or (lambda: create_ocr_converter(ocr_model))
                    )()
                active_converter = ocr_converter
            else:
                if converter is None:
                    converter = (converter_factory or _default_converter)()
                active_converter = converter
            document = active_converter.convert(str(source))
            content = document.text_content
            if not isinstance(content, str):
                raise TypeError("O conversor não retornou conteúdo Markdown em texto.")

            while True:
                output = _available_output_path(source, output_dir, reserved)
                try:
                    with output.open("x", encoding="utf-8", newline="\n") as file:
                        output_created = True
                        file.write(content)
                    reserved.add(_path_key(output))
                    break
                except FileExistsError:
                    reserved.add(_path_key(output))

            yield ConversionResult(source, output)
        except Exception as exc:
            cleanup_error = ""
            if output_created and output is not None and output.exists():
                try:
                    output.unlink()
                except OSError as cleanup_exc:
                    cleanup_error = (
                        f" Não foi possível remover o arquivo parcial "
                        f"'{output}': {cleanup_exc}"
                    )
            message = str(exc).strip() or "Erro sem detalhes."
            yield ConversionResult(
                source,
                None,
                f"{type(exc).__name__}: {message}{cleanup_error}",
            )


def merge_files(
    input_files: list[Path],
    output_dir: Path,
    output_name: str,
    converter_factory: Callable[[], MarkItDownConverter] | None = None,
    ocr_files: set[Path] | None = None,
    ocr_converter_factory: Callable[[], MarkItDownConverter] | None = None,
    ocr_model: str = "gpt-4o",
) -> MergeResult:
    """Combine Markdown inputs and converted documents in the given order."""
    if not output_name or Path(output_name).name != output_name:
        raise ValueError("Informe apenas o nome do arquivo final, sem pastas.")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_name.casefold().endswith(".md"):
        output_name += ".md"

    reserved = {_path_key(Path(source)) for source in input_files}
    output = output_dir / output_name
    stem = output.stem
    suffix = 2
    while output.exists() or _path_key(output) in reserved:
        output = output_dir / f"{stem} ({suffix}).md"
        suffix += 1

    converter: MarkItDownConverter | None = None
    ocr_converter: MarkItDownConverter | None = None
    ocr_keys = {_path_key(path) for path in (ocr_files or set())}
    failures: list[ConversionResult] = []
    succeeded = 0
    output_created = False

    try:
        for source in input_files:
            source = Path(source)
            if not source.is_file():
                failures.append(
                    ConversionResult(
                        source, None, "O arquivo não existe ou não é um arquivo."
                    )
                )
                continue

            try:
                if source.suffix.casefold() == ".md":
                    content = source.read_text(encoding="utf-8-sig")
                else:
                    if _path_key(source) in ocr_keys:
                        if ocr_converter is None:
                            ocr_converter = (
                                ocr_converter_factory
                                or (lambda: create_ocr_converter(ocr_model))
                            )()
                        active_converter = ocr_converter
                    else:
                        if converter is None:
                            converter = (converter_factory or _default_converter)()
                        active_converter = converter
                    document = active_converter.convert(str(source))
                    content = document.text_content
                    if not isinstance(content, str):
                        raise TypeError(
                            "O conversor não retornou conteúdo Markdown em texto."
                        )
            except Exception as exc:
                message = str(exc).strip() or "Erro sem detalhes."
                failures.append(
                    ConversionResult(
                        source, None, f"{type(exc).__name__}: {message}"
                    )
                )
                continue

            while True:
                if not output_created:
                    try:
                        destination = output.open(
                            "x", encoding="utf-8", newline="\n"
                        )
                        output_created = True
                        break
                    except FileExistsError:
                        candidate_suffix = 2
                        while True:
                            candidate = (
                                output_dir / f"{stem} ({candidate_suffix}).md"
                            )
                            if (
                                not candidate.exists()
                                and _path_key(candidate) not in reserved
                            ):
                                output = candidate
                                break
                            candidate_suffix += 1
                else:
                    destination = output.open("a", encoding="utf-8", newline="\n")
                    break

            with destination:
                if succeeded:
                    destination.write("\n\n---\n\n")
                destination.write(f"## {source.name}\n\n")
                destination.write(content.rstrip())
                destination.write("\n")
            succeeded += 1
    except Exception:
        if output_created and output.exists():
            output.unlink()
        raise

    if not succeeded and output_created and output.exists():
        output.unlink()
        output_created = False

    return MergeResult(output if output_created else None, succeeded, tuple(failures))
