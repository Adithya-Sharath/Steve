# Windows helper: engine + API tests
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
Set-Location (Join-Path $root "engine"); & $py -m pytest -q
Set-Location (Join-Path $root "api"); & $py -m pytest -q
