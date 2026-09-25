# Windows helper: full evaluation pipeline (baseline skipped if GEMINI_API_KEY is unset)
$root = Split-Path -Parent $PSScriptRoot
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
Set-Location $root
foreach ($s in "generate", "run_engine", "run_baseline", "metrics", "update_readme") { & $py "eval/$s.py" }
