$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Jalankan setup.ps1 terlebih dahulu.'
}
& $pythonExe (Join-Path $projectDir 'main.py')
