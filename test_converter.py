from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from importlib.metadata import PackageNotFoundError

from converter import get_ocr_setup_issue, iter_convert_files, merge_files


class FakeConverter:
    def convert(self, source: str) -> SimpleNamespace:
        path = Path(source)
        if path.name == "quebrado.bin":
            raise ValueError("formato inválido")
        return SimpleNamespace(text_content=f"# {path.stem}\n")


class ConverterTests(unittest.TestCase):
    def test_converts_files_and_does_not_overwrite_existing_files(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_a = root / "relatorio.pdf"
            source_b = root / "relatorio.docx"
            output_dir = root / "saida"
            source_a.touch()
            source_b.touch()
            output_dir.mkdir()
            (output_dir / "relatorio.md").write_text("preservar", encoding="utf-8")

            results = list(
                iter_convert_files(
                    [source_a, source_b], output_dir, converter_factory=FakeConverter
                )
            )

            self.assertTrue(all(result.succeeded for result in results))
            self.assertEqual(
                [result.output.name for result in results if result.output],
                ["relatorio (2).md", "relatorio (3).md"],
            )
            self.assertEqual(
                (output_dir / "relatorio.md").read_text(encoding="utf-8"),
                "preservar",
            )

    def test_one_conversion_failure_does_not_stop_the_batch(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            good = root / "bom.txt"
            bad = root / "quebrado.bin"
            good.touch()
            bad.touch()

            results = list(
                iter_convert_files(
                    [bad, good], root / "saida", converter_factory=FakeConverter
                )
            )

            self.assertEqual([result.succeeded for result in results], [False, True])
            self.assertIn("formato inválido", results[0].error or "")
            self.assertEqual(results[1].output.read_text(encoding="utf-8"), "# bom\n")

    def test_output_name_cannot_overwrite_an_input_file(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "texto.md"
            source.write_text("original", encoding="utf-8")

            result = next(
                iter_convert_files(
                    [source], root, converter_factory=FakeConverter
                )
            )

            self.assertEqual(result.output.name, "texto (2).md")
            self.assertEqual(source.read_text(encoding="utf-8"), "original")

    def test_merges_markdown_files_in_order_without_a_converter(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "primeiro.md"
            second = root / "segundo.md"
            first.write_text("# Primeiro\n\nConteúdo A", encoding="utf-8")
            second.write_text("# Segundo\n\nConteúdo B", encoding="utf-8")

            def unexpected_converter() -> FakeConverter:
                self.fail("Markdown deve ser unido sem iniciar o conversor")

            result = merge_files(
                [first, second],
                root / "saida",
                "unido",
                converter_factory=unexpected_converter,
            )

            self.assertEqual(result.succeeded, 2)
            self.assertEqual(result.failures, ())
            self.assertEqual(result.output.name, "unido.md")
            content = result.output.read_text(encoding="utf-8")
            self.assertLess(
                content.index("## primeiro.md"), content.index("## segundo.md")
            )
            self.assertIn("\n\n---\n\n", content)
            self.assertIn("Conteúdo A", content)
            self.assertIn("Conteúdo B", content)

    def test_merges_converted_and_markdown_inputs_and_continues_after_failure(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            bad = root / "quebrado.bin"
            converted = root / "bom.txt"
            markdown = root / "ultimo.md"
            bad.touch()
            converted.touch()
            markdown.write_text("Conteúdo Markdown", encoding="utf-8")

            result = merge_files(
                [converted, bad, markdown],
                root / "saida",
                "compilado.md",
                converter_factory=FakeConverter,
            )

            self.assertEqual(result.succeeded, 2)
            self.assertEqual(len(result.failures), 1)
            content = result.output.read_text(encoding="utf-8")
            self.assertLess(
                content.index("## bom.txt"), content.index("## ultimo.md")
            )
            self.assertNotIn("quebrado.bin", content)

    def test_merged_output_does_not_overwrite_existing_files_or_inputs(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "saida.md"
            source.write_text("conteúdo de entrada", encoding="utf-8")
            (root / "final.md").write_text("preservar", encoding="utf-8")

            result = merge_files(
                [source], root, "final.md", converter_factory=FakeConverter
            )

            self.assertEqual(result.output.name, "final (2).md")
            self.assertEqual(
                (root / "final.md").read_text(encoding="utf-8"), "preservar"
            )
            self.assertEqual(
                source.read_text(encoding="utf-8"), "conteúdo de entrada"
            )

    def test_merged_output_name_rejects_directory_paths(self) -> None:
        with TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                merge_files([], Path(temporary), "../fora.md")

    def test_only_selected_files_use_ocr_during_individual_conversion(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_pdf = root / "com_imagem.pdf"
            regular_pdf = root / "normal.pdf"
            image_pdf.touch()
            regular_pdf.touch()
            calls = []

            class NamedConverter:
                def __init__(self, label: str) -> None:
                    self.label = label

                def convert(self, source: str) -> SimpleNamespace:
                    calls.append((Path(source).name, self.label))
                    return SimpleNamespace(text_content=f"# {self.label}\n")

            results = list(
                iter_convert_files(
                    [image_pdf, regular_pdf],
                    root / "saida",
                    converter_factory=lambda: NamedConverter("padrão"),
                    ocr_files={image_pdf},
                    ocr_converter_factory=lambda: NamedConverter("OCR"),
                )
            )

            self.assertTrue(all(result.succeeded for result in results))
            self.assertEqual(
                calls, [("com_imagem.pdf", "OCR"), ("normal.pdf", "padrão")]
            )

    def test_only_selected_files_use_ocr_during_merge(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            image_docx = root / "figura.docx"
            regular_docx = root / "texto.docx"
            image_docx.touch()
            regular_docx.touch()
            calls = []

            class NamedConverter:
                def __init__(self, label: str) -> None:
                    self.label = label

                def convert(self, source: str) -> SimpleNamespace:
                    calls.append((Path(source).name, self.label))
                    return SimpleNamespace(text_content=f"# {self.label}\n")

            result = merge_files(
                [image_docx, regular_docx],
                root / "saida",
                "compilado",
                converter_factory=lambda: NamedConverter("padrão"),
                ocr_files={image_docx},
                ocr_converter_factory=lambda: NamedConverter("OCR"),
            )

            self.assertEqual(result.succeeded, 2)
            self.assertEqual(
                calls, [("figura.docx", "OCR"), ("texto.docx", "padrão")]
            )

    def test_ocr_preflight_checks_model_extension_client_and_api_key(self) -> None:
        self.assertEqual(get_ocr_setup_issue(""), "model")
        with patch(
            "converter.distribution", side_effect=PackageNotFoundError
        ):
            self.assertEqual(get_ocr_setup_issue("vision-model"), "plugin")

        with patch("converter.distribution"), patch("converter.find_spec", return_value=None):
            self.assertEqual(get_ocr_setup_issue("vision-model"), "client")

        with (
            patch("converter.distribution"),
            patch("converter.find_spec", return_value=object()),
            patch.dict("os.environ", {}, clear=True),
        ):
            self.assertEqual(get_ocr_setup_issue("vision-model"), "key")

        with (
            patch("converter.distribution"),
            patch("converter.find_spec", return_value=object()),
            patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True),
        ):
            self.assertIsNone(get_ocr_setup_issue("vision-model"))


if __name__ == "__main__":
    unittest.main()
