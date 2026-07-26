$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$backendRoot = Join-Path $repoRoot "backend"
$frontendRoot = Join-Path $repoRoot "frontend"
$python = Join-Path $backendRoot ".venv\Scripts\python.exe"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Program,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]] $ProgramArgs
    )

    & $Program @ProgramArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Release gate command failed with exit code ${LASTEXITCODE}: $Program $ProgramArgs"
    }
}

Push-Location $backendRoot
try {
    Invoke-Checked $python -m ruff check app tests
    Invoke-Checked $python -m mypy app
    Invoke-Checked $python -m pytest -q

    $upgradeSql = New-TemporaryFile
    $downgradeSql = New-TemporaryFile
    try {
        & $python -m alembic upgrade head --sql | Set-Content -LiteralPath $upgradeSql
        if ($LASTEXITCODE -ne 0) {
            throw "Alembic offline upgrade failed."
        }
        & $python -m alembic downgrade 20260726_0026:20260726_0025 --sql |
            Set-Content -LiteralPath $downgradeSql
        if ($LASTEXITCODE -ne 0) {
            throw "Alembic offline downgrade failed."
        }
    }
    finally {
        Remove-Item -LiteralPath $upgradeSql, $downgradeSql -Force
    }
}
finally {
    Pop-Location
}

Push-Location $frontendRoot
try {
    Invoke-Checked npm.cmd run build
    Invoke-Checked npm.cmd run typecheck
}
finally {
    Pop-Location
}

Push-Location $repoRoot
try {
    Invoke-Checked git diff --check
}
finally {
    Pop-Location
}

Write-Output "BeoOS source release gate passed."
