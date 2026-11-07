@echo off
setlocal
set "PYTHONW=%~dp0.venv\Scripts\pythonw.exe"
if not exist "%PYTHONW%" (
    powershell.exe -NoProfile -WindowStyle Hidden -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Ambiente Python nao encontrado. Consulte README.md para instalar as dependencias primeiro.','Conversor em lote para Markdown','OK','Warning') | Out-Null"
    exit /b 1
)
start "" "%PYTHONW%" "%~dp0launch.pyw"
