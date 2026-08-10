$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

Set-Location $ProjectRoot

$PythonTools = @(
    @{ Name = "Ruff lint"; Command = ".\.venv\Scripts\ruff.exe"; Arguments = @("check", ".") },
    @{ Name = "Ruff format"; Command = ".\.venv\Scripts\ruff.exe"; Arguments = @("format", "--check", ".") },
    @{ Name = "mypy"; Command = ".\.venv\Scripts\mypy.exe"; Arguments = @("backend", "workers") },
    @{ Name = "pytest"; Command = ".\.venv\Scripts\pytest.exe"; Arguments = @() }
)

foreach ($Tool in $PythonTools) {
    Write-Host "Running $($Tool.Name)..."
    & $Tool.Command @($Tool.Arguments)
    if ($LASTEXITCODE -ne 0) { throw "$($Tool.Name) failed" }
}

Push-Location frontend
try {
    foreach ($Script in @("lint", "typecheck", "test", "build")) {
        Write-Host "Running frontend $Script..."
        npm.cmd run $Script
        if ($LASTEXITCODE -ne 0) { throw "Frontend $Script failed" }
    }
}
finally {
    Pop-Location
}

Write-Host "All quality gates passed."

