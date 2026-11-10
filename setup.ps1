$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    python -m venv (Join-Path $projectDir '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Gagal membuat virtual environment.' }
}
& $pythonExe -m pip install -r (Join-Path $projectDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Instalasi dependency gagal.' }
& $pythonExe -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw 'Instalasi Chromium gagal.' }
Write-Output 'Siap. Jalankan .\run.ps1'
