# Conversor em lote para Markdown

A simple desktop app to convert files supported by [Microsoft MarkItDown](https://github.com/microsoft/markitdown) to Markdown. Save one `.md` per input or combine selected files into one document. The UI is available in Portuguese and English; its language choice is saved locally.

Um aplicativo de desktop simples para converter arquivos compatíveis com o [Microsoft MarkItDown](https://github.com/microsoft/markitdown) em Markdown. Salve um `.md` por arquivo ou combine as entradas selecionadas em um único documento. A interface está disponível em português e inglês, e a preferência de idioma fica salva localmente.

## Requirements / Requisitos

- Windows 10 or later / Windows 10 ou superior
- Python 3.10+ with Tcl/Tk (included in the official Windows installer) / Python 3.10+ com Tcl/Tk (incluído no instalador oficial do Windows)

The MarkItDown `all` extra enables its common optional converters. Supported formats depend on MarkItDown and its plugins.

O extra `all` do MarkItDown habilita conversores opcionais comuns. Os formatos aceitos dependem do MarkItDown e de seus plugins.

## Installation / Instalação

Open PowerShell in this folder / Abra o PowerShell nesta pasta:

```shell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Double-click `run.bat` to open the GUI without a console window. For troubleshooting, launch it directly with `.\.venv\Scripts\python.exe app.py`.

Clique duas vezes em `run.bat` para abrir a interface sem janela de terminal. Para diagnóstico, execute `.\.venv\Scripts\python.exe app.py`.

### Optional image OCR / OCR opcional para imagens

OCR uses the optional [`markitdown-ocr`](https://pypi.org/project/markitdown-ocr/) MarkItDown extension and the OpenAI Python client. It supports image extraction in PDF, DOCX, PPTX, and XLSX, including scanned-PDF page OCR. Markdown inputs are joined directly and do not use OCR. Install the optional packages in the same virtual environment as the app:

O OCR usa a extensão opcional [`markitdown-ocr`](https://pypi.org/project/markitdown-ocr/) e o cliente Python da OpenAI. A extensão dá suporte a imagens em PDF, DOCX, PPTX e XLSX, incluindo páginas digitalizadas em PDF. Arquivos Markdown são unidos diretamente, sem OCR. Instale os pacotes opcionais no mesmo ambiente virtual do aplicativo:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt
```

Set your API key before starting the app. For PowerShell, set it for the current terminal and launch `run.bat` from that same terminal:

Defina sua chave de API antes de iniciar. No PowerShell, configure-a para a sessão atual e inicie `run.bat` pelo mesmo terminal:

```powershell
$env:OPENAI_API_KEY = "sua-chave"
.\run.bat
```

Never paste API keys into the app or commit them to the repository. The app checks that the OCR extension and client are installed and that a key is available before starting an OCR batch; it does not store the key. To use an OpenAI-compatible service, set `OPENAI_BASE_URL` as well. Choose a vision-capable model in the UI (default: `gpt-4o`). OCR sends document images to the configured provider and may incur charges; review the provider's privacy and retention terms.

Não cole chaves de API na interface nem as inclua no repositório. Antes de iniciar um lote com OCR, o aplicativo verifica se a extensão, o cliente e a chave estão disponíveis; a chave não é armazenada. Para usar um serviço compatível com OpenAI, defina também `OPENAI_BASE_URL`. Escolha na interface um modelo com suporte a visão (padrão: `gpt-4o`). O OCR envia imagens dos documentos ao provedor configurado e pode gerar custos; verifique as regras de privacidade e retenção desse provedor.

## Usage / Uso

1. Add files using the button or drag and drop them into the list. / Adicione arquivos pelo botão ou arraste-os para a lista.
2. Click the OCR column for each supported PDF, DOCX, PPTX, or XLSX file that should use OCR. The OCR option does not change standard conversions for other rows. / Clique na coluna OCR para cada PDF, DOCX, PPTX ou XLSX que deve usar OCR. Os demais arquivos continuam usando a conversão normal.
3. Choose one Markdown output per input or a single combined file. The combined document follows the displayed order; use ↑ and ↓ to reorder rows. Markdown inputs are read directly, while other inputs are converted by MarkItDown. / Escolha um Markdown por entrada ou um único arquivo combinado. A ordem da lista determina a ordem do resultado; use ↑ e ↓ para reorganizar. Arquivos Markdown são lidos diretamente; os demais passam pelo MarkItDown.
4. Choose the output folder and run the conversion. Existing files are never overwritten; a numeric suffix is added when needed. Individual failures do not stop the rest of the batch. / Escolha a pasta de destino e inicie. Arquivos existentes nunca são substituídos; um sufixo numérico é acrescentado se necessário. Uma falha individual não interrompe o lote.

Use the language selector to switch between English and Portuguese. This preference is saved locally. / Use o seletor de idioma para alternar entre português e inglês. A preferência fica salva localmente.

## Tests / Testes

```shell
python -m unittest -v
```
