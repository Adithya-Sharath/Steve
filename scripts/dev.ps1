# Windows helper: runs API (:8000) and web (:3000) together. Ctrl+C stops both.
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$api = Start-Process -PassThru -NoNewWindow -WorkingDirectory (Join-Path $root "api") $py "-m uvicorn app.main:app --reload --port 8000"
try { Set-Location (Join-Path $root "web"); npm run dev } finally { Stop-Process -Id $api.Id -ErrorAction SilentlyContinue }
