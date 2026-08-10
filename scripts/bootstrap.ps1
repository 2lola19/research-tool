$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot

if (-not (Test-Path -LiteralPath ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }

& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed" }

Push-Location frontend
try {
    npm.cmd install
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed" }
}
finally {
    Pop-Location
}

Write-Host "Development dependencies installed. Copy .env.example to .env before native database work."

